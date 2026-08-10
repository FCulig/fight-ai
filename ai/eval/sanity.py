"""Label-free artifact checks on pipeline output.

These metrics need no ground truth — they detect output that is *internally
impossible* rather than merely inaccurate, so they run on any processed video
today and serve as a cheap regression gate between label batches.

Each check has a plausibility band derived from how MMA actually behaves. A
failure means the pipeline produced something no real fight could have
generated, which localises a bug far faster than an F1 score does.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .predictions import Predictions

# --- Plausibility bands ---------------------------------------------------
# Two fighters do not land strikes on the same frame; anything above a trickle
# is the signature of both corners sharing one pose skeleton.
MAX_MUTUAL_STRIKE_EVENT_RATIO = 0.02
# Every strike should fall inside a round. Non-zero means round gating is absent
# or segmentation is wrong; either way the events come from replays/walkouts.
MAX_OUT_OF_ROUND_RATIO = 0.0
# Real fight state (striking/clinch/ground) persists for seconds at a time.
MAX_STATE_TRANSITIONS_PER_MIN = 15.0
MIN_STATE_MEDIAN_DWELL_SECS = 1.0
# Strikes thrown per minute of round time — a wide but finite band.
MIN_STRIKES_PER_MIN = 5.0
MAX_STRIKES_PER_MIN = 60.0


@dataclass
class Check:
    name: str
    value: float
    passed: bool
    detail: str = ""
    band: str = ""


@dataclass
class SanityReport:
    video: str
    fps: int
    round_minutes: float
    checks: list[Check] = field(default_factory=list)
    type_counts: Counter = field(default_factory=Counter)
    out_of_round_types: Counter = field(default_factory=Counter)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    @property
    def passed(self) -> bool:
        return not self.failures


def _round_minutes(preds: Predictions) -> float:
    frames = sum(r.length for r in preds.rounds)
    if not frames and preds.frame_count:
        frames = preds.frame_count
    return frames / preds.fps / 60 if preds.fps else 0.0


def check(preds: Predictions) -> SanityReport:
    rep = SanityReport(
        video=preds.video,
        fps=preds.fps,
        round_minutes=_round_minutes(preds),
    )
    strikes = preds.strikes
    total = len(strikes)
    rep.type_counts = Counter(s.action for s in strikes)

    # --- 1. Events outside any round -------------------------------------
    if preds.rounds:
        outside = [s for s in strikes if not preds.in_any_round(s.frame)]
        rep.out_of_round_types = Counter(s.action for s in outside)
        ratio = len(outside) / total if total else 0.0
        rep.checks.append(Check(
            name="events inside rounds",
            value=ratio,
            passed=ratio <= MAX_OUT_OF_ROUND_RATIO,
            detail=f"{len(outside)}/{total} strikes fall outside every detected round",
            band=f"expected 0% (=< {MAX_OUT_OF_ROUND_RATIO:.0%})",
        ))

    # --- 2. Simultaneous mutual strikes ----------------------------------
    by_frame: dict[int, set[str]] = defaultdict(set)
    for s in strikes:
        by_frame[s.frame].add(s.fighter)
    mutual_frames = [f for f, who in by_frame.items() if len(who) == 2]
    mutual_events = sum(len(by_frame[f]) for f in mutual_frames)
    ratio = mutual_events / total if total else 0.0
    rep.checks.append(Check(
        name="no simultaneous mutual strikes",
        value=ratio,
        passed=ratio <= MAX_MUTUAL_STRIKE_EVENT_RATIO,
        detail=(f"{len(mutual_frames)} frames have BOTH fighters striking "
                f"({mutual_events}/{total} events). Both corners sharing one pose "
                f"skeleton produces exactly this."),
        band=f"expected =< {MAX_MUTUAL_STRIKE_EVENT_RATIO:.0%} of events",
    ))

    # --- 3. Duplicate events ---------------------------------------------
    dupes = Counter((s.frame, s.fighter, s.action) for s in strikes)
    n_dupes = sum(n - 1 for n in dupes.values() if n > 1)
    rep.checks.append(Check(
        name="no duplicate events",
        value=float(n_dupes),
        passed=n_dupes == 0,
        detail=f"{n_dupes} exact duplicate (frame, fighter, action) rows",
        band="expected 0",
    ))

    # --- 4. State stability ----------------------------------------------
    changes = preds.state_changes
    if rep.round_minutes and changes:
        per_min = len(changes) / rep.round_minutes
        rep.checks.append(Check(
            name="state does not flap",
            value=per_min,
            passed=per_min <= MAX_STATE_TRANSITIONS_PER_MIN,
            detail=f"{len(changes)} state transitions over "
                   f"{rep.round_minutes:.1f} min = {per_min:.1f}/min",
            band=f"expected =< {MAX_STATE_TRANSITIONS_PER_MIN:.0f}/min",
        ))

        dwells = [
            (b.frame - a.frame) / preds.fps
            for a, b in zip(changes, changes[1:])
        ]
        if dwells:
            dwells.sort()
            median = dwells[len(dwells) // 2]
            rep.checks.append(Check(
                name="state dwell is physical",
                value=median,
                passed=median >= MIN_STATE_MEDIAN_DWELL_SECS,
                detail=f"median {median:.2f}s between state changes; "
                       f"{sum(1 for d in dwells if d < 0.5)}/{len(dwells)} "
                       f"segments are under 0.5s",
                band=f"expected >= {MIN_STATE_MEDIAN_DWELL_SECS:.1f}s",
            ))

    # --- 5. Strike rate ---------------------------------------------------
    if rep.round_minutes:
        in_round = [s for s in strikes
                    if not preds.rounds or preds.in_any_round(s.frame)]
        rate = len(in_round) / rep.round_minutes
        rep.checks.append(Check(
            name="strike rate is plausible",
            value=rate,
            passed=MIN_STRIKES_PER_MIN <= rate <= MAX_STRIKES_PER_MIN,
            detail=f"{len(in_round)} in-round strikes over "
                   f"{rep.round_minutes:.1f} min = {rate:.1f}/min",
            band=f"expected {MIN_STRIKES_PER_MIN:.0f}–{MAX_STRIKES_PER_MIN:.0f}/min",
        ))

    return rep


def format_sanity(rep: SanityReport) -> str:
    L: list[str] = []
    add = L.append

    add(f"\n{'=' * 70}")
    add(f"SANITY  {rep.video}   ({rep.round_minutes:.1f} min of round time)")
    add("=" * 70)
    add("\nThese checks need no labels. A failure means the output is internally")
    add("impossible, not merely inaccurate.\n")

    for c in rep.checks:
        mark = "PASS" if c.passed else "FAIL"
        add(f"  [{mark}] {c.name}")
        add(f"         {c.detail}")
        add(f"         {c.band}")

    if rep.type_counts:
        add("\n  event types:")
        for action, n in rep.type_counts.most_common():
            extra = rep.out_of_round_types.get(action, 0)
            suffix = f"   ({extra} outside rounds)" if extra else ""
            add(f"    {action:<16} {n:5d}{suffix}")

    n_fail = len(rep.failures)
    add(f"\n  {len(rep.checks) - n_fail}/{len(rep.checks)} checks passed")
    add("")
    return "\n".join(L)
