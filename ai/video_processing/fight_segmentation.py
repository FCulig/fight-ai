"""
Fight segmentation — splits a full fight video into rounds.

Primary signal: scoreboard overlay OCR (round number + timer).
Fallback signals: YOLO fighter presence + engagement (used when OCR unavailable).

Single streaming pass over the detection JSON; two deque-based sliding-window
state machines (fight-level and round-level) with hysteresis. OCR-derived
round transitions are used to snap boundaries to exact frames.
"""

import bisect
import json
import re
from collections import deque
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from models.constants import (
    LABEL_ID,
    MIN_FIGHT_END_GAP_SECS,
    MIN_ROUND_GAP_SECS,
    MIN_ROUND_LENGTH_SECS,
    MIN_VALID_FRAME_RATIO,
    MIN_FIGHT_DURATION_SECS,
    ROUND_ENGAGEMENT_DISTANCE,
    FIGHT_PRESENCE_WINDOW_SECS,
    FIGHT_ENTER_RATIO,
    FIGHT_EXIT_RATIO,
    ROUND_ENGAGEMENT_WINDOW_SECS,
    ROUND_ENGAGED_RATIO,
    ROUND_DISENGAGED_RATIO,
    FUSION_WEIGHT_OCR,
    FUSION_WEIGHT_DETECTION,
    FUSION_WEIGHT_ENGAGEMENT,
    OCR_BOUNDARY_SNAP_SECS,
)
from debug import DebugContext


def _read_fps(detection_results_file: str) -> float:
    """Read fps from the header of detection_results.json without loading the full file."""
    with open(detection_results_file, "r", encoding="utf-8") as f:
        head = f.read(128)
    m = re.search(r'"fps"\s*:\s*([\d.]+)', head)
    return float(m.group(1)) if m else 50.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def segment_fights(
    detection_results_file: str,
    scoreboard_samples_file: Optional[str] = None,
    debug_ctx: Optional[DebugContext] = None,
) -> dict:
    """
    Segment a full fight video into rounds.

    Args:
        detection_results_file:  Path to runs/detection_results.json.
        scoreboard_samples_file: Path to runs/scoreboard_overlay/samples.json
                                 (optional; falls back to detection-only when absent).
        debug_ctx:               DebugContext for debug output.

    Returns:
        {
          "rounds":  [(start_frame, end_frame), ...],
          "quality": {"is_valid": bool, "reason": str, "metrics": {...}}
        }
    """
    ctx = debug_ctx or DebugContext.disabled()

    # Read fps and derive frame counts from seconds-based constants
    fps = _read_fps(detection_results_file)
    ctx.log("segmentation", f"Video fps: {fps:.2f}")

    min_round_length_frames  = int(MIN_ROUND_LENGTH_SECS  * fps)
    min_fight_duration_frames = int(MIN_FIGHT_DURATION_SECS * fps)

    # Load OCR samples
    ocr_samples: list[dict] = []
    if scoreboard_samples_file:
        try:
            with open(scoreboard_samples_file, "r", encoding="utf-8") as f:
                ocr_samples = json.load(f)
            ctx.log("segmentation", f"Loaded {len(ocr_samples)} OCR samples")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            ctx.log("segmentation", f"WARNING: could not load OCR samples — {e}")

    ocr_index  = _build_ocr_index(ocr_samples)
    ocr_bounds = _extract_ocr_boundaries(ocr_samples)   # hard round-transition frames

    ctx.log("segmentation",
            f"OCR index: {len(ocr_index)} entries  "
            f"hard boundaries: {len(ocr_bounds)}")

    rounds, total_frames, valid_frames, debug_series = _segment_streaming(
        detection_results_file, ocr_index, ctx, fps
    )

    # Snap boundaries to nearest OCR round transition
    rounds = _snap_to_ocr_boundaries(rounds, ocr_bounds, ctx, fps)

    # Quality metrics
    total_fight_duration = sum(e - s + 1 for s, e in rounds)
    valid_ratio          = valid_frames / total_frames if total_frames > 0 else 0.0
    round_count          = len(rounds)

    metrics = {
        "total_frames":               total_frames,
        "valid_frame_ratio":          valid_ratio,
        "round_count":                round_count,
        "total_fight_duration_frames": total_fight_duration,
        "total_fight_duration_secs":  total_fight_duration / fps if fps > 0 else 0,
        "ocr_samples_used":           len(ocr_samples),
        "fps":                        fps,
    }

    is_valid = (
        valid_ratio >= MIN_VALID_FRAME_RATIO and
        total_fight_duration >= min_fight_duration_frames and
        round_count > 0
    )

    reason = ""
    if not is_valid:
        if round_count == 0:
            reason = "No valid fight segments found" if total_frames > 0 else "Empty video"
        elif valid_ratio < MIN_VALID_FRAME_RATIO:
            reason = (f"Valid frame ratio too low: "
                      f"{valid_ratio:.2f} < {MIN_VALID_FRAME_RATIO}")
        elif total_fight_duration < min_fight_duration_frames:
            reason = (f"Fight duration too short: "
                      f"{total_fight_duration/fps:.1f}s < {MIN_FIGHT_DURATION_SECS}s")

    ctx.log("segmentation",
            f"Result: {round_count} round(s)  valid={is_valid}  {reason or 'OK'}")

    # Debug outputs
    _save_debug_outputs(debug_series, rounds, ctx)

    return {
        "rounds":  rounds,
        "quality": {"is_valid": is_valid, "reason": reason, "metrics": metrics},
    }


