"""
Fight segmentation — splits a full fight video into rounds.

Three signals, in descending order of authority:

1. **Scoreboard clock** (`round_clock.derive_rounds_from_clock`) — deterministic
   and therefore authoritative for the round *count* and *identity*. See that
   module for why the fit is robust from only a handful of readings.
2. **Scoreboard round number** — corroborates the clock and pins boundaries, but
   many overlays never render a parseable one, so nothing may depend on it.
3. **YOLO fighter presence + engagement** — a single streaming pass with two
   deque-based sliding-window state machines (fight-level and round-level) with
   hysteresis. Used to refine edges the clock could not pin, and as the sole
   signal when OCR is unavailable entirely.

Detection alone cannot decide a round count: it splits on any sustained loss of
"both fighters visible and close together", which a ground scramble or a camera
cutaway produces routinely. When it is the only signal available,
`enforce_round_plausibility` applies physical constraints on what a round list
can look like, and the result is flagged for human review rather than silently
committed.
"""

import bisect
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
    ROUND_ENGAGEMENT_RATIO,
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
    MIN_REPLAY_SAMPLES,
    MIN_ROUND_NUMBER_RUN_SAMPLES,
    MIN_INTERIOR_ROUND_SECS,
    MIN_ROUND_BREAK_SECS,
    ROUND_CLOCK_HEALTHY_SUPPORT,
)
from video_processing.round_clock import derive_rounds_from_clock
from debug import DebugContext


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def segment_fights(
    detection_data: dict,
    fps: float,
    width: float,
    scoreboard_samples: Optional[list[dict]] = None,
    debug_ctx: Optional[DebugContext] = None,
) -> dict:
    """
    Segment a full fight video into rounds.

    Args:
        detection_data:     In-memory detection dict produced by process_video()
                            (or loaded from a --detection-file dev override).
        fps:                Frames per second, taken from the fights DB row.
        width:              Video frame width in pixels, taken from the fights
                            DB row — engagement distance is scored as a
                            fraction of this rather than an absolute pixel
                            count, so it isn't tied to one resolution/crop.
        scoreboard_samples: In-memory OCR samples list produced by
                            extract_scoreboard_samples() (optional; falls back
                            to detection-only segmentation when absent).
        debug_ctx:          DebugContext for debug output.

    Returns:
        {
          "rounds":          [(start_frame, end_frame), ...],
          "excluded_ranges": [(start_frame, end_frame), ...],  # replays — see detect_replay_ranges()
          "quality":         {"is_valid": bool, "reason": str, "metrics": {...}}
        }
    """
    ctx = debug_ctx or DebugContext.disabled()
    ctx.log("segmentation", f"Video fps: {fps:.2f}")

    min_fight_duration_frames = int(MIN_FIGHT_DURATION_SECS * fps)

    ocr_samples: list[dict] = scoreboard_samples or []
    if ocr_samples:
        ctx.log("segmentation", f"Loaded {len(ocr_samples)} OCR samples")

    ocr_index  = _build_ocr_index(ocr_samples)
    ocr_bounds = _extract_ocr_boundaries(ocr_samples)   # hard round-transition frames
    excluded_ranges = detect_replay_ranges(ocr_samples)

    ctx.log("segmentation",
            f"OCR index: {len(ocr_index)} entries  "
            f"hard boundaries: {len(ocr_bounds)}  "
            f"replay ranges: {len(excluded_ranges)}")

    rounds, total_frames, valid_frames, debug_series = _segment_streaming(
        detection_data, ocr_index, ctx, fps, width
    )

    # Snap boundaries to nearest OCR round transition
    rounds = _snap_to_ocr_boundaries(rounds, ocr_bounds, ctx, fps)

    # Detection alone cannot be trusted with a round count, so clean the list to
    # what a real fight could have produced before the clock gets a say.
    rounds = enforce_round_plausibility(rounds, fps, total_frames, ctx)

    # The clock is deterministic — where it fits, it decides how many rounds
    # there are and detection is demoted to refining the edges it could not pin.
    clock_rounds, clock_diag = derive_rounds_from_clock(
        ocr_samples, fps, total_frames, ctx
    )
    rounds, segmentation_source = _reconcile_with_clock(
        rounds, clock_rounds, total_frames, ctx
    )

    # Quality metrics
    total_fight_duration = sum(e - s + 1 for s, e in rounds)
    valid_ratio          = valid_frames / total_frames if total_frames > 0 else 0.0
    round_count          = len(rounds)

    n_samples          = len(ocr_samples)
    ocr_timer_coverage = (clock_diag["timer_readings"] / n_samples) if n_samples else 0.0
    # Round numbers are mode-smoothed across a sliding window, so a sample can
    # carry one that OCR never actually read. Samples where OCR read nothing at
    # all ("low_confidence") are excluded, or this reports the smoother's output
    # rather than the overlay's.
    genuine_rounds = sum(
        1 for s in ocr_samples
        if s.get("round_num") is not None and s.get("parse_error") != "low_confidence"
    )
    ocr_round_coverage = (genuine_rounds / n_samples) if n_samples else 0.0

    metrics = {
        "total_frames":               total_frames,
        "valid_frame_ratio":          valid_ratio,
        "round_count":                round_count,
        "total_fight_duration_frames": total_fight_duration,
        "total_fight_duration_secs":  total_fight_duration / fps if fps > 0 else 0,
        "ocr_samples_used":           n_samples,
        "ocr_timer_coverage":         round(ocr_timer_coverage, 3),
        "ocr_round_coverage":         round(ocr_round_coverage, 3),
        "clock_rounds_found":         len(clock_rounds),
        "segmentation_source":        segmentation_source,
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

    # A round list that no signal actually corroborated is the failure mode that
    # reaches the database looking exactly like a good one, so say so explicitly
    # rather than leaving it to be noticed by eye.
    needs_review, review_reason = _review_verdict(
        segmentation_source, clock_rounds, ocr_timer_coverage, is_valid
    )
    metrics["needs_review"]  = needs_review
    metrics["review_reason"] = review_reason

    ctx.log("segmentation",
            f"Result: {round_count} round(s)  source={segmentation_source}  "
            f"valid={is_valid}  needs_review={needs_review}  "
            f"{review_reason or reason or 'OK'}")

    # Debug outputs
    _save_debug_outputs(debug_series, rounds, ctx)

    return {
        "rounds":          rounds,
        "excluded_ranges": excluded_ranges,
        "quality":         {
            "is_valid":      is_valid,
            "reason":        reason,
            "needs_review":  needs_review,
            "review_reason": review_reason,
            "metrics":       metrics,
        },
    }


def _review_verdict(
    source: str,
    clock_rounds: list,
    timer_coverage: float,
    is_valid: bool,
) -> tuple[bool, str]:
    """
    Whether a human should confirm the round list before it is trusted.

    Keyed on how well each round is *supported*, not on raw sample coverage. A
    scoreboard visible for only 8% of a fight still pins its rounds exactly when
    every one of those readings agrees on a single intercept — coverage measures
    how often the overlay was on screen, which is a property of the broadcast,
    not of how much the answer can be trusted.
    """
    if not is_valid:
        return True, "Segmentation quality gate failed"

    if source != "clock":
        return True, (
            "Round count came from fighter detection alone — the scoreboard "
            f"clock could not be fitted (timer read on {timer_coverage:.0%} of "
            "samples). Detection splits a round at any long camera cutaway, so "
            "the boundaries below are a guess."
        )

    thin = [r for r in clock_rounds if r.support < ROUND_CLOCK_HEALTHY_SUPPORT]
    if thin:
        worst = min(r.support for r in thin)
        return True, (
            f"{len(thin)} of {len(clock_rounds)} round(s) rest on fewer than "
            f"{ROUND_CLOCK_HEALTHY_SUPPORT} scoreboard readings (thinnest: "
            f"{worst}) — the clock fit is under-determined"
        )

    return False, ""


# ---------------------------------------------------------------------------
# OCR index helpers
# ---------------------------------------------------------------------------

def _build_ocr_index(samples: list[dict]) -> dict[int, dict]:
    """Map frame_num → sample for O(1) lookup. Sorted frames for bisect."""
    return {s["frame"]: s for s in samples}


def _extract_ocr_boundaries(samples: list[dict]) -> list[int]:
    """
    Return frames where the round number demonstrably *increments*.
    These are used later to snap detected round edges.

    Any change used to count, which let OCR flapping manufacture boundaries: one
    misread "R2" in the middle of round 1 produced a false transition, and the
    following correct "R1" produced a second one. Round numbers only ever go up,
    and never skip, so a transition is only accepted when the new value is
    exactly one higher than the established one *and* holds for
    MIN_ROUND_NUMBER_RUN_SAMPLES consecutive readings.
    """
    numbered = [s for s in samples if s.get("round_num") is not None]
    boundaries: list[int] = []
    if len(numbered) <= MIN_ROUND_NUMBER_RUN_SAMPLES:
        return boundaries

    established = numbered[0]["round_num"]
    i = 1
    while i < len(numbered):
        candidate = numbered[i]["round_num"]
        if candidate == established + 1:
            run = 1
            j   = i + 1
            while (j < len(numbered)
                   and run < MIN_ROUND_NUMBER_RUN_SAMPLES
                   and numbered[j]["round_num"] == candidate):
                run += 1
                j   += 1
            if run >= MIN_ROUND_NUMBER_RUN_SAMPLES:
                boundaries.append(numbered[i]["frame"])
                established = candidate
                i = j
                continue
        i += 1

    return boundaries


def detect_replay_ranges(samples: list[dict]) -> list[tuple[int, int]]:
    """Frame ranges where the on-screen round timer just jumped backward or
    off its established trend — evidence of a slow-motion replay, where
    velocity-based strike detection is meaningless (plan Stage 1 step 3).

    `_smooth_samples()` (scoreboard_overlay/extraction.py) already runs this
    exact check per-sample to decide what to reject as OCR noise during timer
    smoothing, tagging each rejected sample `parse_error = "timer_smoothed_out"`
    — this reuses that existing signal rather than re-deriving it, requiring
    MIN_REPLAY_SAMPLES consecutive rejections (not one) before calling it a
    replay instead of a single noisy OCR read.
    """
    ranges: list[tuple[int, int]] = []
    run: list[dict] = []

    def _flush():
        if len(run) >= MIN_REPLAY_SAMPLES:
            ranges.append((run[0]["frame"], run[-1]["frame"]))
        run.clear()

    for s in samples:
        if s.get("parse_error") == "timer_smoothed_out":
            run.append(s)
        else:
            _flush()
    _flush()

    return ranges


def _nearest_sample(
    frame_num: int,
    ocr_index: dict[int, dict],
    frames_list: list[int],
) -> Optional[dict]:
    """Sample closest to *frame_num*, with no distance limit. Debug output only."""
    if not frames_list:
        return None
    idx  = bisect.bisect_left(frames_list, frame_num)
    best = min(
        (c for c in (idx - 1, idx) if 0 <= c < len(frames_list)),
        key=lambda c: abs(frames_list[c] - frame_num),
        default=None,
    )
    return ocr_index[frames_list[best]] if best is not None else None


def _ocr_signal_at(
    frame_num: int,
    ocr_index: dict[int, dict],
    frames_list: list[int],
    stride: int,
) -> float:
    """
    Return OCR in-round probability [0.0, 1.0] for *frame_num*.

    1.0  — sample within half a stride, round number and timer both read
    0.9  — timer only
    0.6  — round number only
    0.0  — low confidence
    -1.0 — no nearby sample (caller should fall back to detection signal)

    A timer-only reading used to return -1.0, i.e. "no OCR here at all". That
    discarded the single strongest in-round signal the pipeline has: a running
    clock is near-conclusive evidence of being inside a round, and it survives
    on overlays that never render a parseable round number — which is most of
    them. `frames_list` is the caller's presorted key list; sorting it per frame
    made this O(n log n) on every frame of the video.
    """
    if not frames_list:
        return -1.0

    idx = bisect.bisect_left(frames_list, frame_num)

    nearest: Optional[dict] = None
    best_dist = stride         # only consider samples within one stride
    for cand_idx in (idx - 1, idx):
        if 0 <= cand_idx < len(frames_list):
            dist = abs(frames_list[cand_idx] - frame_num)
            if dist < best_dist:
                best_dist = dist
                nearest   = ocr_index[frames_list[cand_idx]]

    if nearest is None:
        return -1.0

    if nearest.get("parse_error") == "low_confidence":
        return 0.0

    has_round = nearest.get("round_num") is not None
    has_timer = nearest.get("seconds_remaining") is not None

    if has_round and has_timer:
        return 1.0
    if has_timer:
        return 0.9
    if has_round:
        return 0.6
    return -1.0


# ---------------------------------------------------------------------------
# Streaming segmenter
# ---------------------------------------------------------------------------

def _segment_streaming(
    detection_data: dict,
    ocr_index: dict[int, dict],
    ctx: DebugContext,
    fps: float,
    width: float,
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

    for frame in detection_data["frames"]:
        frame_num  = frame["frame"]
        last_frame = frame_num
        total_frames += 1

        both_present, engaged = _frame_signals(frame["detections"], width)
        if both_present:
            valid_frames += 1

        # --- OCR signal ---
        ocr_sig = _ocr_signal_at(frame_num, ocr_index, frames_list, ocr_stride)

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
            nearest_sample = _nearest_sample(frame_num, ocr_index, frames_list)
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
# Round-list plausibility and clock reconciliation
# ---------------------------------------------------------------------------

def _max_rounds_for_duration(total_frames: int, fps: float) -> int:
    """How many rounds could physically fit in a video of this length."""
    if fps <= 0:
        return 99
    total_secs = total_frames / fps
    per_round  = MIN_INTERIOR_ROUND_SECS + MIN_ROUND_BREAK_SECS
    # The final round needs no break after it, hence the added slack.
    return max(1, int((total_secs + MIN_ROUND_BREAK_SECS) // per_round))


def enforce_round_plausibility(
    rounds: list[tuple[int, int]],
    fps: float,
    total_frames: int,
    ctx: DebugContext,
) -> list[tuple[int, int]]:
    """
    Constrain a detection-derived round list to what a real fight could produce.

    Detection splits a round wherever "both fighters visible and close together"
    fails for long enough, which a ground scramble, a corner cutaway or a replay
    causes routinely — so it both invents breaks inside a round and promotes
    walkout footage to a round of its own. These rules describe how MMA actually
    behaves and need no OCR at all, which is what makes them the backstop for
    videos where the scoreboard is unreadable:

      1. Only the *last* round may be short, because only the last round can end
         in a finish. A short non-final segment is a walkout or a dropout, and
         is dropped rather than merged — merging it would drag the real round's
         start back across the walkout.
      2. Rounds are separated by a real break (~60s). A far shorter gap is a
         tracking dropout inside one round, so the two halves are rejoined.
      3. The video has to be long enough to hold the rounds claimed.

    Applied iteratively, because each edit can expose another.
    """
    if not rounds:
        return rounds

    min_interior = MIN_INTERIOR_ROUND_SECS * fps
    min_break    = MIN_ROUND_BREAK_SECS    * fps
    max_rounds   = _max_rounds_for_duration(total_frames, fps)

    work = sorted(rounds)
    changed = True
    while changed and len(work) > 1:
        changed = False

        # Rule 1 — drop short non-final rounds.
        for i in range(len(work) - 1):
            start, end = work[i]
            if end - start + 1 < min_interior:
                ctx.log("segmentation",
                        f"Plausibility: dropping non-final round {i+1} "
                        f"{start}–{end} ({(end - start + 1) / fps:.1f}s < "
                        f"{MIN_INTERIOR_ROUND_SECS:.0f}s) — too short to be a round")
                work.pop(i)
                changed = True
                break
        if changed:
            continue

        # Rule 2 — merge across gaps too short to be a between-round break.
        for i in range(len(work) - 1):
            gap = work[i + 1][0] - work[i][1]
            if gap < min_break:
                ctx.log("segmentation",
                        f"Plausibility: merging rounds {i+1} and {i+2} across a "
                        f"{gap / fps:.1f}s gap (< {MIN_ROUND_BREAK_SECS:.0f}s) — "
                        f"a break that short is a detection dropout")
                work[i] = (work[i][0], work[i + 1][1])
                work.pop(i + 1)
                changed = True
                break
        if changed:
            continue

        # Rule 3 — too many rounds for the video length; rejoin the closest pair.
        if len(work) > max_rounds:
            i = min(range(len(work) - 1),
                    key=lambda k: work[k + 1][0] - work[k][1])
            ctx.log("segmentation",
                    f"Plausibility: {len(work)} rounds cannot fit in "
                    f"{total_frames / fps:.0f}s (max {max_rounds}); merging "
                    f"rounds {i+1} and {i+2}")
            work[i] = (work[i][0], work[i + 1][1])
            work.pop(i + 1)
            changed = True

    return work


def _reconcile_with_clock(
    det_rounds: list[tuple[int, int]],
    clock_rounds: list,
    total_frames: int,
    ctx: DebugContext,
) -> tuple[list[tuple[int, int]], str]:
    """
    Merge clock-derived rounds with detection-derived ones.

    The clock decides *how many* rounds there are; detection only supplies edges
    the clock could not pin (see round_clock.ClockRound.start_anchored). This is
    the inverse of the original design, where the round count came from the
    engagement state machine and OCR was reduced to nudging boundaries — so a
    camera cutaway could invent a round while the scoreboard sat there reading
    "1" the entire time.

    Returns (rounds, source) where source is "clock" or "detection".
    """
    if not clock_rounds:
        return det_rounds, "detection"

    out: list[tuple[int, int]] = []
    for cr in clock_rounds:
        start, end = cr.start_frame, cr.end_frame

        overlapping = [(s, e) for s, e in det_rounds if e >= start and s <= end]
        if overlapping:
            if not cr.start_anchored:
                det_start = min(s for s, _ in overlapping)
                ctx.log("segmentation",
                        f"Round {cr.round_number}: clock start {start} is "
                        f"extrapolated (overlay appeared late) — using detection "
                        f"start {det_start}")
                start = det_start
            if not cr.end_anchored:
                det_end = max(e for _, e in overlapping)
                ctx.log("segmentation",
                        f"Round {cr.round_number}: clock never reached 0:00 — "
                        f"using detection end {det_end} instead of {end}")
                end = det_end

        start = max(1, start)
        end   = min(total_frames, end)
        if end > start:
            out.append((start, end))

    if not out:
        ctx.log("segmentation",
                "Clock rounds all collapsed after clamping — falling back to detection")
        return det_rounds, "detection"

    out.sort()
    ctx.log("segmentation",
            f"Clock is authoritative: {len(out)} round(s) "
            f"(detection had {len(det_rounds)})")
    return out, "clock"


# ---------------------------------------------------------------------------
# Per-frame signal helpers  (note: _read_fps and _iter_detection_frames
# were removed — detection data and fps are now passed in-memory)
# ---------------------------------------------------------------------------

def _frame_signals(detections: list[dict], width: float) -> tuple[bool, bool]:
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
    engaged = abs(red_cx - blue_cx) < ROUND_ENGAGEMENT_RATIO * width
    return True, engaged


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
