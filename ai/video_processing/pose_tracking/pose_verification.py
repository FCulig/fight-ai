import re
import time
import cv2
import numpy as np
from fight_processing.fight_processing_util import determine_fight_state, is_frame_valid
from models.FightState import FightState, GRAPPLING_STATES


# ---------------------------------------------------------------------------
# Round helpers
# ---------------------------------------------------------------------------

def _frame_number_from_name(image_name: str) -> int | None:
    """Extract the integer frame index from a path like 'frames/frame_1234.jpg'."""
    m = re.search(r"frame_(\d+)", image_name)
    return int(m.group(1)) if m else None


def _is_in_round(frame_num: int, rounds: list[tuple[int, int]]) -> bool:
    return any(start <= frame_num <= end for start, end in rounds)


def _next_round_start(frame_num: int, rounds: list[tuple[int, int]]) -> int | None:
    """Return the start frame of the nearest upcoming round, or None."""
    upcoming = [start for start, end in rounds if start > frame_num]
    return min(upcoming) if upcoming else None


def _draw_between_rounds(frame_bgr: np.ndarray, frame_num: int,
                         rounds: list[tuple[int, int]]) -> None:
    """Dim the frame and overlay a 'BETWEEN ROUNDS' label."""
    h, w = frame_bgr.shape[:2]

    overlay = frame_bgr.copy()
    cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame_bgr, 0.45, 0, frame_bgr)

    label      = "BETWEEN ROUNDS"
    font       = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.6
    thickness  = 3
    (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
    cx = (w - tw) // 2
    cy = (h + th) // 2

    cv2.putText(frame_bgr, label, (cx, cy),
                font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    nxt = _next_round_start(frame_num, rounds)
    sub = f"Next round starts at frame {nxt}" if nxt is not None else "Fight over"
    (sw, _), _ = cv2.getTextSize(sub, font, 0.6, 1)
    cv2.putText(frame_bgr, sub, ((w - sw) // 2, cy + th + 20),
                font, 0.6, (180, 180, 180), 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Frame reader
# ---------------------------------------------------------------------------

def _read_frame(
    frame_num: int,
    image_name: str,
    cap: cv2.VideoCapture | None,
) -> np.ndarray | None:
    """
    Read a single frame either from the supplied VideoCapture or from disk.

    When cap is provided (video_path was given), seek to frame_num and decode.
    Falls back to cv2.imread(image_name) when cap is None.
    """
    if cap is not None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num - 1)
        ret, frame = cap.read()
        return frame if ret else None
    return cv2.imread(image_name)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def verify_pose_tracking(
    pose_data: dict,
    rounds: list[tuple[int, int]],
    fps: int,
    video_path: str | None = None,
    start_frame: int | None = None,
    end_frame: int | None = None,
):
    """[DEBUG] Create a visualisation video with pose tracking and round awareness.

    Renders an annotated MP4 from the in-memory pose dict.

    When a frame falls within a known round (as detected by segment_fights):
      - Bounding boxes and pose skeletons are drawn.
      - Grappling state is evaluated; a unified purple bbox is drawn when grappling.

    When a frame is between rounds:
      - No bounding boxes or skeletons are drawn.
      - The frame is dimmed and a centred "BETWEEN ROUNDS" label is shown,
        along with the start frame of the next round.

    Args:
        pose_data:   In-memory corner-assigned dict from assign_corners()
                     (or loaded from a --pose-results dev override).
        rounds:      List of (start_frame, end_frame) tuples from segment_fights().
        fps:         Frames per second, taken from the fights DB row.
        video_path:  Path to the source .mp4. When supplied, frames are read
                     directly from the video (no dependency on frames/ directory).
                     When None, frames are read from the image_name paths in the dict.
        start_frame: First frame to render (inclusive). None = beginning of video.
        end_frame:   Last frame to render (inclusive). None = end of video.

    Output:
        Writes 'pose_overlay.mp4' to the working directory.
    """
    LOG_INTERVAL = 500   # print a progress line every N frames
    TAG          = "[pose_verify]"

    def log(msg: str) -> None:
        print(f"{TAG} {msg}")

    OUTPUT_MP4 = "pose_overlay.mp4"

    log("Loading pose data (in-memory)")
    frames = pose_data.get("frames", [])
    log(f"{len(frames)} frames in pose data  |  fps={fps}")

    # --- Apply time-range filter ---
    if start_frame is not None or end_frame is not None:
        sf = start_frame or 0
        ef = end_frame   or float("inf")
        frames_before = len(frames)
        frames = [
            fe for fe in frames
            if (fn := _frame_number_from_name(fe.get("image_name", ""))) is not None
            and sf <= fn <= ef
        ]
        log(
            f"Time range filter: frames {sf}–{ef}  "
            f"({sf/fps:.1f}s–{ef/fps:.1f}s)  "
            f"{frames_before} → {len(frames)} frames"
        )

    SKELETON_EDGES = [
        (0, 1), (0, 2), (1, 3), (2, 4),
        (0, 5), (0, 6),
        (5, 7), (7, 9),
        (6, 8), (8, 10),
        (5, 6),
        (5, 11), (6, 12),
        (11, 12),
        (11, 13), (13, 15),
        (12, 14), (14, 16),
    ]

    COLOR_FIGHTER_0 = (0, 0, 255)
    COLOR_FIGHTER_1 = (255, 0, 0)
    COLOR_REFEREE   = (0, 255, 0)
    COLOR_GRAPPLING = (255, 0, 255)

    # Scale factors from frames/ coordinate space → display frame coordinate space.
    # Computed after the first frame is read; draw_pose reads them by closure reference.
    sx = sy = 1.0

    def color_for(det):
        cid = det.get("class_id")
        if cid == 0: return COLOR_FIGHTER_0
        if cid == 1: return COLOR_FIGHTER_1
        if cid == 2: return COLOR_REFEREE
        return (255, 255, 255)

    def draw_pose(frame_bgr, det):
        bbox = det.get("bbox_xyxy")
        if bbox and len(bbox) == 4:
            x1 = int(round(bbox[0] * sx))
            y1 = int(round(bbox[1] * sy))
            x2 = int(round(bbox[2] * sx))
            y2 = int(round(bbox[3] * sy))
            x1, y1 = max(0, min(w - 1, x1)), max(0, min(h - 1, y1))
            x2, y2 = max(0, min(w - 1, x2)), max(0, min(h - 1, y2))
            if x2 > x1 and y2 > y1:
                cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), color_for(det), 2)

        keypoints = det.get("keypoints")
        if not keypoints:
            return

        for a, b in SKELETON_EDGES:
            if a < len(keypoints) and b < len(keypoints):
                pa, pb = keypoints[a], keypoints[b]
                if pa is None or pb is None:
                    continue
                xa = int(round(pa[0] * sx))
                ya = int(round(pa[1] * sy))
                xb = int(round(pb[0] * sx))
                yb = int(round(pb[1] * sy))
                if 0 <= xa < w and 0 <= ya < h and 0 <= xb < w and 0 <= yb < h:
                    cv2.line(frame_bgr, (xa, ya), (xb, yb), color_for(det), 2)

        for k in keypoints:
            if k is None or len(k) < 2:
                continue
            x = int(round(k[0] * sx))
            y = int(round(k[1] * sy))
            if 0 <= x < w and 0 <= y < h:
                cv2.circle(frame_bgr, (x, y), 3, color_for(det), -1)

    # --- Open video capture if a video path was supplied ---
    cap: cv2.VideoCapture | None = None
    if video_path:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")
        # Seek once to the first frame in the (possibly filtered) range,
        # then read sequentially from there to avoid H.264 decode errors.
        if frames:
            first_fn = _frame_number_from_name(frames[0].get("image_name", ""))
            if first_fn and first_fn > 1:
                cap.set(cv2.CAP_PROP_POS_FRAMES, first_fn - 1)
                log(f"Video source : {video_path}  (seeked to frame {first_fn})")
            else:
                log(f"Video source : {video_path}")
    else:
        log("Video source : frames/ directory")

    # --- Locate first readable frame to initialise the VideoWriter ---
    first_img = None
    for fe in frames:
        img_name  = fe.get("image_name", "")
        frame_num = _frame_number_from_name(img_name)
        if frame_num is None and cap is None:
            continue
        img = _read_frame(frame_num or 1, img_name, cap)
        if img is not None:
            first_img = img
            break

    if first_img is None:
        if cap:
            cap.release()
        raise FileNotFoundError(
            "No readable frames found. "
            + ("Check the video path." if video_path else "Check the frames/ directory.")
        )

    h, w = first_img.shape[:2]
    log(f"Frame size   : {w}×{h}")

    # --- Detect coordinate mismatch between frames/ and video resolution ---
    # Keypoints were computed on the frames/ images; if those are a different
    # resolution from the video, every coordinate must be scaled before drawing.
    if cap is not None:
        src_img_name = next(
            (fe.get("image_name") for fe in frames if fe.get("image_name")), None
        )
        if src_img_name:
            src_sample = cv2.imread(src_img_name)
            if src_sample is not None:
                h_src, w_src = src_sample.shape[:2]
                if w_src != w or h_src != h:
                    sx = w / w_src   # update the closure variables
                    sy = h / h_src
                    log(f"Resolution mismatch: frames/={w_src}×{h_src}  "
                        f"video={w}×{h}  scale=({sx:.4f}, {sy:.4f})")
                else:
                    log(f"Resolution match: frames/ and video both {w}×{h} — no scaling")
            else:
                log("WARNING: Could not read a frames/ image to check resolution "
                    "— keypoint scaling disabled (sx=sy=1.0)")
        else:
            log("WARNING: No image_name entries in pose JSON — "
                "keypoint scaling disabled (sx=sy=1.0)")

    log(f"Output       : {OUTPUT_MP4}")
    log(f"Rounds       : {rounds}")
    log("Starting render …")

    writer = cv2.VideoWriter(OUTPUT_MP4, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    current_fight_state = FightState.STRIKING
    state_counters      = {"striking": 0, "clinch": 0, "ground": 0}
    written = missing   = 0
    total               = len(frames)
    t_start             = time.perf_counter()

    for fe in frames:
        img_name  = fe.get("image_name", "")
        frame_num = _frame_number_from_name(img_name)

        if frame_num is None and cap is None:
            missing += 1
            continue

        frame_img = _read_frame(frame_num or 0, img_name, cap)
        if frame_img is None:
            missing += 1
            continue

        detections = fe.get("detections", [])

        # ---- Progress log ----
        if written > 0 and written % LOG_INTERVAL == 0:
            pct    = 100 * written / total if total else 0
            in_rnd = frame_num is not None and _is_in_round(frame_num, rounds)
            if in_rnd:
                state_label = current_fight_state.name
                phase = f"round in progress | state: {state_label}"
            else:
                phase = "between rounds"
            log(f"{written:>6} / {total}  ({pct:5.1f}%)  — {phase}")

        # ---- Between-rounds frame ----
        if frame_num is not None and not _is_in_round(frame_num, rounds):
            _draw_between_rounds(frame_img, frame_num, rounds)
            writer.write(frame_img)
            written += 1
            continue

        # ---- In-round frame: pose + grappling logic ----
        if is_frame_valid(detections):
            current_fight_state, state_counters = determine_fight_state(
                detections,
                state_counters,
                current_fight_state,
            )

        if current_fight_state in GRAPPLING_STATES:
            fighter_dets = [
                d for d in detections
                if d.get("class_id") in (0, 1) and d.get("bbox_xyxy")
            ]
            if fighter_dets:
                xs1 = [d["bbox_xyxy"][0] * sx for d in fighter_dets]
                ys1 = [d["bbox_xyxy"][1] * sy for d in fighter_dets]
                xs2 = [d["bbox_xyxy"][2] * sx for d in fighter_dets]
                ys2 = [d["bbox_xyxy"][3] * sy for d in fighter_dets]
                ux1, uy1 = int(min(xs1)), int(min(ys1))
                ux2, uy2 = int(max(xs2)), int(max(ys2))
                cv2.rectangle(frame_img, (ux1, uy1), (ux2, uy2), COLOR_GRAPPLING, 3)
                cv2.putText(frame_img, current_fight_state.name, (ux1, max(15, uy1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_GRAPPLING, 2, cv2.LINE_AA)
        else:
            for det in detections:
                draw_pose(frame_img, det)

        writer.write(frame_img)
        written += 1

    writer.release()
    if cap:
        cap.release()

    elapsed = time.perf_counter() - t_start
    log(f"Finished in {elapsed:.1f}s — wrote {OUTPUT_MP4} "
        f"({written} frames rendered, {missing} missing)")
