"""
Round boundaries derived from the scoreboard clock.

The on-screen round timer is the only signal in the pipeline that is
*deterministic*: it advances exactly one second per second of video. Its slope
against frame number is therefore known a priori (-1/fps counting down), and
only the intercept has to be estimated. That makes the fit a one-parameter
median — robust to OCR noise, and usable from a handful of readings scattered
anywhere in the round rather than requiring continuous coverage.

This matters because broadcast overlays are intermittent: they disappear during
replays, corner shots and ground close-ups. A signal that needed the overlay to
be continuously visible would be unusable. A clock fit needs three readings.

What this module is authoritative for:
  * **round count** — one fitted run per round, split on clock resets and round
    number increments;
  * **round identity** — which round number each segment is.

What it is deliberately *not* always authoritative for:
  * **exact edges** — the clock only pins an edge when a reading was actually
    observed near it (`start_anchored` / `end_anchored`). A round whose overlay
    only appeared with 2:00 left cannot say where it started, and a round that
    ended in a knockout never reaches 0:00, so extrapolating to clock-zero would
    place the end after the fight stopped. Unanchored edges are left for
    detection-based segmentation to fill in — see `_reconcile_with_clock` in
    fight_segmentation.py.
"""

import statistics
from dataclasses import dataclass
from typing import Optional

from models.constants import (
    ROUND_CLOCK_STANDARD_LENGTHS_SECS,
    ROUND_CLOCK_MIN_SAMPLES,
    ROUND_CLOCK_MAX_RESIDUAL_SECS,
    ROUND_CLOCK_RESET_MIN_JUMP_SECS,
    ROUND_CLOCK_LENGTH_TOLERANCE_SECS,
)
from debug import DebugContext


# A single usable OCR reading: (frame, seconds_remaining, round_num or None)
Reading = tuple[int, float, Optional[int]]


@dataclass
class ClockRound:
    """One round located by fitting the scoreboard clock."""
    round_number: int
    start_frame: int
    end_frame: int
    length_secs: float
    support: int             # timer readings backing the fit
    numbered: bool           # round_number was read by OCR, not inferred from order
    start_anchored: bool     # a reading was seen near the top of the round
    end_anchored: bool       # a reading was seen near 0:00

    @property
    def length_frames(self) -> int:
        return self.end_frame - self.start_frame + 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def derive_rounds_from_clock(
    samples: list[dict],
    fps: float,
    total_frames: int,
    debug_ctx: Optional[DebugContext] = None,
) -> tuple[list[ClockRound], dict]:
    """
    Fit the scoreboard clock and return the rounds it implies.

    Args:
        samples:      Smoothed OCR samples from extract_scoreboard_samples().
        fps:          Frames per second, from the fights DB row.
        total_frames: Video length in frames, used to clamp extrapolated edges.
        debug_ctx:    DebugContext for logging.

    Returns:
        (rounds, diagnostics). `rounds` is empty when the clock could not be
        fitted, which is the signal for callers to fall back to detection.

    Samples whose timer was rejected during smoothing (`timer_smoothed_out` —
    i.e. slow-motion replays) carry `seconds_remaining = None` and so are
    excluded here for free: a replay clock must not drag the fit.
    """
    ctx = debug_ctx or DebugContext.disabled()

    readings: list[Reading] = sorted(
        (
            (int(s["frame"]), float(s["seconds_remaining"]), s.get("round_num"))
            for s in samples
            if s.get("seconds_remaining") is not None
        ),
        key=lambda r: r[0],
    )

    diag = {
        "timer_readings":  len(readings),
        "round_readings":  sum(1 for s in samples if s.get("round_num") is not None),
        "direction":       None,
        "runs":            0,
        "rejected":        0,
    }

    if len(readings) < ROUND_CLOCK_MIN_SAMPLES:
        ctx.log("round_clock",
                f"Only {len(readings)} timer reading(s) — need "
                f"{ROUND_CLOCK_MIN_SAMPLES}; no clock rounds")
        return [], diag

    direction = _clock_direction(readings)
    diag["direction"] = direction
    ctx.log("round_clock",
            f"{len(readings)} timer readings, clock counts {direction}")

    runs = _split_runs(readings, direction)

    fitted: list[tuple[float, list[Reading]]] = []
    rejected = 0
    for run in runs:
        intercept, inliers, n_rej = _fit_intercept(run, fps, direction)
        rejected += n_rej
        if len(inliers) >= ROUND_CLOCK_MIN_SAMPLES:
            fitted.append((intercept, inliers))

    fitted = _merge_consistent_runs(fitted, fps, direction)
    diag["runs"]     = len(fitted)
    diag["rejected"] = rejected

    if not fitted:
        ctx.log("round_clock", "No run had enough inliers to fit; no clock rounds")
        return [], diag

    rounds = _build_rounds(fitted, fps, total_frames, direction, ctx)
    for r in rounds:
        ctx.log("round_clock",
                f"Round {r.round_number}: frames {r.start_frame}–{r.end_frame} "
                f"({r.length_frames / fps:.1f}s of a {r.length_secs:.0f}s round)  "
                f"support={r.support}  "
                f"start_anchored={r.start_anchored}  end_anchored={r.end_anchored}  "
                f"numbered={r.numbered}")
    return rounds, diag


