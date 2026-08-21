"""Measure whether a labeller actually catches a corner swap (plan 0g).

`0a`/`0d`'s mitigation for corner-assignment errors is that the labeller sees
a swap on the overlay and marks a `corner_swap` span. That's an untested
assumption about human attention, applied to the hardest place on screen to
notice anything (overlapping boxes mid-clinch). This module injects a known
swap into `fighter_frames`, then compares the labeller's `corner_swap` spans
(after they work the fight normally) against the injected window.

Workflow:
    1. `python -m eval.cli inject-swap <video> --start F --end F`
    2. Label the fight normally in the Annotate UI, including reviewing the
       injected window as if it were real.
    3. `python -m eval.cli export <video>` to pull the labels out of Postgres.
    4. `python -m eval.cli corner-swap-recall <video> --start F --end F`
    5. `UPDATE ... SET corner = 1 - corner` is its own inverse — re-running
       `inject-swap` with the same bounds restores the original assignment.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text

from database import SessionLocal

from .predictions import lookup_fight
from .schema import FightLabels, Span


def inject_swap(video: str, start: int, end: int) -> int:
    """Flip `corner` on `fighter_frames` for [start, end]. Its own inverse —
    call again with the same bounds to restore. Returns rows affected."""
    db = SessionLocal()
    try:
        fight_id, _, _, _ = lookup_fight(db, video)
        result = db.execute(
            text("UPDATE fighter_frames SET corner = 1 - corner "
                 "WHERE fight_id = :fid AND frame BETWEEN :start AND :end"),
            {"fid": fight_id, "start": start, "end": end},
        )
        db.commit()
        return result.rowcount
    finally:
        db.close()


@dataclass
class RecallResult:
    detected: bool
    matched_span: Optional[Span]
    start_error_frames: Optional[int]  # matched_span.start - injected start
    end_error_frames: Optional[int]    # matched_span.end - injected end
    corner_swap_spans: list[Span]


def measure_recall(video: str, start: int, end: int) -> RecallResult:
    """Compare a labeller's exported `corner_swap` spans against an injected
    window. `detected` = any span overlaps the injection at all — the crude,
    honest bound described in plan 0a: "fraction of labelled frames covered
    by a corner_swap span" only becomes a real corner-assignment error rate
    once this recall is known.
    """
    labels = FightLabels.for_video(video)
    spans = labels.corner_swaps

    best: Optional[Span] = None
    best_overlap = 0
    for s in spans:
        overlap = max(0, min(s.end, end) - max(s.start, start) + 1)
        if overlap > best_overlap:
            best, best_overlap = s, overlap

    if best is None:
        return RecallResult(detected=False, matched_span=None,
                             start_error_frames=None, end_error_frames=None,
                             corner_swap_spans=spans)

    return RecallResult(
        detected=True,
        matched_span=best,
        start_error_frames=best.start - start,
        end_error_frames=best.end - end,
        corner_swap_spans=spans,
    )


def format_recall(r: RecallResult, start: int, end: int) -> str:
    L: list[str] = []
    add = L.append
    add(f"\n{'=' * 70}")
    add(f"CORNER-SWAP RECALL   injected [{start}, {end}]  "
        f"({len(r.corner_swap_spans)} corner_swap span(s) labelled)")
    add("=" * 70)
    if not r.detected:
        add("  [MISS] no labelled corner_swap span overlaps the injected window.")
        add("         The mitigation did not work for this window — treat")
        add("         the corner-assignment error rate as an unmeasured risk,")
        add("         not a small one, until this is re-run and passes.")
    else:
        add("  [DETECTED] a corner_swap span overlaps the injected window.")
        add(f"    labelled span    [{r.matched_span.start}, {r.matched_span.end}]")
        add(f"    start edge error {r.start_error_frames:+d} frames")
        add(f"    end edge error   {r.end_error_frames:+d} frames")
        if abs(r.start_error_frames) > 10 or abs(r.end_error_frames) > 10:
            add("    ⚠ boundary off by >10 frames — that many frames of the")
            add("      injected window are still exported with the wrong corner.")
    add("")
    return "\n".join(L)
