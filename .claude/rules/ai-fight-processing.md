---
paths:
  - "ai/fight_processing/**"
  - "ai/models/FightState.py"
  - "ai/eval/predictions.py"
---

# Fight processing (`process_fight`, `write_frames_and_rounds`)

## Writes
- **One transaction, idempotent.** It deletes this fight's `fight_events WHERE source='prediction'`, `fighter_frames` and `rounds`, bulk-inserts, and calls `db.flush()` every `_FRAME_BATCH_SIZE` rows to free memory. `flush` doesn't end the transaction. One `db.commit()` at the end means every row lands or none does. Never widen the `fight_events` delete beyond `source='prediction'`, because hand labels share the table.
- `fighter_frames` are written for the whole video. State and strike detection run only **inside detected rounds and outside `excluded_ranges`**, which skips walkouts, breaks, the post-fight wrapper and replays.
- `fighter_id` is resolved from corner through the fights row's `red_fighter_id`/`blue_fighter_id`, and is NULL when corners are unassigned. Pass `description` as `None` on every prediction. The pipeline can't emit `fight_end`.

## Fight state (`determine_fight_state`): STRIKING, CLINCH or GROUND
- **Proximity:** torso-rect distance divided by average fighter scale. At or above `DISTANCE_GRAPPLING_RATIO` means `STRIKING`. Below it, the fighters are entangled. If the distance or either scale is unusable, the frame yields no candidate. It must never read as "far apart".
- **Posture** (`is_fighter_grounded`): when entangled, it's `GROUND` if *either* fighter is grounded, otherwise `CLINCH`. The primary signal is torso tilt > `TORSO_VERTICAL_ANGLE_THRESHOLD`. The backup is head→ankle span divided by scale < `GROUND_VERTICAL_SPAN_RATIO`, used only when the nose and both ankles are confident. A hallucinated ankle in a standing clinch otherwise reads as grounded.
- **Smoothing:** a majority vote over `FIGHT_STATE_SMOOTHING_WINDOW_SECS`, and a transition commits only after `FIGHT_STATE_MIN_DWELL_SECS`.
- `GRAPPLING_STATES = {CLINCH, GROUND}` is the "grappling" test everywhere.

## Frame usability (`frame_usable`)
This gates the state machine and the recoil/hip history:
- Both fighters must be detected.
- In `STRIKING`, only the **core trunk joints** (`STRIKING_CORE_KEYPOINT_INDICES`) must be confident. Requiring all 15 joints dropped about 95% of standing frames.
- In grappling, each fighter needs at least `GRAPPLING_MIN_VISIBLE_KEYPOINTS` confident joints.

The strike model is **not** gated by `frame_usable`. It handles missing joints itself.

## Strikes
Detection lives in the action model (see `ai-action-model.md`). This module maps the results and judges landed/missed.
- `_strike_action`:
  - Punches map to `{family}_{head|body}`.
  - Kicks map to `head_kick`, `middle_kick` or `low_kick`.
  - Knees map to `clinch_knee` or `ground_knee`.
  - Punches during CLINCH/GROUND map to `clinch_punch` or `ground_punch`, because no verified label is a grappling punch, so the model's family there is untrained.
- **Landed** (`_landed`) is a recoil proxy. The strike counts as landed if the defender's head moves faster than `RECOIL_VELOCITY_RATIO` × scale per second within `RECOIL_LOOKAHEAD_SECS`. It is `None` if the head isn't readable within 4× the lookahead, and always `None` for grappling strikes. No labels carry landed/missed yet, so this is **unmeasured**.
- One-Euro smoothing (`make_keypoint_smoother`) feeds only the recoil check and the takedown-initiator hip history. The strike model reads **raw** keypoints, which is what it was trained on. Joints below `KEYPOINT_MIN_CONFIDENCE` pass through without updating the filter state.

## Events written (`source='prediction'`, `kind='point'`)
- **Strike:** `action` as mapped above, `fighter_id` = the attacker, `success` = True/False/None.
- **State change:** `state` = STRIKING/CLINCH/GROUND, `action` = `clinch_initiated`, `takedown_initiated` or NULL, `fighter_id` = the initiator or NULL.
- **Round boundary:** `action` = `round_start` or `round_end`.

`eval/predictions.py` reads these columns directly, and takes a strike's corner from `fighter_id` against the fights row.
