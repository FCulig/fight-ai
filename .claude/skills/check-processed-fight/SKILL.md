---
name: check-processed-fight
description: Run the label-free health checks on one processed fight (video integrity, pipeline artifacts, red/blue corner correctness, round-segmentation verdict) and explain what each result means. Use after the pipeline finishes a fight, when a fight's output looks wrong, or before relying on a fight as training or reference data.
argument-hint: "<fight-id>"
arguments: [fight_id]
---

# Check processed fight $fight_id

Run these from `ai/`. None of them need labels, and none of them write anything.

## 1. Look up the fight
```bash
python - <<'EOF'
from sqlalchemy import text
from database import SessionLocal
print(SessionLocal().execute(text("""
    SELECT id, video_path, purpose, state, reported_frames, decoded_frames,
           segmentation_needs_review, segmentation_review_reason
    FROM fights WHERE id = :id"""), {"id": $fight_id}).mappings().first())
EOF
```
If `state='invalid'`, the upload is truncated. Report `reported_frames` against `decoded_frames` and stop, because the pipeline never ran.

## 2. Pipeline artifacts
Run `python -m eval.cli sanity <video_path> --skip-decode`. The upload validator already did the full decode, so drop `--skip-decode` only for a video that bypassed upload. Report every check that doesn't pass.

## 3. Corner correctness
Run `python -m eval.corner_accuracy $fight_id`. This is the only check that catches a red/blue inversion, which stays fully self-consistent.
- `[FAIL]`: the whole fight is inverted.
- `[WARN]`: intermittent swaps the tracker didn't correct. They enter at camera cuts and clinches.
- **No or few decisive frames** means **unverified**, not passed. It is common on ground-heavy footage.

## 4. Round segmentation
- `segmentation_needs_review = true` means the scoreboard didn't corroborate the round list. Quote `segmentation_review_reason`, and note that a labeller must confirm the rounds in Annotate before the fight is used.
- `false` means the clock backed every round.

## 5. Report
Give a short table with one row per check: result, and what to do about it.
