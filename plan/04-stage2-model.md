[← Back to plan index](../PLAN.md)

**Depends on:** [Stage 0](02-stage0-labelling.md) for labelled training data (`ai/eval/export.py` joins to `label_events`/`label_spans`). Benefits from, but does not strictly require, [Stage 1](03-stage1-artifacts.md)'s fixes.
**Blocks:** nothing downstream — this is the last stage.

---

## Stage 2 — Skeleton action model

✅ **DONE (2026-09-26).** [`ai/action_model/`](../ai/action_model/) is the
pipeline's only strike detector. It trains on QA-verified (`is_verified IS TRUE`)
labels from `training_data` fights and validates on `reference` fights only.
Step 3 shipped as a **replacement, not an A/B flag**: the rule cascade
(`detect_strikes` and its constants) was deleted at the owner's request.
Reference fight 60, strike F1 went from 44.9% to 56.8% and target accuracy from
61.4% to 84.4%; family accuracy is flat (53.6% → 53.2%). Not done: the
fight-state head, because no state labels have been QA-verified, so
`determine_fight_state` still decides state.

Detection → tracking → pose is the right foundation; keep it. Replace the rule
cascade on top.

<a id="st2-1"></a>
1. **`ai/eval/export.py`** — windowed training tensors. `fighter_frames.keypoints`
   is already stored as JSONB, so it joins to `label_strikes` directly. Window
   ~1s centred on the labelled frame; both fighters' 17 joints; normalise by
   centring on the attacker's torso midpoint and dividing by fighter scale.
<a id="st2-2"></a>
2. **Model** — ST-GCN or a small temporal CNN / transformer. Two heads: strike
   class (family × target + `none`) and fight state. The model learns the
   hysteresis, the head/body split, and clinch-vs-pummel from data instead of
   from 40 constants.
<a id="st2-3"></a>
3. **Inference module** — drop-in replacement behind the existing
   `detect_strikes` / `determine_fight_state` signatures so `process_fight` does
   not change shape. Keep the rule cascade behind a flag for A/B via the harness.

Depth remains invisible to a 2D pose model, so landed-vs-missed will stay the
weakest output. Expect it to improve from the fixed recoil window
([Stage 1 step 5](03-stage1-artifacts.md#st1-5)) before the model helps.

---

Next: [Also worth doing](05-also-worth-doing.md)