# ---------------------------------------------------------------------------
# Fitting internals
# ---------------------------------------------------------------------------

def _clock_direction(readings: list[Reading]) -> str:
    """Whether the clock counts down (usual) or up, by majority of steps."""
    n_dec = sum(1 for a, b in zip(readings, readings[1:]) if b[1] < a[1])
    n_inc = sum(1 for a, b in zip(readings, readings[1:]) if b[1] > a[1])
    return "down" if n_dec >= n_inc else "up"


def _split_runs(readings: list[Reading], direction: str) -> list[list[Reading]]:
    """
    Cut the reading stream wherever a new round demonstrably begins.

    Two independent triggers, either sufficient:
      * the OCR'd round number changes;
      * the clock jumps *against* its direction of travel by more than
        ROUND_CLOCK_RESET_MIN_JUMP_SECS — i.e. it was reset for a new round.
    """
    runs: list[list[Reading]] = []
    current: list[Reading] = [readings[0]]

    for prev, cur in zip(readings, readings[1:]):
        prev_num, cur_num = prev[2], cur[2]
        starts_new = prev_num is not None and cur_num is not None and cur_num != prev_num

        delta = cur[1] - prev[1]
        if direction == "down" and delta > ROUND_CLOCK_RESET_MIN_JUMP_SECS:
            starts_new = True
        elif direction == "up" and delta < -ROUND_CLOCK_RESET_MIN_JUMP_SECS:
            starts_new = True

        if starts_new:
            runs.append(current)
            current = []
        current.append(cur)

    runs.append(current)
    return runs


def _intercepts(run: list[Reading], fps: float, direction: str) -> list[float]:
    """
    Per-reading estimate of the run's single free parameter.

    Counting down, clock(f) = C - f/fps, so C = clock + f/fps and every reading
    in the same round yields the same C. Counting up, clock(f) = f/fps - D.
    """
    if direction == "down":
        return [secs + frame / fps for frame, secs, _ in run]
    return [frame / fps - secs for frame, secs, _ in run]


def _fit_intercept(
    run: list[Reading],
    fps: float,
    direction: str,
) -> tuple[float, list[Reading], int]:
    """Median fit with one outlier-rejection pass. Returns (C, inliers, n_rejected)."""
    values = _intercepts(run, fps, direction)
    centre = statistics.median(values)

    inliers = [
        r for r, v in zip(run, values)
        if abs(v - centre) <= ROUND_CLOCK_MAX_RESIDUAL_SECS
    ]
    n_rejected = len(run) - len(inliers)

    if inliers and n_rejected:
        centre = statistics.median(_intercepts(inliers, fps, direction))

    return centre, inliers, n_rejected


