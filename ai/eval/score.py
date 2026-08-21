"""Scoring: pipeline predictions vs. hand-labelled ground truth.

Design notes
------------
**Strike matching ignores the fighter.** Predictions are matched to ground truth
on time proximity alone, then attribution accuracy is reported separately. This
deliberately separates two failure modes that a joint match key would conflate:
"we missed the strike entirely" and "we saw the strike but credited the wrong
corner". Corner assignment is a known weak point, and folding it into the
detection score would hide detection progress behind attribution noise.
Use ``strict_fighter=True`` to require the corner to match.

**Only scored frames count.** Both ground-truth and predicted events outside a
labelled round, or inside an ``excluded`` span (replay, walkout, camera cut),
are dropped before matching rather than counted as false positives — the
pipeline should not be graded on footage nobody labelled.

**Non-specific predictions are excluded from family/target denominators.** The
pipeline emits ``clinch_punch`` / ``ground_punch`` with no family or target, so
scoring those against a labelled ``hook``/``head`` would penalise it for a
distinction it never attempts. They still count for event-level detection.
"""

import statistics
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

from .predictions import PredictedStrike, Predictions
from .schema import STATES, FightLabels, Strike

DEFAULT_TOLERANCE_SECS = 0.25


@dataclass
class PRF:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class StrikeScore:
    detection: PRF = field(default_factory=PRF)
    tolerance_frames: int = 0
    # Accuracy numerators/denominators over matched pairs only.
    fighter_correct: int = 0
    fighter_total: int = 0
    family_correct: int = 0
    family_total: int = 0
    target_correct: int = 0
    target_total: int = 0
    landed_correct: int = 0
    landed_total: int = 0
    nonspecific_matches: int = 0
    family_confusion: dict[tuple[str, str], int] = field(default_factory=dict)
    # Signed (pred.frame - truth.frame) per matched pair, not absolute. A
    # systematic lag (e.g. labeller reaction time) is a bias to subtract once,
    # not spread to widen the tolerance window by — see bias/jitter below.
    matched_offsets: list[int] = field(default_factory=list)
    missed: list[Strike] = field(default_factory=list)
    spurious: list[PredictedStrike] = field(default_factory=list)

    def _acc(self, num: int, den: int) -> Optional[float]:
        return num / den if den else None

    @property
    def offset_bias(self) -> Optional[float]:
        """Median signed offset — a systematic lag, not spread."""
        return statistics.median(self.matched_offsets) if self.matched_offsets else None

    @property
    def offset_jitter(self) -> Optional[float]:
        """Median absolute offset — genuine temporal spread."""
        return statistics.median(abs(o) for o in self.matched_offsets) if self.matched_offsets else None

    @property
    def fighter_accuracy(self) -> Optional[float]:
        return self._acc(self.fighter_correct, self.fighter_total)

    @property
    def family_accuracy(self) -> Optional[float]:
        return self._acc(self.family_correct, self.family_total)

    @property
    def target_accuracy(self) -> Optional[float]:
        return self._acc(self.target_correct, self.target_total)

    @property
    def landed_accuracy(self) -> Optional[float]:
        return self._acc(self.landed_correct, self.landed_total)


@dataclass
class StateScore:
    frames_scored: int = 0
    frames_correct: int = 0
    confusion: dict[tuple[str, str], int] = field(default_factory=dict)
    gt_transitions_per_min: float = 0.0
    pred_transitions_per_min: float = 0.0
    gt_median_dwell_secs: float = 0.0
    pred_median_dwell_secs: float = 0.0

    @property
    def accuracy(self) -> Optional[float]:
        return self.frames_correct / self.frames_scored if self.frames_scored else None


