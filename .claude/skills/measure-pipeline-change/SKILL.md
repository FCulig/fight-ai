---
name: measure-pipeline-change
description: Measure whether a pipeline change improved strike or fight-state accuracy, by scoring a fresh ai_labeled re-upload of a reference video against that reference fight's hand labels (eval.cli score-pair). Use before committing any change to the fight-state/strike constants in ai/models/constants.py, to ai/fight_processing logic, or to the strike model weights.
argument-hint: "[reference-fight-id]"
---

# Measure a pipeline change

A fight's pipeline never re-runs. Each pipeline version is therefore a **new `ai_labeled` upload of a reference video**, scored against the reference fight's hand labels across the two fight IDs. Run every command below from `ai/`.

## 1. Check that this procedure applies
- **Applies to:** the `constants.py` block from `FIGHT_STATE_SMOOTHING_WINDOW_SECS` to `HEAD_ABOVE_SHOULDER_RATIO`, anything in `fight_processing/`, and `action_model/weights/strike_model.pt`.
- **Segmentation or `SCOREBOARD_*` changes:** skip `score-pair`. Validate them as `.claude/rules/ai-segmentation.md` and `ai-scoreboard.md` describe, then do step 4 only.

## 2. Find the fixture and its baseline
```bash
python - <<'EOF'
from sqlalchemy import text
from database import SessionLocal
db = SessionLocal()
for r in db.execute(text("""
    SELECT f.id AS reference, f.video_path, e.scored_fight_id, e.id AS run, e.generated_at
    FROM fights f LEFT JOIN eval_runs e ON e.reference_fight_id = f.id
    WHERE f.purpose = 'reference' AND f.labeled_at IS NOT NULL
    ORDER BY f.id, e.id""")):
    print(r)
EOF
```
- **Baseline:** the most recent scored twin for that reference. If the latest twin has no `eval_runs` row yet, create one:
  `python -m eval.cli score-pair --labels-fight-id <reference> --predictions-fight-id <twin> --write-db`
- **Ignore bad old rows:** any row from before 2026-09-14 with `tp + fp = 0` came from a since-fixed bug in `eval/predictions.py`.

## 3. Produce and score the new version
1. Make the change and leave it uncommitted. The backend spawns a fresh `main.py` for each upload, so no restart is needed.
2. Upload the reference fight's source video again as `ai_labeled`. Either use FightList → Upload → **AI annotation**, or run:
   `curl -F file=@<video_path> -F purpose=ai_labeled http://127.0.0.1:8000/fights/upload`
   The upload gets its own `video_path` (with a `_2`/`_3` suffix) and a new fight id.
3. Wait for `state='completed'`. This is the full pipeline, and it runs about 11× slower on CPU than on MPS.
4. Score the new twin:
   `python -m eval.cli score-pair --labels-fight-id <reference> --predictions-fight-id <new twin> --write-db`
   Alternatively, use the Accuracy page's **Run scoring**. It shows every version of the fixture side by side.

## 4. Run the label-free checks on the new fight
Run `python -m eval.cli sanity <new twin's video_path> --skip-decode` and `python -m eval.corner_accuracy <new twin id>`. The `check-processed-fight` skill explains how to read both.

## 5. Report
- Compare the before and after reports' **STRIKE DETECTION** (P/R/F1, family, target) and **FIGHT STATE** sections. Put both sets of numbers in the commit message.
- Never pass `--tolerance-override` when comparing. The pinned tolerance is what makes runs comparable.
- The thresholds were tuned on the one reference fight there is, so read gains as optimistic. A regression on it is still a regression.
