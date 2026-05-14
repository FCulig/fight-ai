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

from .parsers import parse_timer, parse_round
from .debug import draw_roi
from debug import DebugContext
from models.constants import (
    SCOREBOARD_STRIP_Y_START,
    SCOREBOARD_STRIP_SEARCH_FRAMES,
    SCOREBOARD_ROI_PADDING,
    SCOREBOARD_OCR_MIN_CONFIDENCE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def calibrate_scoreboard_overlay(
    video_path: str,
    override_roi: Optional[tuple[int, int, int, int]] = None,
    debug_ctx: Optional[DebugContext] = None,
) -> Optional[dict]:
    """
    Auto-detect (or accept a manual override for) the scoreboard overlay ROI.

    Args:
        video_path:   Path to the source video.
        override_roi: (x, y, w, h) — skips auto-detection when provided.
        debug_ctx:    DebugContext rooted at runs/scoreboard_overlay/.

    Returns:
        {"x", "y", "w", "h", "frame_dims": [W, H]} or None on failure.
    """
    ctx = debug_ctx or DebugContext.disabled()

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

    # Skip first/last 5 % (walkout / post-fight graphics differ from in-fight)
    skip    = max(1, int(total * 0.05))
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

    cap.release()

    if ctx.verbose:
        with open(cal.path("calibration_log.txt"), "w", encoding="utf-8") as f:
            f.write(f"Strip y_start={strip_y}  frames_sampled={n}\n\n")
            f.write("\n".join(log_lines))

    ctx.log("calibration",
            f"Collected {len(timer_boxes)} timer boxes  "
            f"{len(round_boxes)} round boxes across {n} frames")

    if not timer_boxes:
        ctx.log("calibration",
                "ERROR: no timer pattern found in bottom strip across any sampled frame. "
                "Check calibration_debug/strip_frame_*.jpg to see what EasyOCR found. "
                "Possible causes: overlay absent, font unrecognised, EasyOCR on CPU (too slow).")
        return None

    # --- Union all timer + round boxes → ROI ---
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

    # --- Validate: re-OCR the candidate ROI on a few frames ---
    validate_indices = indices[:5]
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
        results = reader.readtext(crop)
        text = " ".join(t for (_, t, c) in results if c >= SCOREBOARD_OCR_MIN_CONFIDENCE)
        if parse_timer(text) is not None:
            matches += 1
    cap.release()

    match_rate = matches / len(validate_indices) if validate_indices else 0.0
    ctx.log("calibration",
            f"Validation: timer found in {matches}/{len(validate_indices)} frames "
            f"({match_rate:.0%})")

    if match_rate < 0.2:
        ctx.log("calibration",
                f"ERROR: validation failed (match rate {match_rate:.0%} < 20%). "
                "The union ROI does not reliably produce a timer. "
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
