[← Back to plan index](../PLAN.md)

**Depends on:** [Prerequisite P1–P3](01-prerequisite.md) complete.
**Blocks:** [Stage 1](03-stage1-artifacts.md) steps 6 & 8 (need the labelled set); [P4](01-prerequisite.md#p4) (needs [0c(5)](02b-label-schema.md#0c-5)); [Stage 2](04-stage2-model.md) (needs labelled training data).

---

## Stage 0 — The labelling framework

This stage is split into five sub-chunks, in execution order. **[0c(5)](02b-label-schema.md#0c-5)
goes first, ahead of the file it lives in** — it closes a live data-loss bug
rather than adding a feature, so it jumps the queue instead of waiting for its
turn inside 0c. After that the original chain resumes: upload track →
remaining schema changes → UI → quality measurement. Work top to bottom.

| Order | Sub-chunk | File | Covers | Depends on | Status |
|---|---|---|---|---|---|
| 1 | [0c(5)](02b-label-schema.md#0c-5) | [Label schema](02b-label-schema.md) | Move labels off `fight_events` into their own `label_events` table — closes the bug where running the AI pipeline over a labelled fight silently destroys the labels | Prerequisite only | ✅ DONE |
| 2 | 0a/0b | [Upload tracks & validation](02a-upload-tracks.md) | Two upload tracks, `labeled_at` marker, full-decode validation, pid handoff | Prerequisite only — sequenced after [0c(5)](02b-label-schema.md#0c-5) by recommendation, not a hard technical dependency | ✅ DONE |
| 3 | 0c(1–4) | [Label schema](02b-label-schema.md) | The remaining changes that make the annotation feature trainable — `success=null`, `labeled_at` gate, target zone, clinch/ground split | 0a/0b | ✅ DONE |
| 4 | 0d | [Labelling UI](02c-labelling-ui.md) | Span annotation (`label_spans`), round bounds, corner-swap override, backend routes | 0c | ✅ DONE |
| 5 | 0e/0f/0g | [Label quality](02d-label-quality.md) | Double-labelling ceiling, matching-tolerance derivation, corner-swap recall measurement | 0d + one fully labelled fight | ✅ tooling built (`agreement`, `inject-swap`, `corner-swap-recall`) · ⏳ not yet run for real — no fight has been labelled yet |

⚠️ **Why [0c(5)](02b-label-schema.md#0c-5) jumps the queue:** annotations are
written into `fight_events`, the same table `process_fight()` opens with
`DELETE FROM fight_events WHERE fight_id = :fid` and rewrites. Any manual
labelling done before this lands is one pipeline re-run away from silent,
total loss — this is a live, confirmed risk (the same `DELETE` was observed
firsthand against this project's `fight_events` table during the P3 baseline
capture), not a hypothetical. Land it before touching anything else in this
stage, including 0a/0b.

---

Next: [Stage 1 — Fix the artifacts](03-stage1-artifacts.md)
