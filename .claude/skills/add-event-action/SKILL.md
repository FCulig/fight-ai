---
name: add-event-action
description: Checklist for adding, renaming or removing a fight_events action across frontend and ai — a new strike, grappling or outcome label in the Annotate palette, or a new action the pipeline writes. Use whenever an action string is added or changed, because the vocabulary is mirrored in several lookup tables that nothing checks against each other.
---

# Add or change an event action

`action` is free text (`String(50)`) with no DB constraint, so a missed table fails silently. The symptoms are a wrong category or colour, a strike missing from stats, or a label dropped from training or eval. No migration is needed.

## A. A label action (Annotate palette)
1. **`frontend/src/components/annotate/taxonomy.ts`**: add a `ToolItem` to the right `TOOL_GROUPS` group with `key`, `action`, `name`, `needsFighter`, `text`, and either `hasTarget` (hand strikes: Shift+key = body) or `fixedTarget` (kicks).
   - The key must be unused and must not collide with `PLAYBACK_KEYS`, `EDIT_KEYS` or `SPAN_KEYS`.
   - The palette button, shortcut, legend, `KEYMAP` and `ACTION_TO_TOOL` then follow automatically.
   - An outcome that implies success goes in `SUCCESS_TRUE_ACTIONS`. Strikes never do.
2. **`frontend/src/utils/eventTaxonomy.ts`**: category, colour and icon come from prefix rules. Confirm the new action lands in the right category, and add a rule if it doesn't.
3. **`frontend/src/utils/trainingDataTaxonomy.ts`**:
   - Every `needsFighter` item becomes a Training Data QA class unless it is listed in `NOT_A_CLASS`.
   - A strike goes in `FAMILY_BY_ACTION`.
   - Check that `reclassifyPayload()` derives the right `target`/`success` for it.
4. **`ai/eval/labels_db.py` `LABEL_FAMILY_MAP`**: add the strike with the same family as `FAMILY_BY_ACTION`. Only families listed in `ai/action_model/config.py` `CLASSES` are trained. Others, such as `elbow`, are exported for eval only.
5. **New model family?** Changing `CLASSES` makes `load_model` refuse the current checkpoint. Retrain (see the `retrain-strike-model` skill) before this change ships.
6. **`frontend/src/utils/liveStats.ts`**: update the target mapping and the clinch/ground sets if it should count in FIGHT STATISTICS.

## B. A prediction action (written by the pipeline)
1. **`ai/fight_processing/fight_processing.py`**: `_strike_action` or the event-writing code.
2. **`ai/eval/schema.py` `PIPELINE_ACTION_MAP`**: map it to `(family, target)`, or eval can't compare it with labels.
3. **`frontend/src/utils/describeEvent.ts`**: add the prediction's display text.
4. **`eventTaxonomy.ts` and `liveStats.ts`**, as in A.
5. Measure it with the `measure-pipeline-change` skill.

## C. Before finishing
Grep for an existing sibling action to catch any table this list missed:
`git grep -n "left_uppercut" -- ai frontend/src`
Every hit should now have a line for the new action, or a reason not to.
