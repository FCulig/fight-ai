import re
import statistics
import subprocess
from typing import List, Optional

from sqlalchemy import text

from app.models.eval_run import EvalRun
from app.services.pipeline_runner import AI_DIR, AI_PYTHON
from app.utils.db import run_db_query

_SCORE_TIMEOUT_S = 60  # a DB read + in-memory matching pass, not a video decode


class InvalidPairing(Exception):
    """Raised when a reference/scored fight pairing doesn't satisfy the real
    accuracy workflow (backend/CLAUDE.md), or when `score-pair` itself fails
    (e.g. the reference fight isn't finished labelling)."""


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Same formulas as ai/eval/score.py's `PRF` properties — the stored
    report blob only carries tp/fp/fn (see EvalRunSummary's docstring)."""
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def _pipeline_versions(session, reference_fight_id: int) -> dict[int, int]:
    """`scored_fight_id` → 1-based pipeline version for one fixture. A fight's
    pipeline never re-runs (backend/CLAUDE.md), so every pipeline version is a
    new `ai_labeled` upload of the reference video: versions are the fixture's
    scored fights in upload (id) order, however many times each was scored.
    `git_sha` can't serve — it's the scorer's HEAD at scoring time, not the
    code that produced the predictions."""
    rows = (
        session.query(EvalRun.scored_fight_id)
        .filter(EvalRun.reference_fight_id == reference_fight_id)
        .distinct()
        .order_by(EvalRun.scored_fight_id)
        .all()
    )
    return {scored_fight_id: i + 1 for i, (scored_fight_id,) in enumerate(rows)}


def _summarize(row: EvalRun, versions: dict[int, int]) -> EvalRun:
    row.pipeline_version = versions[row.scored_fight_id]

    d = row.report["strikes"]["detection"]
    p, r, f1 = _prf(d["tp"], d["fp"], d["fn"])
    row.precision = round(p * 100, 1)
    row.recall = round(r * 100, 1)
    row.f1 = round(f1 * 100, 1)
    row.tp, row.fp, row.fn = d["tp"], d["fp"], d["fn"]

    # Same bias (median signed offset)/jitter (median absolute offset) split
    # as ai/eval/score.py's StrikeScore.offset_bias/offset_jitter properties
    # — a systematic lag to subtract once vs. genuine temporal spread.
    offsets = row.report["strikes"].get("matched_offsets") or []
    row.offset_bias_frames = statistics.median(offsets) if offsets else None
    row.offset_jitter_frames = statistics.median(abs(o) for o in offsets) if offsets else None
    return row


def list_runs(reference_fight_id: int, scored_fight_id: Optional[int] = None) -> List[EvalRun]:
    def _query(session):
        versions = _pipeline_versions(session, reference_fight_id)
        q = session.query(EvalRun).filter(EvalRun.reference_fight_id == reference_fight_id)
        if scored_fight_id is not None:
            q = q.filter(EvalRun.scored_fight_id == scored_fight_id)
        return [_summarize(r, versions) for r in q.order_by(EvalRun.generated_at).all()]

    return run_db_query(_query)


def get_run(run_id: int) -> Optional[EvalRun]:
    def _query(session):
        row = session.query(EvalRun).filter(EvalRun.id == run_id).first()
        if row is None:
            return None
        return _summarize(row, _pipeline_versions(session, row.reference_fight_id))

    return run_db_query(_query)


def list_fixtures() -> List[dict]:
    """Every candidate fixture — a `purpose='reference'` fight with
    `labeled_at` set — with its newest pipeline version's latest scoring, or
    `is_measurable=False` when it has no eval_runs row yet. Deliberately not
    "does any ai_labeled fight exist anywhere" — that would false-positive on
    an unrelated fight; a fixture only becomes measurable once a run has
    actually been recorded against it."""
    def _query(session):
        fights = session.execute(
            text(
                "SELECT id, video_path, labeled_at FROM fights "
                "WHERE purpose = 'reference' AND labeled_at IS NOT NULL "
                "ORDER BY id"
            )
        ).all()
        out = []
        for f in fights:
            # Newest version first, so re-scoring an older version never
            # makes the table report it as the current pipeline.
            latest = (
                session.query(EvalRun)
                .filter(EvalRun.reference_fight_id == f.id)
                .order_by(EvalRun.scored_fight_id.desc(), EvalRun.generated_at.desc())
                .first()
            )
            out.append({
                "reference_fight_id": f.id,
                "video_path": f.video_path,
                "labeled_at": f.labeled_at,
                "is_measurable": latest is not None,
                "latest_run": _summarize(latest, _pipeline_versions(session, f.id)) if latest else None,
            })
        return out

    return run_db_query(_query)


def _validate_pairing(session, reference_fight_id: int, scored_fight_id: int) -> None:
    ref = session.execute(
        text("SELECT purpose, labeled_at FROM fights WHERE id = :id"),
        {"id": reference_fight_id},
    ).first()
    if ref is None:
        raise InvalidPairing(f"reference fight {reference_fight_id} not found")
    if ref.purpose != "reference" or ref.labeled_at is None:
        raise InvalidPairing(
            f"fight {reference_fight_id} is not a labelled reference fixture "
            f"(purpose={ref.purpose!r}, labeled_at={'set' if ref.labeled_at else None})"
        )

    scored = session.execute(
        text("SELECT purpose, state FROM fights WHERE id = :id"),
        {"id": scored_fight_id},
    ).first()
    if scored is None:
        raise InvalidPairing(f"scored fight {scored_fight_id} not found")
    if scored.purpose != "ai_labeled" or scored.state != "completed":
        raise InvalidPairing(
            f"fight {scored_fight_id} is not a completed AI-processed fight "
            f"(purpose={scored.purpose!r}, state={scored.state!r}) — upload the "
            f"source video again with purpose=ai_labeled and wait for it to finish"
        )


_WROTE_ID_RE = re.compile(r"wrote eval_runs row id=(\d+)")


def create_run(
    reference_fight_id: int,
    scored_fight_id: int,
    tolerance_secs: Optional[float] = None,
) -> EvalRun:
    """Validate the pairing, then shell into the ai/ venv to run and persist
    a real `score-pair` pass — this is the "Run scoring" action behind
    Section E's E0 not-measurable state. Synchronous: unlike a pipeline run
    (video decode, minutes), scoring is a DB read plus an in-memory
    Hungarian-matching pass — no polling/SSE needed."""
    run_db_query(lambda session: _validate_pairing(session, reference_fight_id, scored_fight_id))

    cmd = [
        AI_PYTHON, "-m", "eval.cli", "score-pair",
        "--labels-fight-id", str(reference_fight_id),
        "--predictions-fight-id", str(scored_fight_id),
        "--no-sanity", "--write-db",
    ]
    if tolerance_secs is not None:
        cmd += ["--tolerance-override", str(tolerance_secs)]

    result = subprocess.run(
        cmd, cwd=AI_DIR, capture_output=True, text=True, timeout=_SCORE_TIMEOUT_S,
    )
    if result.returncode != 0:
        raise InvalidPairing(
            (result.stderr or result.stdout or "scoring failed").strip().splitlines()[-1]
            if (result.stderr or result.stdout) else "scoring failed"
        )

    m = _WROTE_ID_RE.search(result.stdout)
    if not m:
        raise InvalidPairing("scoring ran but did not report a new eval_runs id")

    run = get_run(int(m.group(1)))
    if run is None:
        raise InvalidPairing("scoring wrote a row that could not be read back")
    return run
