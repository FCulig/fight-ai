"""
Sample frames from a video, OCR the scoreboard overlay ROI, and smooth results.

Samples at SCOREBOARD_OCR_SAMPLE_RATE_HZ (default 2 fps).
Each sample is cropped, upscaled, thresholded, then run through PaddleOCR.
Two smoothing passes follow:
  1. Round number: sliding-window mode
  2. Timer: per-round monotonicity enforcement
"""

import json
import statistics
from pathlib import Path
from typing import Optional

import cv2
import easyocr
import numpy as np

from .parsers import parse_round, parse_timer
from .debug import save_crop_pair, plot_timer_series
from debug import DebugContext
from models.constants import (
    SCOREBOARD_OCR_SAMPLE_RATE_HZ,
    SCOREBOARD_OCR_MIN_CONFIDENCE,
    SCOREBOARD_OCR_UPSCALE,
    SCOREBOARD_SMOOTHING_WINDOW,
    SCOREBOARD_TIMER_MAX_BACKWARD_JUMP,
    SCOREBOARD_DEBUG_CROP_INTERVAL,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_scoreboard_samples(
    video_path: str,
    roi: dict,
    debug_ctx: Optional[DebugContext] = None,
) -> list[dict]:
    """
    OCR the scoreboard overlay across the video and return smoothed samples.

    Each sample is a dict:
        {
          "frame":             int,
          "round_num":         int | None,
          "seconds_remaining": int | None,
          "conf":              float,
          "raw_text":          str,
          "parse_error":       str | None,   # None when fully parsed
        }

    Outputs written to debug_ctx root:
        samples_raw.json        — pre-smoothing
        samples.json            — post-smoothing (canonical)
        timer_plot.png
        sample_debug/           — crop images every SCOREBOARD_DEBUG_CROP_INTERVAL samples
    """
    ctx        = debug_ctx or DebugContext.disabled()
    sample_ctx = ctx.subdir("sample_debug")

    ctx.log("extraction", f"Opening {video_path}  ROI={roi}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        ctx.log("extraction", "ERROR: cannot open video")
        return []

    fps    = cap.get(cv2.CAP_PROP_FPS)
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    stride = max(1, int(round(fps / SCOREBOARD_OCR_SAMPLE_RATE_HZ)))
    ctx.log("extraction",
            f"fps={fps:.1f}  stride={stride}  "
            f"effective_rate={fps/stride:.2f} samp/s  total_frames={total}")

    reader = easyocr.Reader(["en"], gpu=True, verbose=False)
    raw_samples: list[dict] = []
    sample_idx  = 0
    frame_num   = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_num += 1

        if frame_num % stride != 0:
            continue

        # --- Crop & pre-process ---
        x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
        crop = frame[y:y+h, x:x+w]
        if crop.size == 0:
            ctx.log("extraction", f"frame={frame_num:08d} SKIP: empty crop")
            continue

        upscaled = cv2.resize(
            crop,
            (w * SCOREBOARD_OCR_UPSCALE, h * SCOREBOARD_OCR_UPSCALE),
            interpolation=cv2.INTER_CUBIC,
        )
        gray         = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
        preprocessed = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Debug crops at interval
        if ctx.verbose and sample_idx % SCOREBOARD_DEBUG_CROP_INTERVAL == 0:
            prefix = sample_ctx.path(f"frame_{frame_num:08d}")
            save_crop_pair(crop, preprocessed, prefix)

        # --- OCR — use colour upscaled image for best results ---
        result   = reader.readtext(upscaled)
        raw_text = ""
        conf     = 0.0
        if result:
            lines    = [(t, float(c)) for (_bbox, t, c) in result]
            conf     = float(np.mean([c for _, c in lines])) if lines else 0.0
            raw_text = " ".join(t for t, c in lines if c >= SCOREBOARD_OCR_MIN_CONFIDENCE)

        # --- Parse ---
        round_num         = None
        seconds_remaining = None
        parse_error       = None

        if conf >= SCOREBOARD_OCR_MIN_CONFIDENCE or raw_text:
            round_num         = parse_round(raw_text)
            seconds_remaining = parse_timer(raw_text)
            if   round_num is None and seconds_remaining is None:
                parse_error = "no_match"
            elif round_num is None:
                parse_error = "round_not_found"
            elif seconds_remaining is None:
                parse_error = "timer_not_found"
        else:
            parse_error = "low_confidence"

        entry = {
            "frame":             frame_num,
            "round_num":         round_num,
            "seconds_remaining": seconds_remaining,
            "conf":              round(conf, 3),
            "raw_text":          raw_text,
            "parse_error":       parse_error,
        }
        raw_samples.append(entry)

        # Per-sample log line
        if parse_error:
            ctx.log("extraction",
                    f"frame={frame_num:08d}  error={parse_error}  "
                    f"conf={conf:.2f}  raw={raw_text!r}")
        else:
            ctx.log("extraction",
                    f"frame={frame_num:08d}  R={round_num}  "
                    f"timer={seconds_remaining}s  conf={conf:.2f}  raw={raw_text!r}")

        sample_idx += 1

    cap.release()
    ctx.log("extraction", f"Collected {len(raw_samples)} raw samples")
    ctx.save_json("samples_raw.json", raw_samples)

    # --- Smooth ---
    smoothed = _smooth_samples(raw_samples, ctx)
    ctx.save_json("samples.json", smoothed)

    # --- Timer plot ---
    plot_timer_series(
        smoothed,
        ctx.path("timer_plot.png") if ctx.verbose else None,
    )
    if ctx.verbose:
        ctx.log("extraction", f"Timer plot → {ctx.path('timer_plot.png')}")

    return smoothed


# ---------------------------------------------------------------------------
# Smoothing
# ---------------------------------------------------------------------------

def _smooth_samples(samples: list[dict], ctx: DebugContext) -> list[dict]:
    """
    Pass 1: round-number mode over a sliding window.
    Pass 2: per-round timer monotonicity (direction auto-detected).
    """
    if not samples:
        return []

    result = [dict(s) for s in samples]
    W      = SCOREBOARD_SMOOTHING_WINDOW

    # --- Pass 1: round mode ---
    for i in range(len(result)):
        lo = max(0, i - W // 2)
        hi = min(len(result), i + W // 2 + 1)
        window_rounds = [result[j]["round_num"] for j in range(lo, hi)
                         if result[j]["round_num"] is not None]
        if not window_rounds:
            continue
        mode = statistics.mode(window_rounds)
        if result[i]["round_num"] != mode:
            ctx.log("smoothing",
                    f"frame={result[i]['frame']}  "
                    f"round corrected {result[i]['round_num']} → {mode}")
            result[i]["round_num"] = mode

    # --- Pass 2: timer monotonicity per round ---
    all_rounds = {s["round_num"] for s in result if s["round_num"] is not None}
    for rnum in all_rounds:
        round_entries = [
            (i, s) for i, s in enumerate(result)
            if s["round_num"] == rnum and s["seconds_remaining"] is not None
        ]
        if len(round_entries) < 2:
            continue

        timers = [s["seconds_remaining"] for _, s in round_entries]
        n_dec  = sum(1 for a, b in zip(timers, timers[1:]) if a > b)
        n_inc  = sum(1 for a, b in zip(timers, timers[1:]) if a < b)
        direction = "down" if n_dec >= n_inc else "up"
        ctx.log("smoothing",
                f"Round {rnum}: timer direction={direction}  "
                f"({n_dec} dec, {n_inc} inc)")

        last_valid: Optional[int] = None
        for idx, s in round_entries:
            t = s["seconds_remaining"]
            if last_valid is None:
                last_valid = t
                continue
            bad = (
                (direction == "down" and t > last_valid + SCOREBOARD_TIMER_MAX_BACKWARD_JUMP) or
                (direction == "up"   and t < last_valid - SCOREBOARD_TIMER_MAX_BACKWARD_JUMP)
            )
            if bad:
                ctx.log("smoothing",
                        f"frame={s['frame']}  timer rejected "
                        f"({t}s vs last {last_valid}s, direction={direction})")
                result[idx]["seconds_remaining"] = None
                result[idx]["parse_error"]       = "timer_smoothed_out"
            else:
                last_valid = t

    return result


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def load_samples(path: str) -> list[dict]:
    """Load samples.json; returns empty list on any error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
