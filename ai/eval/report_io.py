"""JSON persistence for `sanity` and `score` reports.

Every artifact records, beside the scores themselves, the four fields that
make a before/after comparison verifiable instead of an honour system:
`git_sha`, `constants_sha256` (hash of `models/constants.py` — the actual
independent variable), `video`, and `tolerance_frames` (a score at a
different tolerance is not comparable). See plan P2.

`SanityReport`, `Report`, `StrikeScore`, `StateScore`, `RoundScore` and `PRF`
are already dataclasses, so `dataclasses.asdict()` does most of the work —
same as `FightLabels.save()` already relies on for its own nested
dataclasses (`Strike`, `Round`, ...). Two things `asdict()` can't handle:

- `StrikeScore.family_confusion` / `StateScore.confusion`, both keyed by a
  `(str, str)` tuple, which cannot be a JSON object key: joined to
  `"gt>pred"` on write, split back out on read.
- `SanityReport.type_counts` / `.out_of_round_types` are `Counter`s.
  `asdict()` reconstructs dict-typed fields via `type(obj)(pairs)`, but
  `Counter(pairs)` doesn't load `pairs` as `{k: v}` the way `dict()` does —
  it *tallies* each `(k, v)` tuple as one occurrence of that tuple, silently
  turning `{"jab_body": 6}` into `Counter({("jab_body", 6): 1})`. Rebuilt
  from the original object with plain `dict()` instead.
"""

import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .sanity import SanityReport
from .score import Report

CONSTANTS_PATH = Path(__file__).parent.parent / "models" / "constants.py"


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, text=True,
    ).strip()


def _constants_sha256() -> str:
    return hashlib.sha256(CONSTANTS_PATH.read_bytes()).hexdigest()


def _confusion_to_json(confusion: dict[tuple[str, str], int]) -> dict[str, int]:
    return {f"{gt}>{pred}": n for (gt, pred), n in confusion.items()}


def _confusion_from_json(confusion: dict[str, int]) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for key, n in confusion.items():
        gt, pred = key.split(">", 1)
        out[(gt, pred)] = n
    return out


def _envelope(video: str, tolerance_frames: int | None, report: dict) -> dict[str, Any]:
    return {
        "git_sha": _git_sha(),
        "constants_sha256": _constants_sha256(),
        "video": video,
        "tolerance_frames": tolerance_frames,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report": report,
    }


def _write(payload: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return path


# ---------------------------------------------------------------------------
# sanity
# ---------------------------------------------------------------------------

def save_sanity_report(rep: SanityReport, path: str | Path) -> Path:
    """Label-free — there is no matching tolerance, so that field is null."""
    d = asdict(rep)
    d["type_counts"] = dict(rep.type_counts)
    d["out_of_round_types"] = dict(rep.out_of_round_types)
    return _write(_envelope(rep.video, None, d), path)


def load_sanity_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------

def save_report(report: Report, path: str | Path) -> Path:
    d = asdict(report)
    d["strikes"]["family_confusion"] = _confusion_to_json(report.strikes.family_confusion)
    d["state"]["confusion"] = _confusion_to_json(report.state.confusion)
    return _write(
        _envelope(report.video, report.strikes.tolerance_frames, d), path,
    )


def load_report_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    raw["report"]["strikes"]["family_confusion"] = _confusion_from_json(
        raw["report"]["strikes"]["family_confusion"])
    raw["report"]["state"]["confusion"] = _confusion_from_json(
        raw["report"]["state"]["confusion"])
    return raw
