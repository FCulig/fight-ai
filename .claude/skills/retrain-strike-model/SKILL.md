---
name: retrain-strike-model
description: Retrain the skeleton strike model in ai/action_model, decide whether to promote the new checkpoint, re-sweep STRIKE_PROB_THRESHOLD and STRIKE_NMS_SECS, and measure the result. Use when asked to retrain or refresh the strike/action model, or after a batch of new QA-confirmed training labels.
---

# Retrain the strike model

Run everything from `ai/`. `.claude/rules/ai-action-model.md` holds the data rules and the input/output contract.

## 1. Check there is new data
Training uses only QA-confirmed labels (`is_verified IS TRUE`) on `training_data` fights, and training is seeded. With no new confirmed labels since the last run, retraining changes nothing.
```bash
python - <<'EOF'
from sqlalchemy import text
from database import SessionLocal
for r in SessionLocal().execute(text("""
    SELECT e.action, count(*) FROM fight_events e JOIN fights f ON f.id = e.fight_id
    WHERE f.purpose = 'training_data' AND e.source = 'label' AND e.kind = 'point'
      AND e.is_verified IS TRUE
    GROUP BY e.action ORDER BY 2 DESC""")):
    print(r)
EOF
```

## 2. Train without promoting
Run `python -m action_model.train`, optionally with `--device mps`. The model is small, so CPU is fine. It writes `runs/action_model/<timestamp>/{model.pt,report.md,report.json}`.

## 3. Compare with the checkpoint in use
1. Find which run is promoted:
   `shasum action_model/weights/strike_model.pt runs/action_model/*/model.pt`
2. Compare the two runs' `report.md`: best-validation macro-F1 and the per-class numbers. Validation picks the epoch, so its best score is slightly optimistic.
3. Stop here if the new run isn't better.

## 4. Promote
Run `cp runs/action_model/<timestamp>/model.pt action_model/weights/strike_model.pt`. That is exactly what `--promote` does. `load_model` refuses a checkpoint built against a different `action_model/config.py`, so the promoted file must match the committed config.

## 5. Re-sweep the two strike thresholds
They are tuned to one checkpoint's probability calibration. No sweep script is committed, so write a throwaway one in the scratchpad:
1. Rebuild the tracks for the reference fight's `ai_labeled` twin from its stored `fighter_frames`, the way `process_fight` does before it calls `detect_strikes(tracks, fps, scan_spans, model)`.
2. Call `action_model.inference.detect_strikes` across a grid of `threshold` and NMS values. Last time the grid was 0.90–0.99 × 0.3–0.6 s.
3. Score each cell against the reference labels with `eval.score`'s strike matcher.
4. Pick the **middle of the F1 plateau**, not the single best cell.
5. Update `STRIKE_PROB_THRESHOLD` and `STRIKE_NMS_SECS`, and rewrite their comment in `models/constants.py`: grid, plateau, chosen cell, fixture ids.

## 6. Measure and commit
1. Run the `measure-pipeline-change` skill: a new `ai_labeled` upload plus `score-pair --write-db`.
2. Commit the weights, the constants and both runs' numbers together.
3. Update the "Current baseline" table in `.claude/rules/ai-action-model.md`.
