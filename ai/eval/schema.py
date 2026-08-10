"""Ground-truth label format for fight videos.

One JSON file per video, stored in ``eval/labels/<video_stem>.json``. The format
serves double duty: it is the evaluation ground truth *and* the training set for
the skeleton action model that will replace the rule cascade, so strike
attributes are stored decomposed (family / target / landed) rather than as the
pipeline's flat ``jab_head`` strings.

Frames are **1-based**, matching the pipeline's frame-numbering contract
(see ai/CLAUDE.md — the Nth frame of the video is frame N).

Schema
------
```json
{
  "video":      "BATURvsSTAMATOVIC.mp4",
  "fps":        50,
  "frame_count": 8147,
  "labeler":    "filip",
  "labeled_at": "2026-08-06",
  "notes":      "free text",
  "rounds":   [{"round": 1, "start": 1507, "end": 4809}],
  "excluded": [{"start": 4810, "end": 5200, "reason": "replay"}],
  "states":   [{"start": 1507, "end": 1600, "state": "STRIKING"}],
  "strikes":  [{"frame": 1620, "fighter": "red", "family": "jab",
                "target": "head", "landed": true}]
}
```

``excluded`` regions (replays, walkouts, corner rest, camera cuts) are dropped
from every metric — both a predicted and a ground-truth event inside one is
ignored rather than counted as a false positive.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

LABELS_DIR = Path(__file__).parent / "labels"

# --- Taxonomy -------------------------------------------------------------
# Strike families. `punch` is the deliberately unspecific bucket the pipeline
# emits in clinch/ground (clinch_punch / ground_punch) where it does not attempt
# a jab/cross/hook/uppercut split. Labellers should always use a specific family;
# `punch` exists so predictions can be represented faithfully.
FAMILIES = ("jab", "cross", "hook", "uppercut", "elbow", "knee", "kick", "punch")
SPECIFIC_FAMILIES = ("jab", "cross", "hook", "uppercut", "elbow", "knee", "kick")

# Target zones. `unknown` is again a prediction-only value: the pipeline's
# grappling strikes carry no target.
TARGETS = ("head", "body", "leg", "unknown")

FIGHTERS = ("red", "blue")
STATES = ("STRIKING", "CLINCH", "GROUND")

# --- Pipeline vocabulary → (family, target) -------------------------------
# Maps the flat `fight_events.action` strings the pipeline writes onto the
# decomposed label taxonomy, so predictions and ground truth are comparable.
PIPELINE_ACTION_MAP: dict[str, tuple[str, str]] = {
    "jab_head":      ("jab",      "head"),
    "jab_body":      ("jab",      "body"),
    "cross_head":    ("cross",    "head"),
    "cross_body":    ("cross",    "body"),
    "hook_head":     ("hook",     "head"),
    "hook_body":     ("hook",     "body"),
    "uppercut_head": ("uppercut", "head"),
    "uppercut_body": ("uppercut", "body"),
    "head_kick":     ("kick",     "head"),
    "middle_kick":   ("kick",     "body"),
    "low_kick":      ("kick",     "leg"),
    # Grappling strikes carry neither a punch family nor a target zone.
    "clinch_punch":  ("punch",    "unknown"),
    "ground_punch":  ("punch",    "unknown"),
    "clinch_knee":   ("knee",     "unknown"),
    "ground_knee":   ("knee",     "unknown"),
}

# Non-strike `action` values written to fight_events.
STATE_ACTIONS = {"round_start", "round_end", "clinch_initiated", "takedown_initiated"}


class LabelError(ValueError):
    """Raised when a label file fails validation."""


@dataclass
class Strike:
    frame: int
    fighter: str          # red | blue
    family: str           # see FAMILIES
    target: str           # see TARGETS
    landed: Optional[bool] = None

    @property
    def is_specific(self) -> bool:
        """True when family and target are both committed values.

        Grappling predictions are non-specific; they still count for
        event-level detection but are excluded from the family/target accuracy
        denominators so the pipeline is not penalised for a distinction it does
        not attempt to make.
        """
        return self.family in SPECIFIC_FAMILIES and self.target != "unknown"


@dataclass
class Span:
    start: int
    end: int

    def contains(self, frame: int) -> bool:
        return self.start <= frame <= self.end

    @property
    def length(self) -> int:
        return max(0, self.end - self.start + 1)


@dataclass
class Round(Span):
    round: int = 1


@dataclass
class Excluded(Span):
    reason: str = ""


@dataclass
class StateSpan(Span):
    state: str = "STRIKING"


@dataclass
class FightLabels:
    video: str
    fps: int
    frame_count: int = 0
    labeler: str = ""
    labeled_at: str = ""
    notes: str = ""
    rounds: list[Round] = field(default_factory=list)
    excluded: list[Excluded] = field(default_factory=list)
    states: list[StateSpan] = field(default_factory=list)
    strikes: list[Strike] = field(default_factory=list)

    # -- exclusion / round helpers ----------------------------------------

    def is_excluded(self, frame: int) -> bool:
        return any(e.contains(frame) for e in self.excluded)

    def in_any_round(self, frame: int) -> bool:
        return any(r.contains(frame) for r in self.rounds)

    def scored_frames(self) -> set[int]:
        """Frames eligible for scoring: inside a round and not excluded.

        When no rounds are labelled, every non-excluded frame up to
        ``frame_count`` is eligible — this lets a partially-labelled file still
        produce numbers.
        """
        if self.rounds:
            candidate = {f for r in self.rounds for f in range(r.start, r.end + 1)}
        else:
            candidate = set(range(1, self.frame_count + 1))
        return {f for f in candidate if not self.is_excluded(f)}

    def state_at(self, frame: int) -> Optional[str]:
        for s in self.states:
            if s.contains(frame):
                return s.state
        return None

    # -- persistence -------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> "FightLabels":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        labels = cls(
            video=raw["video"],
            fps=int(raw["fps"]),
            frame_count=int(raw.get("frame_count", 0)),
            labeler=raw.get("labeler", ""),
            labeled_at=raw.get("labeled_at", ""),
            notes=raw.get("notes", ""),
            rounds=[Round(**r) for r in raw.get("rounds", [])],
            excluded=[Excluded(**e) for e in raw.get("excluded", [])],
            states=[StateSpan(**s) for s in raw.get("states", [])],
            strikes=[Strike(**s) for s in raw.get("strikes", [])],
        )
        labels.validate()
        return labels

    @classmethod
    def for_video(cls, video: str | Path) -> "FightLabels":
        """Load the label file matching a video path by its stem."""
        path = LABELS_DIR / f"{Path(video).stem}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No label file at {path}. Create one with:\n"
                f"  python -m eval.cli label {video}"
            )
        return cls.load(path)

    def save(self, path: str | Path | None = None) -> Path:
        path = Path(path) if path else LABELS_DIR / f"{Path(self.video).stem}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.strikes.sort(key=lambda s: s.frame)
        self.states.sort(key=lambda s: s.start)
        self.rounds.sort(key=lambda r: r.start)
        self.excluded.sort(key=lambda e: e.start)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)
        return path

    # -- validation --------------------------------------------------------

    def validate(self) -> None:
        errs: list[str] = []

        if self.fps <= 0:
            errs.append(f"fps must be positive, got {self.fps}")

        for i, s in enumerate(self.strikes):
            if s.frame < 1:
                errs.append(f"strikes[{i}]: frame {s.frame} is not 1-based")
            if s.fighter not in FIGHTERS:
                errs.append(f"strikes[{i}]: fighter {s.fighter!r} not in {FIGHTERS}")
            if s.family not in FAMILIES:
                errs.append(f"strikes[{i}]: family {s.family!r} not in {FAMILIES}")
            if s.target not in TARGETS:
                errs.append(f"strikes[{i}]: target {s.target!r} not in {TARGETS}")

        for i, s in enumerate(self.states):
            if s.state not in STATES:
                errs.append(f"states[{i}]: state {s.state!r} not in {STATES}")
            if s.end < s.start:
                errs.append(f"states[{i}]: end {s.end} before start {s.start}")

        # State spans must not overlap — state_at() would be ambiguous.
        ordered = sorted(self.states, key=lambda s: s.start)
        for a, b in zip(ordered, ordered[1:]):
            if b.start <= a.end:
                errs.append(
                    f"state spans overlap: [{a.start},{a.end}] and [{b.start},{b.end}]"
                )

        for i, r in enumerate(self.rounds):
            if r.end < r.start:
                errs.append(f"rounds[{i}]: end {r.end} before start {r.start}")

        if errs:
            raise LabelError(
                f"{len(errs)} problem(s) in labels for {self.video}:\n  "
                + "\n  ".join(errs)
            )

    # -- summary -----------------------------------------------------------

    def summary(self) -> str:
        scored = len(self.scored_frames())
        mins = scored / self.fps / 60 if self.fps else 0
        by_family: dict[str, int] = {}
        for s in self.strikes:
            by_family[s.family] = by_family.get(s.family, 0) + 1
        fam = ", ".join(f"{k}={v}" for k, v in sorted(by_family.items()))
        landed = sum(1 for s in self.strikes if s.landed)
        return (
            f"{self.video}: {len(self.strikes)} strikes ({landed} landed) over "
            f"{mins:.1f} min of scored footage\n"
            f"  rounds={len(self.rounds)} state_spans={len(self.states)} "
            f"excluded={len(self.excluded)}\n"
            f"  families: {fam or '(none)'}"
        )
