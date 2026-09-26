"""Skeleton action model — Stage 2 (plan/04-stage2-model.md).

A small temporal CNN over pose windows that classifies "what is this fighter
doing around frame F" into a strike family (or `none`) plus a target zone.
Trained only on QA-verified hand labels from `purpose='training_data'` fights:

    python -m action_model.train

`inference.py` is the pipeline's strike detector: process_fight loads
`weights/strike_model.pt` and scans every round with it. Promote a new
training run there with `python -m action_model.train --promote`.
"""