@dataclass
class RoundScore:
    matched: list[tuple[int, float, float, float]] = field(default_factory=list)
    gt_count: int = 0
    pred_count: int = 0

    @property
    def mean_iou(self) -> Optional[float]:
        return statistics.mean(m[1] for m in self.matched) if self.matched else None

    @property
    def count_correct(self) -> bool:
        """
        Whether the pipeline found the right *number* of rounds.

        Scored separately from IoU because the two fail independently, and only
        this one is visible to a user: splitting one round into three still
        yields a healthy mean IoU, since the largest predicted segment overlaps
        the real round fine — but the round list is plainly wrong. Round count
        is the failure that had to be corrected by hand on fight 44.
        """
        return self.gt_count == self.pred_count


@dataclass
class Report:
    video: str
    fps: int
    scored_minutes: float
    strikes: StrikeScore
    state: StateScore
    rounds: RoundScore


# ---------------------------------------------------------------------------
# Strike matching
# ---------------------------------------------------------------------------

def _match_strikes(
    gt: list[Strike],
    pred: list[PredictedStrike],
    tolerance_frames: int,
    strict_fighter: bool,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Optimal one-to-one matching minimising total temporal offset.

    Greedy nearest-match is order-dependent and inflates or deflates the score
    depending on which end you start from, so this solves the assignment problem
    properly. Pairs beyond the tolerance are forbidden and dropped after solving.

    Returns (pairs, unmatched_gt_indices, unmatched_pred_indices).
    """
    if not gt or not pred:
        return [], list(range(len(gt))), list(range(len(pred)))

    big = tolerance_frames * 10 + 1_000_000
    cost = np.full((len(gt), len(pred)), float(big))
    for i, g in enumerate(gt):
        for j, p in enumerate(pred):
            offset = abs(g.frame - p.frame)
            if offset > tolerance_frames:
                continue
            if strict_fighter and g.fighter != p.fighter:
                continue
            cost[i, j] = offset

    rows, cols = linear_sum_assignment(cost)

    pairs = [(int(i), int(j)) for i, j in zip(rows, cols) if cost[i, j] < big]
    matched_gt = {i for i, _ in pairs}
    matched_pred = {j for _, j in pairs}
    return (
        pairs,
        [i for i in range(len(gt)) if i not in matched_gt],
        [j for j in range(len(pred)) if j not in matched_pred],
    )


def score_strikes(
    labels: FightLabels,
    preds: Predictions,
    tolerance_secs: float = DEFAULT_TOLERANCE_SECS,
    strict_fighter: bool = False,
) -> StrikeScore:
    scored = labels.scored_frames()
    gt = [s for s in labels.strikes if s.frame in scored]
    pred = [s for s in preds.strikes if s.frame in scored]

    tol = max(1, round(tolerance_secs * labels.fps))
    pairs, unmatched_gt, unmatched_pred = _match_strikes(gt, pred, tol, strict_fighter)

    out = StrikeScore(tolerance_frames=tol)
    out.detection = PRF(tp=len(pairs), fp=len(unmatched_pred), fn=len(unmatched_gt))
    out.missed = [gt[i] for i in unmatched_gt]
    out.spurious = [pred[j] for j in unmatched_pred]

    for i, j in pairs:
        g, p = gt[i], pred[j]
        out.matched_offsets.append(p.frame - g.frame)

        out.fighter_total += 1
        if g.fighter == p.fighter:
            out.fighter_correct += 1

        if not p.is_specific:
            # Grappling prediction — carries no family/target claim to grade.
            out.nonspecific_matches += 1
        else:
            out.family_total += 1
            if g.family == p.family:
                out.family_correct += 1
            key = (g.family, p.family)
            out.family_confusion[key] = out.family_confusion.get(key, 0) + 1

            if g.target != "unknown":
                out.target_total += 1
                if g.target == p.target:
                    out.target_correct += 1

        if g.landed is not None and p.landed is not None:
            out.landed_total += 1
            if g.landed == p.landed:
                out.landed_correct += 1

    return out


# ---------------------------------------------------------------------------
# Fight state
# ---------------------------------------------------------------------------

def _segments_from_frames(frames: list[int], state_of) -> list[tuple[str, int]]:
    """Collapse a frame sequence into (state, length) runs, ignoring gaps."""
    segments: list[tuple[str, int]] = []
    for f in frames:
        s = state_of(f)
        if s is None:
            continue
        if segments and segments[-1][0] == s:
            segments[-1] = (s, segments[-1][1] + 1)
        else:
            segments.append((s, 1))
    return segments


def score_state(labels: FightLabels, preds: Predictions) -> StateScore:
    scored = sorted(labels.scored_frames())
    out = StateScore()

    for f in scored:
        g = labels.state_at(f)
        if g is None:
            continue          # frame inside a round but not state-labelled
        p = preds.state_at(f)
        if p is None:
            # `preds` is sometimes a second FightLabels (agreement — see
            # cli.py's `agreement` command), whose state_at() returns None
            # outside a labelled span, unlike Predictions.state_at() which
            # always falls back to initial_state. Either way, "no prediction
            # here" is not a mismatch to grade.
            continue
        out.frames_scored += 1
        if g == p:
            out.frames_correct += 1
        out.confusion[(g, p)] = out.confusion.get((g, p), 0) + 1

    minutes = len(scored) / labels.fps / 60 if labels.fps else 0
    gt_segs = _segments_from_frames(scored, labels.state_at)
    pred_segs = _segments_from_frames(scored, preds.state_at)

    if minutes:
        out.gt_transitions_per_min = max(0, len(gt_segs) - 1) / minutes
        out.pred_transitions_per_min = max(0, len(pred_segs) - 1) / minutes
    if gt_segs:
        out.gt_median_dwell_secs = statistics.median(n for _, n in gt_segs) / labels.fps
    if pred_segs:
        out.pred_median_dwell_secs = statistics.median(n for _, n in pred_segs) / labels.fps

    return out


# ---------------------------------------------------------------------------
# Rounds
# ---------------------------------------------------------------------------

def score_rounds(labels: FightLabels, preds: Predictions) -> RoundScore:
    out = RoundScore(gt_count=len(labels.rounds), pred_count=len(preds.rounds))

    for g in labels.rounds:
        best, best_iou = None, 0.0
        for p in preds.rounds:
            inter = max(0, min(g.end, p.end) - max(g.start, p.start) + 1)
            union = g.length + p.length - inter
            iou = inter / union if union else 0.0
            if iou > best_iou:
                best, best_iou = p, iou
        if best is not None:
            out.matched.append((
                g.round,
                best_iou,
                (best.start - g.start) / labels.fps,
                (best.end - g.end) / labels.fps,
            ))

    return out


def score(
    labels: FightLabels,
    preds: Predictions,
    tolerance_secs: float = DEFAULT_TOLERANCE_SECS,
    strict_fighter: bool = False,
) -> Report:
    if labels.fps != preds.fps:
        print(f"  warning: label fps ({labels.fps}) != pipeline fps ({preds.fps}); "
              f"using label fps for all conversions")
    return Report(
        video=labels.video,
        fps=labels.fps,
        scored_minutes=len(labels.scored_frames()) / labels.fps / 60,
        strikes=score_strikes(labels, preds, tolerance_secs, strict_fighter),
        state=score_state(labels, preds),
        rounds=score_rounds(labels, preds),
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _pct(v: Optional[float]) -> str:
    return f"{v:6.1%}" if v is not None else "     —"


def format_report(r: Report, show_examples: int = 8) -> str:
    L: list[str] = []
    add = L.append

    add(f"\n{'=' * 70}")
    add(f"EVAL  {r.video}   ({r.scored_minutes:.1f} min scored @ {r.fps} fps)")
    add("=" * 70)

    s = r.strikes
    d = s.detection
    add(f"\nSTRIKE DETECTION   (±{s.tolerance_frames} frames "
        f"= {s.tolerance_frames / r.fps:.2f}s tolerance)")
    add(f"  ground truth {d.tp + d.fn:4d}   predicted {d.tp + d.fp:4d}")
    add(f"  TP {d.tp:4d}   FP {d.fp:4d}   FN {d.fn:4d}")
    add(f"  precision {d.precision:6.1%}   recall {d.recall:6.1%}   F1 {d.f1:6.1%}")
    if s.matched_offsets:
        add(f"  temporal offset on matches: bias {s.offset_bias:+.1f}f "
            f"(systematic lag)   jitter {s.offset_jitter:.1f}f (spread)")

    add("\nCLASSIFICATION   (matched strikes only)")
    add(f"  fighter attribution {_pct(s.fighter_accuracy)}  ({s.fighter_total} matches)")
    add(f"  strike family       {_pct(s.family_accuracy)}  ({s.family_total} specific)")
    add(f"  target zone         {_pct(s.target_accuracy)}  ({s.target_total} specific)")
    add(f"  landed vs missed    {_pct(s.landed_accuracy)}  ({s.landed_total} confirmable)")
    if s.nonspecific_matches:
        add(f"  {s.nonspecific_matches} matches were grappling predictions "
            f"(no family/target claim — excluded above)")

    if s.family_confusion:
        add("\n  family confusion (truth → predicted):")
        for (g, p), n in sorted(s.family_confusion.items(), key=lambda kv: -kv[1])[:10]:
            mark = "  " if g == p else " ✗"
            add(f"   {mark} {g:>9} → {p:<9} {n:4d}")

    st = r.state
    add(f"\nFIGHT STATE")
    add(f"  per-frame accuracy {_pct(st.accuracy)}  ({st.frames_scored} frames scored)")
    add(f"  transitions/min    truth {st.gt_transitions_per_min:6.1f}   "
        f"predicted {st.pred_transitions_per_min:6.1f}")
    add(f"  median dwell (s)   truth {st.gt_median_dwell_secs:6.2f}   "
        f"predicted {st.pred_median_dwell_secs:6.2f}")
    if st.pred_transitions_per_min > 3 * max(st.gt_transitions_per_min, 0.1):
        add("  ⚠ predicted state flaps far faster than reality — hysteresis is "
            "not holding.")
    if st.confusion:
        add("\n  state confusion (truth → predicted):")
        labels_seen = sorted({p for _, p in st.confusion})
        add("           " + "".join(f"{p:>10}" for p in labels_seen))
        for g in STATES:
            row = [st.confusion.get((g, p), 0) for p in labels_seen]
            if any(row):
                add(f"  {g:>8} " + "".join(f"{n:>10d}" for n in row))

    rd = r.rounds
    verdict = "OK" if rd.count_correct else "WRONG"
    add(f"\nROUNDS   truth {rd.gt_count}   predicted {rd.pred_count}   count {verdict}")
    for num, iou, dstart, dend in rd.matched:
        add(f"  round {num}: IoU {iou:5.1%}   start {dstart:+6.2f}s   end {dend:+6.2f}s")
    if not rd.count_correct:
        add("  NOTE: mean IoU stays high when one round is split into several — "
            "the count is what catches that.")

    if show_examples and s.missed:
        add(f"\nWORST MISSES (first {show_examples} of {len(s.missed)} FN)")
        for m in s.missed[:show_examples]:
            t = m.frame / r.fps
            add(f"  f{m.frame:<6d} {int(t // 60):d}:{t % 60:05.2f}  "
                f"{m.fighter:<4} {m.family}_{m.target}")

    if show_examples and s.spurious:
        add(f"\nWORST FALSE POSITIVES (first {show_examples} of {len(s.spurious)} FP)")
        for m in s.spurious[:show_examples]:
            t = m.frame / r.fps
            # `m` is a plain Strike (no `.action`) when `preds` is a second
            # FightLabels, i.e. scoring an agreement run rather than pipeline
            # predictions — see cli.py's `agreement` command.
            action = getattr(m, "action", f"{m.family}_{m.target}")
            add(f"  f{m.frame:<6d} {int(t // 60):d}:{t % 60:05.2f}  "
                f"{m.fighter:<4} {action}")

    add("")
    return "\n".join(L)
