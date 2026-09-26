"""Skeleton action model — Stage 2 (plan/04-stage2-model.md).

A small temporal CNN over pose windows that classifies "what is this fighter
doing around frame F" into a strike family (or `none`) plus a target zone.
Trained only on QA-verified hand labels from `purpose='training_data'` fights:

    python -m action_model.train

Nothing here is imported by the pipeline yet — the drop-in replacement for
`detect_strikes` (plan step 3) is a follow-up.
"""
