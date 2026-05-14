"""
Scoreboard overlay verification video (Extension C).

Reads samples.json + roi.json and renders an annotated MP4 where every
frame shows:
  - A coloured rectangle around the detected ROI
  - A HUD box (top-left) with the nearest parsed round + timer reading
  - OCR confidence as a thin bar under the HUD

Run standalone:
    python -m video_processing.scoreboard_overlay.scoreboard_verification \\
        --video fight.mp4 \\
        --samples runs/scoreboard_overlay/samples.json \\
        --roi    runs/scoreboard_overlay/roi.json \\
        --out    runs/scoreboard_overlay/verification.mp4
"""

import bisect
import json
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def build_verification_video(
    video_path: str,
    samples: list[dict],
    roi: dict,
    output_path: str = "runs/scoreboard_overlay/verification.mp4",
    max_frames: Optional[int] = None,
) -> str:
    """
    Write an annotated copy of *video_path* to *output_path*.

    Args:
        video_path:   Source video.
        samples:      Smoothed samples from extract_scoreboard_samples().
        roi:          ROI dict from calibrate_scoreboard_overlay().
        output_path:  Destination MP4 path.
        max_frames:   Cap output length (useful for quick sanity checks).

    Returns:
        output_path
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    W   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (W, H))

    # Build fast lookup: sorted list of sample frame numbers
    sample_frames = [s["frame"] for s in samples]

    frame_num = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_num += 1
        if max_frames and frame_num > max_frames:
            break

        nearest = _nearest_sample(samples, sample_frames, frame_num)
        frame   = _draw_overlay(frame, roi, nearest, frame_num)
        writer.write(frame)

    cap.release()
    writer.release()
    print(f"Verification video written → {output_path}")
    return output_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nearest_sample(
    samples: list[dict],
    sample_frames: list[int],
    frame_num: int,
) -> Optional[dict]:
    """Return the sample whose frame is closest to *frame_num*."""
    if not samples:
        return None
    idx = bisect.bisect_left(sample_frames, frame_num)
    candidates = []
    if idx < len(samples):
        candidates.append(samples[idx])
    if idx > 0:
        candidates.append(samples[idx - 1])
    return min(candidates, key=lambda s: abs(s["frame"] - frame_num))


def _draw_overlay(
    frame: np.ndarray,
    roi: dict,
    sample: Optional[dict],
    frame_num: int,
) -> np.ndarray:
    """Draw the ROI rect and HUD onto *frame*."""
    out = frame.copy()

    # --- ROI rectangle ---
    rx, ry, rw, rh = roi["x"], roi["y"], roi["w"], roi["h"]
    cv2.rectangle(out, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 2)

    # --- HUD background ---
    hud_x, hud_y, hud_w, hud_h = 10, 10, 300, 90
    overlay = out.copy()
    cv2.rectangle(overlay, (hud_x, hud_y), (hud_x + hud_w, hud_y + hud_h),
                  (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, out, 0.45, 0, out)

    # --- HUD text ---
    tx, ty = hud_x + 8, hud_y + 24
    lh = 22  # line height

    if sample:
        r   = sample.get("round_num")
        sec = sample.get("seconds_remaining")
        c   = sample.get("conf", 0.0)
        err = sample.get("parse_error")

        r_str   = f"R{r}" if r is not None else "R?"
        t_str   = _fmt_timer(sec) if sec is not None else "?:??"
        hud_col = (0, 255, 0) if err is None else (0, 140, 255)

        cv2.putText(out, f"{r_str}  {t_str}", (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, hud_col, 2, cv2.LINE_AA)
        cv2.putText(out, f"conf: {c:.2f}  {err or 'OK'}", (tx, ty + lh),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

        # Confidence bar
        bar_y = hud_y + hud_h - 8
        bar_w = int((hud_w - 16) * min(max(c, 0.0), 1.0))
        bar_col = (0, 200, 0) if c >= 0.7 else (0, 100, 255)
        cv2.rectangle(out, (tx, bar_y - 4), (tx + hud_w - 16, bar_y + 4),
                      (60, 60, 60), -1)
        if bar_w > 0:
            cv2.rectangle(out, (tx, bar_y - 4), (tx + bar_w, bar_y + 4),
                          bar_col, -1)
    else:
        cv2.putText(out, "No OCR data", (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 1)

    # --- Frame counter ---
    cv2.putText(out, f"frame {frame_num}", (tx, ty + 2 * lh),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1, cv2.LINE_AA)

    return out


def _fmt_timer(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    from .extraction import load_samples
    from .calibration import load_roi

    p = argparse.ArgumentParser(description="Render scoreboard verification video")
    p.add_argument("--video",   required=True)
    p.add_argument("--samples", default="runs/scoreboard_overlay/samples.json")
    p.add_argument("--roi",     default="runs/scoreboard_overlay/roi.json")
    p.add_argument("--out",     default="runs/scoreboard_overlay/verification.mp4")
    p.add_argument("--max-frames", type=int, default=None)
    args = p.parse_args()

    _samples = load_samples(args.samples)
    _roi     = load_roi(args.roi)
    if not _samples:
        print(f"ERROR: no samples loaded from {args.samples}")
        raise SystemExit(1)
    if not _roi:
        print(f"ERROR: no ROI loaded from {args.roi}")
        raise SystemExit(1)

    build_verification_video(args.video, _samples, _roi, args.out, args.max_frames)