# ---------------------------------------------------------------------------
# OCR index helpers
# ---------------------------------------------------------------------------

def _build_ocr_index(samples: list[dict]) -> dict[int, dict]:
    """Map frame_num → sample for O(1) lookup. Sorted frames for bisect."""
    return {s["frame"]: s for s in samples}


def _extract_ocr_boundaries(samples: list[dict]) -> list[int]:
    """
    Return frames where the round number changes in the smoothed sample list.
    These are used later to snap detected round edges.
    """
    boundaries: list[int] = []
    prev_round: Optional[int] = None
    for s in samples:
        r = s.get("round_num")
        if r is not None and prev_round is not None and r != prev_round:
            boundaries.append(s["frame"])
        if r is not None:
            prev_round = r
    return boundaries


def _ocr_signal_at(frame_num: int, ocr_index: dict[int, dict], stride: int) -> float:
    """
    Return OCR in-round probability [0.0, 1.0] for *frame_num*.

    1.0  — sample within half a stride, valid round + timer
    0.6  — sample within half a stride, valid round only
    0.0  — low confidence
    -1.0 — no nearby sample (caller should fall back to detection signal)
    """
    if not ocr_index:
        return -1.0

    # Find nearest sample frame by key proximity
    frames = sorted(ocr_index.keys())
    idx    = bisect.bisect_left(frames, frame_num)

    nearest: Optional[dict] = None
    best_dist = stride         # only consider samples within one stride
    for cand_idx in [idx - 1, idx]:
        if 0 <= cand_idx < len(frames):
            dist = abs(frames[cand_idx] - frame_num)
            if dist < best_dist:
                best_dist = dist
                nearest   = ocr_index[frames[cand_idx]]

    if nearest is None:
        return -1.0

    err = nearest.get("parse_error")
    if err == "low_confidence":
        return 0.0
    if nearest.get("round_num") is None:
        return -1.0
    if nearest.get("seconds_remaining") is not None:
        return 1.0
    return 0.6   # round found, timer missing


# ---------------------------------------------------------------------------
# Streaming segmenter
# ---------------------------------------------------------------------------

