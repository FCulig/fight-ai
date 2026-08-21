"""
Auto-detect the scoreboard overlay ROI from a video.

Strategy — bottom-strip OCR:
  1. Sample SCOREBOARD_STRIP_SEARCH_FRAMES frames spread across the video.
  2. For each frame, crop the bottom strip (y >= H * SCOREBOARD_STRIP_Y_START).
     Scoreboards in MMA broadcasts are always in this region.
  3. Run EasyOCR on the strip and collect every bounding box whose text
     matches a timer (M:SS) or round-number pattern.
  4. Union all collected boxes across all sampled frames → ROI.
  5. Validate by re-running OCR on the candidate ROI across a few frames;
     require a minimum timer-match rate before accepting.

Results are cached in roi.json keyed by video file stats so repeat runs
of the same file skip calibration entirely.
"""

import json
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .parsers import (
    parse_timer,
    parse_round,
    parse_round_from_boxes,
    find_round_digit_box,
)
from .debug import draw_roi
from debug import DebugContext
from models.constants import (
    SCOREBOARD_STRIP_Y_START,
    SCOREBOARD_STRIP_SEARCH_FRAMES,
    SCOREBOARD_CAL_EDGE_SKIP_RATIO,
    SCOREBOARD_CAL_VALIDATE_FRAMES,
    SCOREBOARD_CAL_MIN_MATCH_RATE,
    SCOREBOARD_ROI_PADDING,
    SCOREBOARD_OCR_MIN_CONFIDENCE,
    SCOREBOARD_OCR_UPSCALE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dominant_position_cluster(
    boxes: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    """
    Keep only the boxes sitting at the overlay's own position.

    A broadcast puts more than one timer-shaped string in the bottom strip —
    ground-control clocks, stat panels and sponsor countdowns all read as MM:SS
    — but only the round clock holds one fixed position for the whole fight.
    Because the ROI is a min/max union, a *single* stray match is enough to
    stretch it across half the frame, and the extraction crop then carries a
    second clock that competes with the real one.

    Boxes are grouped by centre proximity and the largest group wins: the round
    clock is on screen far more often than any transient panel. The tolerance is
    the median box size, so it scales with resolution and needs no constant.
    """
    if not boxes:
        return boxes

    tol_x = max(1.0, float(np.median([b[2] - b[0] for b in boxes])))
    tol_y = max(1.0, float(np.median([b[3] - b[1] for b in boxes])))

    def centre(b: tuple[int, int, int, int]) -> tuple[float, float]:
        return (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0

    clusters: list[list[tuple[int, int, int, int]]] = []
    for box in boxes:
        cx, cy = centre(box)
        for cluster in clusters:
            mx = float(np.mean([centre(c)[0] for c in cluster]))
            my = float(np.mean([centre(c)[1] for c in cluster]))
            if abs(cx - mx) <= tol_x and abs(cy - my) <= tol_y:
                cluster.append(box)
                break
        else:
            clusters.append([box])

    return max(clusters, key=len)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calibrate_scoreboard_overlay(
    video_path: str,
    override_roi: Optional[tuple[int, int, int, int]] = None,
    recalibrate: bool = False,
    debug_ctx: Optional[DebugContext] = None,
) -> Optional[dict]:
    """
    Auto-detect (or accept a manual override for) the scoreboard overlay ROI.

    Args:
        video_path:   Path to the source video.
        override_roi: (x, y, w, h) — skips auto-detection when provided.
        recalibrate:  Delete the cached roi.json and re-run detection.
        debug_ctx:    DebugContext rooted at runs/scoreboard_overlay/.

    Returns:
        {"x", "y", "w", "h", "frame_dims": [W, H]} or None on failure.
    """
    ctx = debug_ctx or DebugContext.disabled()

    # --- Recalibrate: wipe the cache before the cache-check below ---
    if recalibrate:
        roi_cache = str(ctx.path("roi.json"))
        if os.path.exists(roi_cache):
            os.remove(roi_cache)
            ctx.log("calibration", "Cleared cached ROI — recalibrating")

    # --- Manual override ---
    if override_roi is not None:
        x, y, w, h = override_roi
        roi = {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
        ctx.log("calibration", f"Manual override ROI: {roi}")
        cap = cv2.VideoCapture(video_path)
        W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        roi["frame_dims"] = [W, H]
        save_roi(roi, str(ctx.path("roi.json")), video_path)
        return roi

    # --- Cache check ---
    cached = load_roi(str(ctx.path("roi.json")), video_path)
    if cached:
        ctx.log("calibration", f"Loaded cached ROI: {cached}")
        return cached

    ctx.log("calibration", f"Auto-detecting ROI in {video_path}")
    ctx.start_timer("calibration")
    cal = ctx.subdir("calibration_debug")

    # --- Open video ---
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        ctx.log("calibration", f"ERROR: cannot open {video_path}")
        return None

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps   = cap.get(cv2.CAP_PROP_FPS)
    W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ctx.log("calibration", f"Video {W}×{H}  {fps:.1f}fps  {total} frames")

    strip_y = int(H * SCOREBOARD_STRIP_Y_START)
    ctx.log("calibration",
            f"Search strip: y={strip_y}–{H} "
            f"(bottom {100*(1-SCOREBOARD_STRIP_Y_START):.0f}% of frame)")

    # Skip the head and tail (walkout, tale-of-the-tape and post-fight graphics
    # carry text but no live scoreboard, and sampling them wastes OCR passes).
    skip    = max(1, int(total * SCOREBOARD_CAL_EDGE_SKIP_RATIO))
    usable  = max(1, total - 2 * skip)
    n       = min(SCOREBOARD_STRIP_SEARCH_FRAMES, usable)
    indices = [skip + int(i * usable / n) for i in range(n)]

    # --- Init EasyOCR ---
    import easyocr
    import torch
    reader = easyocr.Reader(["en"], gpu=True, verbose=False)

    try:
        det_dev = next(reader.detector.parameters()).device
        rec_dev = next(reader.recognizer.parameters()).device
        ctx.log("calibration",
                f"EasyOCR  detector={det_dev}  recognizer={rec_dev}  "
                f"torch.cuda.is_available()={torch.cuda.is_available()}")
        if det_dev.type != "cuda":
            ctx.log("calibration",
                    "WARNING: EasyOCR running on CPU — calibration will be slow. "
                    "Fix: pip install --force-reinstall torch torchvision "
                    "--index-url https://download.pytorch.org/whl/cu126")
    except Exception as exc:
        ctx.log("calibration", f"Could not introspect EasyOCR device: {exc}")

    # --- Strip OCR pass ---
    # Accumulate bounding boxes (in full-frame coords) that match timer or round.
    timer_boxes: list[tuple[int, int, int, int]] = []   # (x1,y1,x2,y2)
    round_boxes: list[tuple[int, int, int, int]] = []

    reference_frame: Optional[np.ndarray] = None
    log_lines: list[str] = []

    for frame_idx, vid_idx in enumerate(indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, vid_idx)
        ret, frame = cap.read()
        if not ret:
            ctx.log("calibration", f"Frame {vid_idx}: could not read, skipping")
            continue
        if reference_frame is None:
            reference_frame = frame.copy()

        strip = frame[strip_y:H, 0:W]
        results = reader.readtext(strip)

        ctx.log("calibration",
                f"Frame {frame_idx+1}/{n}  (vid_frame={vid_idx})  "
                f"→ {len(results)} text regions in strip")

        # Debug: annotate strip with all detections
        strip_dbg = strip.copy()
        for (bbox, text, conf) in results:
            pts = np.array(bbox, dtype=np.int32)
            is_timer = parse_timer(text) is not None
            is_round = parse_round(text) is not None
            colour = (0, 255, 0) if is_timer else ((255, 100, 0) if is_round else (120, 120, 120))
            cv2.polylines(strip_dbg, [pts], isClosed=True, color=colour, thickness=2)
            cv2.putText(strip_dbg, f"{text[:20]} ({conf:.2f})",
                        (int(pts[0][0]), max(0, int(pts[0][1]) - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1, cv2.LINE_AA)

        if ctx.verbose:
            cv2.imwrite(str(cal.path(f"strip_frame_{frame_idx:02d}.jpg")), strip_dbg)

        # Collect timer- and round-matching boxes (adjust y back to full-frame)
        for (bbox, text, conf) in results:
            if conf < SCOREBOARD_OCR_MIN_CONFIDENCE:
                continue
            pts = np.array(bbox, dtype=np.int32)
            xs  = pts[:, 0]
            ys  = pts[:, 1] + strip_y   # back to full-frame y
            aabb = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

            if parse_timer(text) is not None:
                timer_boxes.append(aabb)
                log_lines.append(
                    f"  TIMER  frame={vid_idx}  text={text!r}  conf={conf:.2f}  box={aabb}"
                )
            elif parse_round(text) is not None:
                round_boxes.append(aabb)
                log_lines.append(
                    f"  ROUND  frame={vid_idx}  text={text!r}  conf={conf:.2f}  box={aabb}"
                )

        # A bare round digit matches no text pattern, so it is found by its
        # position beside the timer. It must be unioned into the ROI explicitly:
        # on a typical overlay it sits just outside a timer-only crop, and a crop
        # that clips it leaves the round number unreadable for the whole run.
        digit = find_round_digit_box(results, SCOREBOARD_OCR_MIN_CONFIDENCE)
        if digit is not None:
            (dx1, dy1, dx2, dy2), value = digit
            aabb = (int(dx1), int(dy1) + strip_y, int(dx2), int(dy2) + strip_y)
            round_boxes.append(aabb)
            log_lines.append(
                f"  DIGIT  frame={vid_idx}  round={value}  box={aabb}  (positional)"
            )

    cap.release()

    if ctx.verbose:
        with open(cal.path("calibration_log.txt"), "w", encoding="utf-8") as f:
            f.write(f"Strip y_start={strip_y}  frames_sampled={n}\n\n")
            f.write("\n".join(log_lines))

    ctx.log("calibration",
            f"Collected {len(timer_boxes)} timer boxes  "
            f"{len(round_boxes)} round boxes across {n} frames")

    if not timer_boxes and not round_boxes:
        ctx.log("calibration",
                "ERROR: no timer or round pattern found in bottom strip across any "
                f"sampled frame ({n} sampled). "
                "Check calibration_debug/strip_frame_*.jpg to see what EasyOCR found. "
                "Possible causes: overlay absent, font unrecognised, EasyOCR on CPU (too slow).")
        return None

    # --- Union the boxes at the overlay's own position → ROI ---
    # Outliers are dropped first: a raw union stretches the ROI to cover every
    # stray match, and one is enough to do it (see _dominant_position_cluster).
    timer_boxes = _dominant_position_cluster(timer_boxes)
    round_boxes = _dominant_position_cluster(round_boxes)
    ctx.log("calibration",
            f"After position clustering: {len(timer_boxes)} timer  "
            f"{len(round_boxes)} round boxes")

    all_boxes = timer_boxes + round_boxes
    x1 = min(b[0] for b in all_boxes)
    y1 = min(b[1] for b in all_boxes)
    x2 = max(b[2] for b in all_boxes)
    y2 = max(b[3] for b in all_boxes)

    # Add padding, clamp to frame
    x1 = max(0,     x1 - SCOREBOARD_ROI_PADDING)
    y1 = max(0,     y1 - SCOREBOARD_ROI_PADDING)
    x2 = min(W,     x2 + SCOREBOARD_ROI_PADDING)
    y2 = min(H,     y2 + SCOREBOARD_ROI_PADDING)
    roi_candidate = {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}

    ctx.log("calibration", f"Candidate ROI (union + padding): {roi_candidate}")

    # --- Validate: re-OCR the candidate ROI on frames spread across the video ---
    # This must mirror extract_scoreboard_samples() exactly — same upscale, same
    # acceptance test. Validating on the raw tight crop while extraction OCRs a
    # 3x upscale makes the gate stricter than the thing it is gating, and a
    # small-digit ROI that production reads fine gets rejected here.
    n_val = min(SCOREBOARD_CAL_VALIDATE_FRAMES, len(indices))
    validate_indices = [indices[int(i * len(indices) / n_val)] for i in range(n_val)]

    matches = 0
    cap = cv2.VideoCapture(video_path)
    for vid_idx in validate_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, vid_idx)
        ret, frame = cap.read()
        if not ret:
            continue
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        upscaled = cv2.resize(
            crop,
            (crop.shape[1] * SCOREBOARD_OCR_UPSCALE, crop.shape[0] * SCOREBOARD_OCR_UPSCALE),
            interpolation=cv2.INTER_CUBIC,
        )
        results = reader.readtext(upscaled)
        text = " ".join(t for (_, t, c) in results if c >= SCOREBOARD_OCR_MIN_CONFIDENCE)
        # Either signal is enough: an overlay that yields only a round number is
        # still worth extracting, and one that yields only a timer is the common
        # case that drives round-clock segmentation.
        if (parse_timer(text) is not None
                or parse_round_from_boxes(results, SCOREBOARD_OCR_MIN_CONFIDENCE) is not None):
            matches += 1
    cap.release()

    match_rate = matches / len(validate_indices) if validate_indices else 0.0
    ctx.log("calibration",
            f"Validation: timer or round found in {matches}/{len(validate_indices)} "
            f"frames ({match_rate:.0%})")

    if match_rate < SCOREBOARD_CAL_MIN_MATCH_RATE:
        ctx.log("calibration",
                f"ERROR: validation failed (match rate {match_rate:.0%} < "
                f"{SCOREBOARD_CAL_MIN_MATCH_RATE:.0%}). "
                "The union ROI does not reliably produce a timer or round number. "
                "Check calibration_debug/strip_frame_*.jpg")
        return None

    # --- Save debug + cache ---
    roi_out = {**roi_candidate, "frame_dims": [W, H]}

    if reference_frame is not None:
        annotated = draw_roi(reference_frame, roi_candidate,
                             color=(0, 255, 0),
                             label=f"ROI  match={match_rate:.0%}")
        # Also draw individual timer boxes (green) and round boxes (blue)
        for (bx1, by1, bx2, by2) in timer_boxes:
            cv2.rectangle(annotated, (bx1, by1), (bx2, by2), (0, 220, 0), 1)
        for (bx1, by1, bx2, by2) in round_boxes:
            cv2.rectangle(annotated, (bx1, by1), (bx2, by2), (255, 100, 0), 1)
        cv2.imwrite(str(cal.path("selected_roi.jpg")), annotated)
        ctx.log("calibration",
                f"Debug image → {cal.path('selected_roi.jpg')}")

    save_roi(roi_out, str(ctx.path("roi.json")), video_path)
    ctx.stop_timer("calibration")
    ctx.log("calibration", f"Done. ROI={roi_out}")
    return roi_out


# ---------------------------------------------------------------------------
# ROI persistence helpers (cache keyed by file stats)
# ---------------------------------------------------------------------------

def _cache_key(video_path: str) -> str:
    stat = os.stat(video_path)
    return f"{Path(video_path).name}|{stat.st_size}|{int(stat.st_mtime)}"


def save_roi(roi: dict, path: str, video_path: Optional[str] = None) -> None:
    data = dict(roi)
    if video_path:
        data["_cache_key"] = _cache_key(video_path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_roi(path: str, video_path: Optional[str] = None) -> Optional[dict]:
    """Load cached ROI; returns None if file missing or cache key stale."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if video_path and data.get("_cache_key") != _cache_key(video_path):
        return None
    return {k: v for k, v in data.items() if not k.startswith("_")}
