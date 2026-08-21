[← Back to Stage 0 index](02-stage0-labelling.md) · [Plan index](../PLAN.md)

**Depends on:** nothing in Stage 0 strictly. [0c(5)](#0c-5) runs first — before
[0a/0b](02a-upload-tracks.md) — because it is a live data-loss bug, not because
anything in this file requires it. [0c(1)](#0c-1)–[0c(4)](#0c-4) keep their
original place in the chain, after [0a/0b](02a-upload-tracks.md).
**Blocks:** [0d](02c-labelling-ui.md#0d) (labelling UI reads/writes `label_events`, needs [0c(5)](#0c-5)); [0e](02d-label-quality.md#0e) (needs the taxonomy from [0c(3)](#0c-3)/[0c(3b)](#0c-3b)/[0c(4)](#0c-4) settled first); [P4](01-prerequisite.md#p4) (needs [0c(5)](#0c-5)).

---

<a id="0c"></a>
## 0c. Make the labels trainable

Six changes turn the existing annotation feature into a training set. Numbers
are stable IDs (referenced elsewhere as `0c(3)`, `0c(5)`, ...), **not
execution order** — (5) is read and executed first, ahead of (1)–(4) and
ahead of [0a/0b](02a-upload-tracks.md), because it fixes a live data-loss bug
rather than adding a feature:

| Order | # | Change | Size | Status |
|---|---|---|---|---|
| 1 | [5](#0c-5) | Move labels to a `label_events` table | migration + routes | ✅ DONE |
| 2 | [1](#0c-1) | `successForAction` returns `null` instead of `true` | one line | ✅ DONE |
| 3 | [2](#0c-2) | Train only on `LABELING_COMPLETE` fights | export guard | ✅ DONE — gated on `labeled_at`, enforced in `labels_db.build_labels` |
| 4 | [3](#0c-3) | Target zone (head/body) on hand strikes, `Shift`-modified | palette + column | ✅ DONE |
| 5 | [3b](#0c-3b) | Fix `right_hook` hardcoded to "body" | taxonomy + description gen | ✅ DONE |
| 6 | [4](#0c-4) | Split `state_grappling` → `state_clinch` (`f`) / `state_ground` (`g`) | palette + cleanup | ✅ DONE |

[#1](#0c-1) and [#3b](#0c-3b) are one-liners. The rest are migrations plus
wiring.

<a id="0c-5"></a>
### (5) Separate `label_events` table — do this first

Annotations are written into `fight_events`, the same table as pipeline
predictions ([Annotate.tsx:213](../frontend/src/pages/Annotate.tsx) →
[api.ts:95](../frontend/src/services/api.ts)). `process_fight` opens with
`DELETE FROM fight_events WHERE fight_id = :fid`
([fight_processing.py:292](../ai/fight_processing/fight_processing.py)), and
`write_frames_and_rounds` does the same
([:181](../ai/fight_processing/fight_processing.py)) — so even re-running the
*manual* pipeline wipes the labels. **Running the AI pipeline over a labelled
fight — the scoring path — destroys every hand label**, with no warning.
`run_batch` skips labelling states, but single-file mode does not.

**Fix: a separate `label_events` table.** Same principle as the corner-swap
decision in [0a](02a-upload-tracks.md#0a) / [0d](02c-labelling-ui.md#0d) —
predictions and ground truth never live in the same place. The Annotate page
reads and writes only `label_events`; the Player reads only `fight_events`.

```sql
label_events (id, fight_id FK, frame,
              corner,          -- 0=red 1=blue; NULL for state marks
              action,          -- 'jab' | 'left_hook' | 'state_clinch' | 'fight_end' …
              target,          -- 'head' | 'body' | 'leg' | NULL   (0c(3))
              success,         -- NULL for now                     (0c(1))
              description, labeler, created_at)
```

`corner` rather than `fighter_id`: it is what the labeller can actually see, it
is what the model trains against, and it matches `fighter_frames.corner`. The
fighter identity is derivable from the `fights` row when needed.

Migrating the existing Annotate write path off `POST /fights/{id}/events/` is the
bulk of the work — a model class, a service, three routes, and the corresponding
`api.ts` calls.

The third route is the undo path, and it is the easiest to miss: `deleteEvent`
([api.ts:108](../frontend/src/services/api.ts)) calls `DELETE /events/{id}`
([events.py:14](../backend/app/api/routes/events.py)), a **global delete by row
id** with no fight scoping and no notion of label-vs-prediction. Once labels move
it must delete from `label_events` only. Remove or scope the `fight_events`
variant in the same change — left as-is it is a route that can silently delete
pipeline output by guessing an integer.

The cheaper alternative — a `source` column on `fight_events` with every pipeline
`DELETE` scoped to `source='pipeline'` — is ~30 minutes instead of ~2 hours, but
leaves a permanent footgun: any query that forgets the filter silently blends
model output into the training set, and that failure is invisible until it shows
up as degraded accuracy. The separate table makes it impossible by construction.

**→ Once (5) lands, go do [0a/0b — Upload tracks & validation](02a-upload-tracks.md)
next.** Come back here for (1)–(4) afterward; they resume the original chain
and don't need (5) to make sense on their own, but this file reads top to
bottom as (5) → [0a/0b] → (1)–(4).

<a id="0c-1"></a>
### (1) Store `success = null`, not `true`

Landed-vs-missed is **deferred** — the MVP target is "count strikes thrown", which
is a coherent task on its own. But `taxonomy.ts:80` hardcodes `success: true` for
every strike, which records a claim that is not being made: punches that visibly
missed are written to the DB as landed.

Fix: `successForAction` returns `null` for strikes. It costs nothing now and
means the rows are not lying when landed% comes back into scope. The rule that
matters is **consistency** — log every strike thrown, outcome unknown.

**Keep `knockdown` at `true`.** It is in the same `SUCCESS_TRUE_ACTIONS` set
([taxonomy.ts:75](../frontend/src/components/annotate/taxonomy.ts)) but it is not
a default — a knockdown that did not land is not a knockdown. Blanket-nulling the
whole set would erase a claim the labeller genuinely made. Empty the set of the
twelve strike actions and leave `knockdown` in it.

<a id="0c-2"></a>
### (2) Train only on fully-annotated fights

Rather than tracking which frames a human reviewed, a fight becomes training data
only once **fully** annotated. `finish-labeling` sets `labeled_at` and transitions
to `LABELING_COMPLETE`; the export step refuses any fight with
`labeled_at IS NULL`. Gate on `labeled_at`, **not** on `state` — an evaluation
fixture loses its `LABELING_COMPLETE` state the moment it is run through the AI
pipeline (see [0a](02a-upload-tracks.md#0a)).

"Fully annotated" = every round's full span annotated (see the rounds decision
in [0d](02c-labelling-ui.md#0d)).

<a id="0c-3"></a>
### (3) Implement target zone (where the strike lands)

**Capture target; train collapsed.** These are separable decisions and
conflating them is the trap: collapsing a label at training time is free,
splitting one later means re-watching every fight. At ~300 strikes, 12 types × 2
targets ≈ 12 examples per class trains nothing, so the MVP model will collapse
them — but the labels must carry the distinction so it is there when volume
allows.

**Only hand strikes need it.** The kick vocabulary already encodes target
(`calf_kick` / `low_kick` / `middle_kick` / `high_kick`), so target applies to the
six numbered hand strikes plus `elbow`.

**Interaction: a modifier, not an extra keystroke.** Plain key = head (the common
case), `Shift`+key = body. Read `e.code` (`'Digit1'`) together with `e.shiftKey`
in the keydown handler, so it works regardless of the shifted character the
keyboard produces.

**Storage:** a dedicated `target` column on `label_events` (`head` | `body` |
`leg` | `NULL`), not baked into the action string. This mirrors the decomposed
`(family, target)` taxonomy already in `eval/schema.py` and keeps the collapse
decision at training time rather than label time.

⚠️ **`NULL` in the DB, `"unknown"` in the harness.** `schema.py:52` is
`TARGETS = ("head", "body", "leg", "unknown")` — a sentinel string, not a null —
and `score_strikes` skips target grading on `g.target != "unknown"`
([score.py:212](../ai/eval/score.py)). `labels_db.py` must map `NULL → "unknown"`
on the way out, and export must never emit a literal `None` into the JSON.
Getting this wrong makes every un-targeted strike silently score as a target
mismatch rather than being excluded from target accuracy.

<a id="0c-3b"></a>
### (3b) Fix the hardcoded target bug

The palette bakes target into the description prose, inconsistently, and
`right_hook` is hardcoded to *"to the body"*
([taxonomy.ts:35](../frontend/src/components/annotate/taxonomy.ts)) — so **every
right hook to the head is currently mislabelled.** `left_hook` says head,
`right_hook` says body, uppercuts say "on the inside". Once target is a real
column, the description strings must be generated from `action` + `target`
rather than carrying a fixed claim.

✅ **Handedness fixed.** `straight_right` (key `2`) is now `cross` — jab/cross
are lead/rear-relative (matching the pipeline's own `classify_punch_type()`),
so a southpaw's jab (thrown with their right hand) is labelled correctly
without any stance tracking. Hooks/uppercuts stay absolute left/right
(`left_hook`, `right_hook`, ...) — directly observable without judging stance,
and lossless either way since both hands collapse to the same family
(`hook`/`uppercut`) at export time (`labels_db.py`'s `LABEL_FAMILY_MAP`).

<a id="0c-4"></a>
### (4) Split grappling into clinch and ground

The palette has `state_striking` / `state_grappling`; the pipeline has
STRIKING / CLINCH / GROUND and emits different labels per state (`clinch_punch`
vs `ground_punch`), so the distinction is currently neither scoreable nor
trainable.

1. **Palette** ([taxonomy.ts:60-66](../frontend/src/components/annotate/taxonomy.ts))
   — replace the two-item group:
   ```ts
   { key: 'w', action: 'state_striking', name: 'Striking', needsFighter: false, text: () => 'Fight state → STRIKING' },
   { key: 'f', action: 'state_clinch',   name: 'Clinch',   needsFighter: false, text: () => 'Fight state → CLINCH' },
   { key: 'g', action: 'state_ground',   name: 'Ground',   needsFighter: false, text: () => 'Fight state → GROUND' },
   ```
   `g` = ground, `f` = clinch. `f` was free — `1-6, c, l, m, h, e, n, t, d, s, x,
   w, g` were taken, `r`/`b` are corner select, `z` is undo.
2. **Legacy rows** — existing `state_grappling` events are ambiguous. Labelling
   has barely started, so delete them rather than guessing a mapping.
3. **Harness** — no change needed. `schema.py` `STATES` is already
   `("STRIKING","CLINCH","GROUND")` and `predictions.py` already parses
   `FightState.(\w+)` on the pipeline side. `labels_db.py` maps
   `state_clinch → CLINCH` and so on. Only the palette is binary.
4. **Span derivation** — marks are change points; each runs to the next, and the
   last runs to **the end of its round**, not the end of the video.
5. **UI** — `colorForAction` / `iconForAction` already match on
   `action.startsWith('state_')` and work unchanged. Give the three states
   distinct colours in `AnnotationTimeline`.

---

Next: [0d — Labelling UI, remaining pieces](02c-labelling-ui.md)