def _merge_consistent_runs(
    fitted: list[tuple[float, list[Reading]]],
    fps: float,
    direction: str,
) -> list[tuple[float, list[Reading]]]:
    """
    Rejoin consecutive runs that turn out to describe the same round.

    A single bad OCR read (0:50 misread as 3:50) can look like a clock reset and
    split one round in two. Two runs from the same round fit the same intercept,
    so agreement within the residual tolerance — with no conflicting round
    numbers — is proof they should not have been split.
    """
    if not fitted:
        return []

    merged = [fitted[0]]
    for centre, inliers in fitted[1:]:
        prev_centre, prev_inliers = merged[-1]

        prev_nums = {n for _, _, n in prev_inliers if n is not None}
        cur_nums  = {n for _, _, n in inliers if n is not None}
        conflicts = bool(prev_nums and cur_nums and prev_nums != cur_nums)

        if not conflicts and abs(centre - prev_centre) <= ROUND_CLOCK_MAX_RESIDUAL_SECS:
            combined = sorted(prev_inliers + inliers, key=lambda r: r[0])
            new_centre, new_inliers, _ = _fit_intercept(combined, fps, direction)
            merged[-1] = (new_centre, new_inliers)
        else:
            merged.append((centre, inliers))

    return merged


def _snap_length(observed_max: float) -> float:
    """
    Snap the observed clock maximum to the nearest standard round length.

    Falls through to the observed value for formats we don't know about, rather
    than forcing a fight into a 3- or 5-minute mould.
    """
    for length in sorted(ROUND_CLOCK_STANDARD_LENGTHS_SECS):
        if observed_max <= length + ROUND_CLOCK_LENGTH_TOLERANCE_SECS:
            return length
    return observed_max


def _build_rounds(
    fitted: list[tuple[float, list[Reading]]],
    fps: float,
    total_frames: int,
    direction: str,
    ctx: DebugContext,
) -> list[ClockRound]:
    numbers = _assign_round_numbers(fitted)

    rounds: list[ClockRound] = []
    for (centre, inliers), (number, numbered) in zip(fitted, numbers):
        clocks       = [secs for _, secs, _ in inliers]
        observed_max = max(clocks)
        observed_min = min(clocks)
        length       = _snap_length(observed_max)

        if direction == "down":
            start_secs = centre - length
            end_secs   = centre
        else:
            start_secs = centre
            end_secs   = centre + length

        start_frame = max(1, int(round(start_secs * fps)))
        end_frame   = min(total_frames, int(round(end_secs * fps)))
        if end_frame <= start_frame:
            ctx.log("round_clock",
                    f"Discarding degenerate clock round {number}: "
                    f"{start_frame}–{end_frame}")
            continue

        # An edge is only pinned if a reading was actually observed near it.
        # Otherwise we are extrapolating past all evidence: a round whose
        # overlay appeared late cannot say where it began, and a round ended by
        # a finish never reaches 0:00.
        start_anchored = observed_max >= length - ROUND_CLOCK_LENGTH_TOLERANCE_SECS
        end_anchored   = observed_min <= ROUND_CLOCK_LENGTH_TOLERANCE_SECS

        rounds.append(ClockRound(
            round_number=number,
            start_frame=start_frame,
            end_frame=end_frame,
            length_secs=length,
            support=len(inliers),
            numbered=numbered,
            start_anchored=start_anchored,
            end_anchored=end_anchored,
        ))

    return rounds


def _assign_round_numbers(
    fitted: list[tuple[float, list[Reading]]],
) -> list[tuple[int, bool]]:
    """
    Number each run, returning (round_number, came_from_ocr) per run.

    Where OCR read a round number, it wins (by mode over the run's inliers).
    Where it didn't, the number is counted off from the nearest run that has
    one — so a fight whose overlay only became readable in round 2 still numbers
    its rounds 2, 3 rather than restarting at 1.
    """
    observed: list[Optional[int]] = []
    for _centre, inliers in fitted:
        nums = [n for _, _, n in inliers if n is not None]
        observed.append(statistics.mode(nums) if nums else None)

    anchor = next((i for i, n in enumerate(observed) if n is not None), None)

    out: list[tuple[int, bool]] = []
    for i, n in enumerate(observed):
        if n is not None:
            out.append((n, True))
        elif anchor is not None:
            out.append((max(1, observed[anchor] + (i - anchor)), False))
        else:
            out.append((i + 1, False))
    return out
