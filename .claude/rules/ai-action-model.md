---
paths:
  - "ai/action_model/**"
---

# Strike action model (`action_model/`, design in `plan/04-stage2-model.md`)

This is the pipeline's **only** strike detector. It replaced the hand-tuned rule cascade, which was deleted on 2026-09-26. Don't add rules back on top of it.

## Data
- **Train** only on `purpose='training_data'` labels with `is_verified IS TRUE`.
- **Validate** only on `purpose='reference'` fights, never on a slice of a training fight. Training keeps the best-validation epoch.
- `dataset.py` joins `fight_events(fight, corner)` → `fighter_frames` windows **without** applying `corner_swap` spans, because both corners are track slots (see root CLAUDE.md).

## Train and promote
Use the `retrain-strike-model` skill. `weights/strike_model.pt` is the committed file the pipeline loads. Every retrain must re-sweep `STRIKE_PROB_THRESHOLD` and `STRIKE_NMS_SECS`, because they are tuned to one checkpoint's probability calibration.

## Contract
- **Input:** a 1.2 s window of 31 samples at a fixed 25 Hz, so 24 and 50 fps fights look the same. It holds the attacker's and the opponent's 17 raw keypoints, centred on the attacker's torso, divided by `get_fighter_scale`, and mirrored so the opponent is on the right.
- `windows.py` builds windows for **both** training and inference. Keep it as one implementation so the two can't drift apart. `load_model` refuses a checkpoint built against a different `config.py`.
- **Output:**
  - family: `none`, jab, cross, hook, uppercut, kick or knee. Families are hand-agnostic, and jab/cross mean lead/rear.
  - target: head, body or leg.
- **Detection** (`inference.detect_strikes`):
  - Scans every round minus replays, for both fighters, one window per 1/25 s.
  - Peaks of `1 − P(none)` at or above `STRIKE_PROB_THRESHOLD` become strikes.
  - Each strike suppresses weaker peaks from the same fighter within `STRIKE_NMS_SECS`.

## Current baseline
Reference fight 60 against its `ai_labeled` twin 62 (`score-pair`, ±0.24 s):

| Detector | P | R | F1 | Family | Target |
|---|---|---|---|---|---|
| Rule cascade | 57.1% | 37.0% | 44.9% | 53.6% | 61.4% |
| Strike model | 48.2% | 69.2% | 56.8% | 53.2% | 84.4% |

The thresholds were tuned on that same fight, and there is no second reference fight yet, so these numbers are optimistic.
