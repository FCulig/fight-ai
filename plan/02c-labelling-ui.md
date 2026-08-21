[← Back to Stage 0 index](02-stage0-labelling.md) · [Plan index](../PLAN.md)

**Depends on:** [0c(5)](02b-label-schema.md#0c-5) (`label_events`/`label_spans` tables), [0c(2)](02b-label-schema.md#0c-2) (`labeled_at`), [0c(3)](02b-label-schema.md#0c-3) (target column).
**Blocks:** [0e](02d-label-quality.md#0e) and [0g](02d-label-quality.md#0g) (need a fully-labelled fight to measure against); bulk labelling in general.

---

<a id="0d"></a>
## 0d. Labelling UI — remaining pieces

✅ **DONE.** `label_spans` table + routes, round-bound auto-seeding from AI
segmentation with draggable edges, corner-swap/excluded start/end toggle
spans (`O`/`P` keys) with delete controls, `finish-labeling`'s
fully-annotated gate, and the `labels_db.py` → `eval.cli export` pipeline
(including the `corner_swaps` schema field) are all implemented and verified
end-to-end.

The `Annotate.tsx` page, palette, timeline and undo already exist. Manual-track
videos carry fighter boxes and keypoints but **no predicted events**, so
labelling is already unbiased by construction. What is missing is span
annotation.

**Span schema** — migration in `db/alembic/versions/`:

```sql
label_spans (id, fight_id FK, kind, start_frame, end_frame, value)
```

A strike is a *moment* — those already work, and move to
`POST /fights/{id}/label-events/` in [0c(5)](02b-label-schema.md#0c-5). The
things still missing are *stretches of frames*, all of the shape
`(start, end, what)`, so they share one table with a `kind` column:

| `kind` | example | used for |
|---|---|---|
| `round` | 1507–4809 | human-verified round bounds — defines the annotated region |
| `corner_swap` | 3200–3450 | red/blue are flipped here — see below |
| `excluded` | 3600–3700, "replay" | mid-round replay / camera cut away from the cage |

Fight **state does not need a span kind** — the palette already records it as
change-point events, which is the right representation. It only needs the
clinch/ground split from [0c(4)](02b-label-schema.md#0c-4); the harness derives
spans from those marks at read time.

### Rounds define the annotated region

Everything **outside** a round — intros, walkouts, between-round rest,
post-fight, the whole broadcast wrapper — is simply not training data and not
scored. No separate concept is needed for any of it.

**Seed round bounds from the AI segmentation, but let the labeller adjust them.**
Segmentation is one of the unreliable components being fixed: if it reports a
round starting at frame 1507 when it really starts at 1400, that is 100 frames of
real strikes sitting in a region treated as unlabelled or negative. A human is
already watching, so confirming or nudging a boundary is ~4 keystrokes per fight
— and it yields ground-truth rounds to score segmentation against, which
otherwise do not exist. Unlike strikes, round boundaries are unambiguous, so
seeding from the AI carries no anchoring risk.

`excluded` therefore survives for one narrow purpose: **mid-round replays and
camera cuts away from the cage.** Between-round replays are already outside the
rounds. A rare annotation, but a real one.

"Fully annotated" ([0c(2)](02b-label-schema.md#0c-2)) = every round's full span
annotated. `finish-labeling` should verify that before allowing the transition to
`LABELING_COMPLETE` and setting `labeled_at`.

### Corner override

The labeller **can** override corner assignment, and does it by marking a
`corner_swap` span: "from here to here, red and blue are flipped." A whole-video
flip is just a span covering everything — no special case.

This beats excluding the bad span, because clinch frames are where the pipeline
is worst and therefore the most valuable training data; excluding them discards
exactly what the model most needs.

**Do not mutate `fighter_frames`.** Those rows are pipeline *output*. Correcting
them in place destroys the evidence of how often corner assignment was wrong,
which [Stage 1](03-stage1-artifacts.md) needs to measure. Predictions stay
immutable, corrections are stored as labels, and the flip is applied at export
time when joining labels to keypoints. A metric falls out for free: **fraction
of labelled frames covered by a `corner_swap` span = the pipeline's
corner-assignment error rate** — a *lower bound* on it, strictly, since it
counts only the swaps a human caught. [0g](02d-label-quality.md#0g) measures
that recall and replaces the bound with a real figure.

### How span annotation works

All three kinds are **start/end toggles**: one key at the playhead to open the
span, one to close it. A handful per fight. `round` spans arrive pre-seeded from
segmentation, so the labeller is usually adjusting rather than creating.

**Why state stays as change-points** (already the case, worth preserving): you
do not mark "clinch from 3001 to 3400"; you mark *"clinch starts here"*, then
later *"striking starts here"*, and the span is derived — each mark runs to the
next. This matches how state actually behaves (the fight is always in exactly one
state) and halves the interaction: one keystroke per transition rather than two
per span.

Correction happens on the existing **`AnnotationTimeline`** — add one lane per
span kind, coloured bars, drag the edges to fine-tune. Keyboard marking at the
playhead stays primary; the timeline is for fixing afterwards. Derived state
spans must not overlap; `excluded`, `corner_swap` and `round` may overlap
anything.

**Backend** — follows the established model/service/route layering (mirror
`round.py` + `round_service.py`):

| Method | Path | Note |
|---|---|---|
| `GET` / `POST` / `DELETE` | `/fights/{id}/label-events/` | moved off `fight_events` per [0c(5)](02b-label-schema.md#0c-5) |
| `GET` / `PUT` | `/fights/{id}/label-spans/` | new |

New files: `app/models/label_event.py`, `app/models/label_span.py`, their
services, and `app/api/routes/labels.py`. `POST /fights/{id}/finish-labeling`
already exists and gains the "all rounds fully annotated" check.

**Harness side:** new `ai/eval/labels_db.py` builds a `FightLabels` from
`label_events` + `label_spans`, and `python -m eval.cli export` writes
`eval/labels/*.json` for git so ground truth stays diffable — refusing any fight
with `labeled_at IS NULL` ([0a](02a-upload-tracks.md#0a)). Add `corner_swap` to
`schema.py`, apply it when joining labels to keypoints in `export.py`, and map
the palette's action vocabulary onto `PIPELINE_ACTION_MAP`'s `(family, target)`
decomposition, mapping `target NULL → "unknown"` per
[0c(3)](02b-label-schema.md#0c-3).

**Volume target:** ~300 strikes across 2–3 fights (~10–15 min of round time).
Useful for evaluation from ~50; needed for training from ~300. Labelling
conventions go in `ai/eval/README.md` — log every strike *thrown* with outcome
unknown ([0c(1)](02b-label-schema.md#0c-1)), exclude mid-round replays, and mark
corner swaps rather than trusting the overlay. Plus one round double-labelled
for the agreement ceiling ([0e](02d-label-quality.md#0e)).

---

## Verification — Labelling (0c/0d)

Label part of a round, hit the finish button →
`LABELING_COMPLETE`. Run `python -m eval.cli export <video>`, confirm the JSON
round-trips through `FightLabels.load()` and `eval.cli summary` is sane.

Ten properties most likely to be got wrong, so test each explicitly:

- **Re-running the AI pipeline over a labelled fight leaves the hand labels
  intact** ([0c(5)](02b-label-schema.md#0c-5)) — currently it deletes them.
  Regression-test this one; it is silent data loss on the scoring path.
- **A labelled fight re-run through the AI pipeline is still exportable**
  ([0a](02a-upload-tracks.md#0a)) — `state` goes back to `queued`/`completed`,
  `labeled_at` survives, and `export` accepts it. This is the
  evaluation-fixture path; today it is a one-way door.
- `export` refuses a fight with `labeled_at IS NULL`, and `finish-labeling`
  refuses a fight with an unannotated stretch inside a round.
- Deleting a label through the undo path removes a `label_events` row and
  **cannot** reach `fight_events` ([0c(5)](02b-label-schema.md#0c-5)).
- A `corner_swap` span flips red/blue in the exported training tensor while
  leaving the underlying `fighter_frames` rows untouched.
- Only frames inside `round` spans reach the training set — intros, walkouts and
  between-round rest are absent from both the positive and negative samples.
- `Shift`+`1` records `jab` / `body` and plain `1` records `jab` / `head`, on a
  keyboard layout where `Shift`+`1` produces `!` ([0c(3)](02b-label-schema.md#0c-3)
  reads `e.code`).
- Every logged strike has `success = null` — no row claims "landed" — while a
  logged `knockdown` still records `success = true`
  ([0c(1)](02b-label-schema.md#0c-1)).
- `eval.cli agreement` on a double-labelled round returns the same F1 when the
  two passes are swapped — the check that the report is not silently asymmetric.
- `score` prints the ceiling beside the F1, and declines to when the agreement
  file's tolerance differs from the current run's.
- Two strikes 0.2s apart in a labelled combination, with the first missed by the
  pipeline, score as 1 TP + 1 FN + 1 FP — not 2 TP by shift-matching
  ([0f](02d-label-quality.md#0f)).

---

Next: [0e/0f/0g — Label quality, tolerance, corner-swap recall](02d-label-quality.md)