def _segment_streaming(
    detection_results_file: str,
    ocr_index: dict[int, dict],
    ctx: DebugContext,
    fps: float,
) -> tuple[list[tuple[int, int]], int, int, list[dict]]:
    """
    One-pass streaming segmenter.

    Returns (rounds, total_frames, valid_frames, debug_series).
    debug_series is a list of per-sampled-frame dicts for plotting.
    """
    # Convert seconds-based constants to frames using detected fps
    min_fight_end_gap    = int(MIN_FIGHT_END_GAP_SECS    * fps)
    min_round_gap        = int(MIN_ROUND_GAP_SECS        * fps)
    presence_window_sz   = int(FIGHT_PRESENCE_WINDOW_SECS  * fps)
    engagement_window_sz = int(ROUND_ENGAGEMENT_WINDOW_SECS * fps)
    debug_sample_interval = max(1, int(0.5 * fps))  # debug point every 0.5 s

    # Estimate OCR stride for signal lookup
    frames_list = sorted(ocr_index.keys())
    ocr_stride  = (
        int(np.median(np.diff(frames_list))) if len(frames_list) >= 2 else int(fps // 2)
    )

    presence_window  = deque()
    presence_sum     = 0
    engagement_window = deque()
    engagement_sum   = 0

    total_frames = 0
    valid_frames = 0

    in_fight          = False
    fight_start       = None
    fight_exit_cand   = None
    fight_exit_streak = 0

    in_round           = False
    round_start        = None
    break_cand         = None
    break_streak       = 0

    rounds:       list[tuple[int, int]] = []
    last_frame    = None
    debug_series: list[dict] = []

    for frame in _iter_detection_frames(detection_results_file):
        frame_num  = frame["frame"]
        last_frame = frame_num
        total_frames += 1

        both_present, engaged = _frame_signals(frame["detections"])
        if both_present:
            valid_frames += 1

        # --- OCR signal ---
        ocr_sig = _ocr_signal_at(frame_num, ocr_index, ocr_stride)

        # --- Fused in-round probability ---
        det_sig = 1.0 if both_present else 0.0
        eng_sig = 1.0 if engaged      else 0.0

        if ocr_sig >= 0:                          # OCR available
            prob = (FUSION_WEIGHT_OCR        * ocr_sig +
                    FUSION_WEIGHT_DETECTION  * det_sig +
                    FUSION_WEIGHT_ENGAGEMENT * eng_sig)
        else:                                     # OCR absent — redistribute
            det_w = FUSION_WEIGHT_DETECTION  / (FUSION_WEIGHT_DETECTION + FUSION_WEIGHT_ENGAGEMENT)
            eng_w = FUSION_WEIGHT_ENGAGEMENT / (FUSION_WEIGHT_DETECTION + FUSION_WEIGHT_ENGAGEMENT)
            prob  = det_w * det_sig + eng_w * eng_sig

        # Debug series (one sample every ~0.5 s)
        if total_frames % debug_sample_interval == 0:
            nearest_sample = (
                ocr_index.get(min(frames_list, key=lambda f: abs(f - frame_num)))
                if frames_list else None
            )
            debug_series.append({
                "frame":        frame_num,
                "both_present": both_present,
                "engaged":      engaged,
                "ocr_signal":   ocr_sig,
                "fused_prob":   round(prob, 3),
                "in_fight":     in_fight,
                "in_round":     in_round,
                "ocr_round":    nearest_sample.get("round_num")    if nearest_sample else None,
                "ocr_timer":    nearest_sample.get("seconds_remaining") if nearest_sample else None,
            })

        # --- Update fight presence window ---
        presence_window.append(prob >= 0.5)
        presence_sum += int(prob >= 0.5)
        if len(presence_window) > presence_window_sz:
            presence_sum -= int(presence_window.popleft())
        presence_ratio = presence_sum / len(presence_window)

        # ---- Fight state machine ----
        if not in_fight:
            if (len(presence_window) >= presence_window_sz and
                    presence_ratio >= FIGHT_ENTER_RATIO):
                in_fight         = True
                fight_start      = frame_num - len(presence_window) + 1
                fight_exit_cand  = None
                fight_exit_streak = 0
                in_round         = True
                round_start      = fight_start
                break_cand       = None
                break_streak     = 0
                engagement_window.clear()
                engagement_sum   = 0
                ctx.log("segmentation",
                        f"frame={frame_num}  FIGHT START (back-dated to {fight_start})")
        else:
            if presence_ratio <= FIGHT_EXIT_RATIO:
                if fight_exit_cand is None:
                    fight_exit_cand = frame_num
                fight_exit_streak += 1
            else:
                fight_exit_cand   = None
                fight_exit_streak = 0

            if fight_exit_streak >= min_fight_end_gap:
                fight_end = fight_exit_cand
                if in_round and round_start is not None and fight_end >= round_start:
                    rounds.append((round_start, fight_end))
                    ctx.log("segmentation",
                            f"frame={frame_num}  ROUND END (fight end): "
                            f"{round_start}–{fight_end}")
                in_fight = False
                fight_start = fight_exit_cand = None
                fight_exit_streak = 0
                in_round = False
                round_start = break_cand = None
                break_streak = 0
                engagement_window.clear()
                engagement_sum = 0
                ctx.log("segmentation", f"frame={frame_num}  FIGHT END")
                continue

        if not in_fight:
            continue

        # ---- Round state machine ----
        engagement_window.append(prob >= 0.5)
        engagement_sum += int(prob >= 0.5)
        if len(engagement_window) > engagement_window_sz:
            engagement_sum -= int(engagement_window.popleft())
        eng_ratio = (engagement_sum / len(engagement_window)
                     if engagement_window else 0.0)

        if in_round:
            if eng_ratio <= ROUND_DISENGAGED_RATIO:
                if break_cand is None:
                    break_cand = frame_num
                break_streak += 1
            else:
                break_cand   = None
                break_streak = 0

            if break_streak >= min_round_gap:
                round_end = break_cand
                if round_start is not None and round_end >= round_start:
                    rounds.append((round_start, round_end))
                    ctx.log("segmentation",
                            f"frame={frame_num}  ROUND SPLIT: {round_start}–{round_end}")
                in_round     = False
                round_start  = None
                break_cand   = None
                break_streak = 0
        else:
            if (len(engagement_window) >= engagement_window_sz and
                    eng_ratio >= ROUND_ENGAGED_RATIO):
                in_round    = True
                round_start = frame_num - len(engagement_window) + 1
                break_cand  = None
                break_streak = 0
                ctx.log("segmentation",
                        f"frame={frame_num}  ROUND START (back-dated to {round_start})")

    # End of stream
    if in_fight and last_frame is not None:
        if in_round and round_start is not None and last_frame >= round_start:
            rounds.append((round_start, last_frame))
            ctx.log("segmentation",
                    f"End of stream: closed final round {round_start}–{last_frame}")

    min_round_len = int(MIN_ROUND_LENGTH_SECS * fps)
    rounds = [(s, e) for s, e in rounds if e - s + 1 >= min_round_len]
    return rounds, total_frames, valid_frames, debug_series


# ---------------------------------------------------------------------------
# OCR boundary snapping
# ---------------------------------------------------------------------------

def _snap_to_ocr_boundaries(
    rounds: list[tuple[int, int]],
    ocr_bounds: list[int],
    ctx: DebugContext,
    fps: float,
) -> list[tuple[int, int]]:
    """
    For each detected round boundary, snap to the nearest OCR-derived
    round-transition frame if within OCR_BOUNDARY_SNAP_SECS.
    """
    if not ocr_bounds or not rounds:
        return rounds

    snap_frames = int(OCR_BOUNDARY_SNAP_SECS * fps)
    snapped: list[tuple[int, int]] = []

    for i, (start, end) in enumerate(rounds):
        new_start = start
        new_end   = end

        if i > 0:
            nearest = min(ocr_bounds, key=lambda b: abs(b - start))
            if abs(nearest - start) <= snap_frames:
                ctx.log("segmentation",
                        f"Snap round {i+1} start {start} → {nearest} (OCR transition)")
                new_start = nearest

        nearest_end = min(ocr_bounds, key=lambda b: abs(b - end))
        if abs(nearest_end - end) <= snap_frames:
            ctx.log("segmentation",
                    f"Snap round {i+1} end {end} → {nearest_end} (OCR transition)")
            new_end = nearest_end

        if new_end > new_start:
            snapped.append((new_start, new_end))
        else:
            snapped.append((start, end))

    return snapped


# ---------------------------------------------------------------------------
# Per-frame signal helpers
# ---------------------------------------------------------------------------

def _frame_signals(detections: list[dict]) -> tuple[bool, bool]:
    """Return (both_present, engaged) for one frame's detections."""
    red_bbox  = None
    blue_bbox = None
    for d in detections:
        cls = d.get("class_id")
        if cls == LABEL_ID["fighter_red"]  and red_bbox  is None:
            red_bbox  = d["bbox_xyxy"]
        elif cls == LABEL_ID["fighter_blue"] and blue_bbox is None:
            blue_bbox = d["bbox_xyxy"]

    both_present = red_bbox is not None and blue_bbox is not None
    if not both_present:
        return False, False

    red_cx  = (red_bbox[0]  + red_bbox[2])  / 2
    blue_cx = (blue_bbox[0] + blue_bbox[2]) / 2
    engaged = abs(red_cx - blue_cx) < ROUND_ENGAGEMENT_DISTANCE
    return True, engaged


def _iter_detection_frames(detection_results_file: str):
    """Stream frames from {"frames":[...]} JSON without loading the whole file."""
    with open(detection_results_file, "r", encoding="utf-8") as f:
        data = json.loads(f.read())
    for frame in data["frames"]:
        yield frame


# ---------------------------------------------------------------------------
# Debug output writers
# ---------------------------------------------------------------------------

def _save_debug_outputs(
    debug_series: list[dict],
    rounds: list[tuple[int, int]],
    ctx: DebugContext,
) -> None:
    if not ctx.verbose or not debug_series:
        return

    seg_ctx = ctx.subdir("segmentation_debug")

    # CSV
    csv_path = seg_ctx.path("signal_series.csv")
    header   = "frame,both_present,engaged,ocr_signal,fused_prob,in_fight,in_round,ocr_round,ocr_timer"
    rows     = [
        ",".join(str(s.get(k, "")) for k in
                 ["frame","both_present","engaged","ocr_signal","fused_prob",
                  "in_fight","in_round","ocr_round","ocr_timer"])
        for s in debug_series
    ]
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(header + "\n" + "\n".join(rows))
    ctx.log("segmentation", f"Signal series CSV → {csv_path}")

    # Timeline plot
    _plot_timeline(debug_series, rounds,
                   seg_ctx.path("timeline.png"))
    ctx.log("segmentation", f"Timeline plot → {seg_ctx.path('timeline.png')}")


def _plot_timeline(
    series: list[dict],
    rounds: list[tuple[int, int]],
    path: Path,
) -> None:
    frames    = [s["frame"]       for s in series]
    fused     = [s["fused_prob"]  for s in series]
    ocr_sigs  = [s["ocr_signal"]  for s in series]
    det_sigs  = [1.0 if s["both_present"] else 0.0 for s in series]
    ocr_rounds = [s.get("ocr_round") for s in series]

    fig, axes = plt.subplots(3, 1, figsize=(18, 10), sharex=True)
    fig.suptitle("Fight segmentation — signal series", fontsize=13)

    # Panel 1 — fused probability + round bands
    ax = axes[0]
    ax.set_ylabel("Fused in-round prob")
    ax.set_ylim(-0.05, 1.1)
    ax.plot(frames, fused, color="steelblue", linewidth=0.8, label="fused prob")
    ax.axhline(0.5, color="grey", linestyle="--", linewidth=0.6)
    palette = plt.cm.tab10([0, 1, 2, 3, 4])
    for i, (s, e) in enumerate(rounds):
        ax.axvspan(s, e, alpha=0.15, color=palette[i % 5],
                   label=f"Round {i+1} ({s}–{e})")
    ax.legend(fontsize=7, loc="upper right")

    # Panel 2 — individual signals
    ax2 = axes[1]
    ax2.set_ylabel("Individual signals")
    ax2.set_ylim(-0.1, 1.2)
    ax2.plot(frames, det_sigs, color="orange", linewidth=0.6,
             alpha=0.7, label="detection (both present)")
    ocr_valid = [s if s >= 0 else None for s in ocr_sigs]
    ax2.plot(frames, [s if s is not None else 0 for s in ocr_valid],
             color="green", linewidth=0.8, alpha=0.8, label="OCR signal")
    ax2.legend(fontsize=7)

    # Panel 3 — OCR round number
    ax3 = axes[2]
    ax3.set_ylabel("OCR round")
    ax3.set_xlabel("Frame number")
    ax3.set_yticks([1, 2, 3, 4, 5])
    ax3.set_ylim(0.5, 5.5)
    valid_r = [(f, r) for f, r in zip(frames, ocr_rounds) if r is not None]
    if valid_r:
        fs, rs = zip(*valid_r)
        ax3.scatter(fs, rs, c="purple", s=8, zorder=5)

    plt.tight_layout()
    plt.savefig(str(path), dpi=150)
    plt.close(fig)
