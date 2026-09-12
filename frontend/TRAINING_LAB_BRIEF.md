# Training Lab — design brief

> **For Claude Design.** Paste this whole file. It describes a new page for the
> Fight.AI web app: a dashboard over hand-labelled training data and the
> pipeline's measured accuracy. Every number under "Sample" is **illustrative** —
> realistic in shape, modelled on the fights in this repo, not a live snapshot.
> The visual language must match the existing app (§14).

## 1. Context

Fight.AI turns MMA fight video into structured events. A Python pipeline detects
both fighters, tracks them, estimates 17-point pose skeletons, assigns red/blue
corners, reads the scoreboard to find rounds, then runs a hand-tuned rule cascade
that emits strikes (`jab_head`, `ground_punch`, …) and fight state
(STRIKING / CLINCH / GROUND).

That rule cascade is being replaced by a trained skeleton action model, which is
blocked on **labelled data**. A human watches a fight in the **Annotate** page and
logs every strike, state change, takedown, round boundary, corner swap and
excluded stretch. The target is **~300 labelled strikes across 2–3 fights**
(~10–15 min of round time) before training; ~50 is already useful for evaluation.

A labelled fight becomes one of two things, never both:

- **Training fight** — its labels and skeletons feed the model.
- **Evaluation fixture** — it is re-run through the full AI pipeline and the
  predictions are scored against the labels (strike precision/recall/F1, fight
  state, rounds).

Today all of this lives in CLI output (`python -m eval.cli summary | score |
sanity`). The Training Lab puts it on one page.

## 2. Users and the questions the page answers

Users: 1–3 pipeline developers who label fights and change the pipeline.
Technical, data-literate, rightly suspicious of any unqualified number.
Desktop-first.

In priority order, the page must answer:

1. **How much labelled data do we have, of which kinds, and how far are we from
   the 300-strike target?**
2. **Is it trainable?** Which classes are starved? Is one fight dominating?
3. **What is the pipeline's current accuracy — and how far can that number be
   trusted?**
4. **Did the last pipeline change help or hurt?** Against the frozen baseline and
   the previous version.
5. **Is the ground truth itself healthy?** Rounds confirmed, swaps marked, no open
   spans, source video still on disk, exported to git.
6. **What should I do next?** Finish labelling X, export Y, re-run Z as a fixture,
   fix a failing check.

**10-second test:** someone opening the page cold can say "213 of 300 strikes,
ground punches dominate, strike F1 isn't measurable yet because no labelled fight
has predictions."

## 3. Honesty rules — design these in, they are the point of the page

This project has been misled repeatedly by numbers that looked fine. Each rule
matches a real trap in this codebase.

1. **Every metric shows its n and its provenance.** F1 always travels with the
   ground-truth strike count, the fixture count, the matching tolerance
   (±0.25 s = ±12 frames at 50 fps) and the pipeline version (short git SHA +
   constants hash). No bare percentages.
2. **"Not measured", "Not scorable" and "Unverified" are first-class states —
   never 0%, never blank.** A labelled fight processed on the manual track has no
   predictions: its F1 is *not scorable*, not 0%.
3. **Circular metrics are visibly flagged, or hidden.**
   - *Corner read-back* (the labeller's corner matches the pipeline's on matched
     strikes) reads ~100% by construction: the labeller clicks the overlay box the
     pipeline drew, so a tracker swap is copied into the label. Never call it
     "attribution accuracy". It sits behind a `Circular` badge.
   - *Round IoU* is circular when the labelled round spans were auto-seeded from
     the pipeline's own output and never edited. Show `Seeded — not verified`
     instead of an IoU.
4. **Lower bounds say so.** Corner-swap coverage (share of round time inside
   labeller-marked swap spans) is a *lower bound* on corner-assignment error until
   labeller swap recall is measured. Render it as `≥ 4.4%`.
5. **Low evidence is not a pass.** A label-free corner check with few decisive
   frames is `Unverified`, even when it reads 100%.
6. **Accuracy is shown against the human ceiling.** With a double-labelling
   agreement measurement: `F1 56.7% · human ceiling 91.4%`. Without one:
   `ceiling not measured`. An F1 with no ceiling can't be judged good or bad.
7. **Fight state leads with stability, not per-frame accuracy.** Per-frame
   accuracy is dominated by the most common state and stays high while the state
   machine visibly flaps. Lead with transitions/min and median dwell, truth vs
   predicted.
8. **Numbers are only comparable at the same tolerance and on the same fixture
   set.** A trend line breaks (gap plus a note) wherever either changes.

## 4. Placement and layout

- **Nav:** add **Lab** to the header after Analysis and Library (the app already
  uses "Lab Report" wording). Route `/lab`. Page title "Training Lab", subtitle
  "Labelled data and pipeline accuracy".
- **Width:** max 1440 px, centred, 22 px / 30 px page padding — same as the Player.
- **One scrolling page**, with a compact sticky section index on wide screens:
  1. Filter row
  2. **A** Overview
  3. **B** Annotated events
  4. **C** Spans & coverage
  5. **D** Fight ledger
  6. **E** Pipeline accuracy
  7. **F** Pipeline health (label-free)
  8. **G** Label quality & action queue
  - A reference drawer (taxonomy mapping, §13) opens from section B's header.
- **Grid:** 12 columns, 14 px gaps. Every section is a glass card (§14).

## 5. Filter row

One left-aligned row under the page title. It scopes everything below it.

- **Fights:** pills `All labelled` · `Training` · `Evaluation fixtures` ·
  `In progress`, plus a multi-select fight combobox.
- **Labelling period:** `All time` · `Last 7 days` · `Last 30 days`. Affects the
  activity chart and the "added" deltas only.
- **Pipeline version** (scopes E and F): dropdown of scored versions, newest first,
  rows like `807c1b6 · constants a41f… · 10 Sep`; `Working tree (uncommitted)`
  flagged with a dot.
- Far right: `Refreshed 2 min ago` and a refresh icon button. A refetch keeps the
  previous render at reduced opacity — no skeleton flash, no layout jump.

## 6. A · Overview

One **hero card** and a row of stat tiles. The hero is training-set progress — the
user's first question. Accuracy is the most prominent tile, with detail in E.

**Hero card — Training set progress** (~5 columns)

- Hero figure **213 / 300 strikes**, in the app's stat face.
- A meter beneath it: fill = strikes labelled, track = a lighter step of the same
  hue. Ticks at **50** ("useful for evaluation") and **300** ("training target").
- `71% · 87 to go · ~26 days at the last-14-day pace (3.4 strikes/day)`
- `18.4 min of labelled round time across 3 fights`

**Stat tiles**

| Tile | Sample value | Sub-line |
|---|---|---|
| Label events | 250 | +59 in the last 14 days · includes state marks |
| Fights | 3 labelled | 2 finished · 1 in progress · 1 exported to git |
| Largest-fight share | 67% | DRAGOJEVIC vs HONDA — warning above 50%: the model would mostly learn one bout |
| Strike detection F1 | `Not scorable` | "No evaluation fixture yet" · populated: `56.7%` · P 62.9 · R 51.7 · n = 118 · ceiling not measured |
| Sanity checks | 7 / 9 | latest AI run · JURIC vs NOGUEIRA |

Clicking a tile scrolls to its section.

## 7. B · Annotated events — "what have we labelled?"

The core section. Card header: title, total (`213 strikes · 37 other events`), a
view toggle, a `Table` toggle, and the reference-drawer icon.

### B1. Events by type

**Form:** a horizontal bar list, one row per palette action, grouped under the
Annotate palette's own group names. All bars share one hue (cyan): the row label
carries identity, so no per-row colours. Each row:

`[key] Label ········ [bar] count · share · R|B split · trains-as · scored status`

- **Key chip** — the Annotate shortcut (`1`, `c`, `v` …) in a small inner tile, so
  labellers can map the row to the palette. Group note for hand strikes:
  "⇧ = body".
- **R|B split** — a thin two-segment bar under the main bar (red / blue, 2 px
  surface gap) or `R 19 · B 14`. Tooltip: "Corner = the overlay box the labeller
  clicked (a track slot), not a named fighter."
- **Trains-as chip** — the export family: `hook`, `kick · leg`,
  `punch · non-specific`.
- **Scored status** (icon + label):
  - `Scored` — has a pipeline counterpart
  - `Always a miss` — elbow: the pipeline has no elbow detector, so every labelled
    elbow is a false negative
  - `Captured only` — exported, not yet scored (takedown landed)
  - `Not exported` — takedown attempt/defended, submission, knockdown, fight end
- **Minimum-examples marker** — a hairline at the per-class minimum (default 25,
  editable from the card menu). Rows under it get a small `Low` warning chip.

**View toggle:** `Palette actions` (default) · `Training classes` (collapsed to
export families: jab, cross, hook, uppercut, elbow, knee, kick, punch) ·
`By fight` (small multiples, one mini list per fight, shared x-scale).

**Sample — palette actions, all labelled fights**

| Group | Action | Key | Count | R | B | Trains as | Status |
|---|---|---|---|---|---|---|---|
| Strikes | Jab | 1 | 33 | 19 | 14 | jab | Scored |
| | Cross | 2 | 20 | 11 | 9 | cross | Scored |
| | Left hook | 3 | 9 | 5 | 4 | hook | Scored |
| | Right hook | 4 | 14 | 8 | 6 | hook | Scored |
| | Left uppercut | 5 | 2 | 1 | 1 | uppercut | Scored |
| | Right uppercut | 6 | 3 | 2 | 1 | uppercut | Scored |
| | Calf kick | c | 8 | 3 | 5 | kick · leg | Scored |
| | Low kick | l | 7 | 4 | 3 | kick · leg | Scored |
| | Middle kick | m | 5 | 2 | 3 | kick · body | Scored |
| | High kick | h | 3 | 1 | 2 | kick · head | Scored |
| | Elbow | e | 3 | 3 | 0 | elbow | Always a miss |
| | Clinch knee | n | 5 | 2 | 3 | knee · non-specific | Scored |
| Ground & pound | Clinch punch | u | 10 | 6 | 4 | punch · non-specific | Scored |
| | Ground and pound | v | 87 | 49 | 38 | punch · non-specific | Scored |
| | Ground knee | j | 4 | 2 | 2 | knee · non-specific | Scored |
| Grappling | Takedown attempt | t | 5 | 3 | 2 | — | Not exported |
| | Takedown landed | y | 4 | 3 | 1 | takedown | Captured only |
| | Takedown defended | d | 2 | 1 | 1 | — | Not exported |
| | Submission | s | 1 | 1 | 0 | — | Not exported |
| Outcome | Knockdown | x | 1 | 1 | 0 | — | Not exported |
| Fight state | Striking | w | 10 | — | — | state span | Scored |
| | Clinch | f | 6 | — | — | state span | Scored |
| | Ground | g | 6 | — | — | state span | Scored |
| Other | Fight end | modal | 2 | — | — | — | Not exported |

### B2. Training classes — family × target

**Form:** a heatmap. Rows = families, columns = head · body · leg · non-specific,
each cell showing its count. One sequential hue (cyan ramp), count text in white
or ink chosen by the cell's luminance. Cells under the minimum get a small warning
tick in the corner. `—` cells are impossible combinations (drawn empty, not zero).

| Family | head | body | leg | non-specific | Total |
|---|---|---|---|---|---|
| jab | 26 | 7 | — | — | 33 |
| cross | 16 | 4 | — | — | 20 |
| hook | 18 | 5 | — | — | 23 |
| uppercut | 4 | 1 | — | — | 5 |
| elbow | 2 | 1 | — | — | 3 |
| kick | 3 | 5 | 15 | — | 23 |
| knee | — | — | — | 9 | 9 |
| punch | — | — | — | 97 | 97 |
| **Total** | **69** | **23** | **15** | **106** | **213** |

Caption: "107 specific · 106 non-specific. At ~300 strikes the first model will
collapse target (and probably family) — the labels keep the distinction for
later."

### B3. Strikes by fight state

**Form:** a 100% stacked horizontal bar per training family plus one overall bar.
Segments: STRIKING · CLINCH · GROUND · before first state mark, in the state
colours from §14. Legend always shown; direct labels only on segments wide enough
to hold them.

Sample overall: STRIKING 92 · CLINCH 21 · GROUND 98 · no state yet 2.

Callout: "46% of strikes happened on the ground; 83 of the 87 ground-and-pound
punches come from one fight."

### B4. Labelling activity

**Form:** a column chart of label events per day (last 30 days), one hue. The
tooltip breaks a day down by fight. Cumulative strikes against the 300 target go
in a separate small line chart underneath, sharing the x-axis — never a second
y-axis on the same plot.

Sample: 15 Aug 16 · 19 Aug 38 · 20 Aug 52 · 21 Aug 41 · 22 Aug 32 · 26 Aug 12 ·
29 Aug 18 · 2 Sep 9 · 5 Sep 22 · 9 Sep 10.

## 8. C · Spans & coverage — "is the ground truth complete?"

Three compact cards in a row, then a coverage strip per fight.

**C1. Rounds confirmed** — per fight: `3 rounds · 2 adjusted · 1 seeded`. Each
round carries a status: `Adjusted by hand` (good) or `Seeded, unchanged`
(warning; tooltip: "identical to the pipeline's own segmentation — round accuracy
measured against it is circular").
Sample: DRAGOJEVIC vs HONDA 2 adjusted / 1 seeded · VITASOVIC vs STOSIC 0 / 3
seeded (in progress) · MILIDRAGOVIC vs MOOSMAN 1 adjusted.

**C2. Corner swaps** — count, total duration, share of labelled round time,
always rendered as a lower bound.
Sample: DRAGOJEVIC vs HONDA `5 · 25 s · ≥ 4.4%` · VITASOVIC vs STOSIC
`8 · 2.4 min · ≥ 16%` · MILIDRAGOVIC vs MOOSMAN `0 marked` (never "0% error").
Footnote: "Lower bound — labeller swap recall not measured yet (see G1)."

**C3. Excluded** — count, total duration, reason chips.
Sample: DRAGOJEVIC vs HONDA 2 (replay 14 s, camera cut 3 s) · VITASOVIC vs
STOSIC 1 (replay 9 s) · MILIDRAGOVIC vs MOOSMAN 1 (no reason given).

**C4. Coverage strip** (one per fight, full width) — the whole video as a thin
timeline, borrowing the Annotate timeline's lanes at miniature scale:

- **Rounds** — green blocks; a seeded-unchanged round gets a dashed outline.
- **State** — segments in the state colours.
- **Swaps / excluded** — purple / muted blocks, as in Annotate.
- **Label density** — a one-row heat strip of strikes per 10 s (cyan ramp). A
  stretch *inside a round* with no labels lights up as `Unlabelled stretch`. This
  is the strip's main job: it shows "round 2 only labelled up to 3:10".
- Hover shows time, frame and counts. Clicking opens Annotate at that frame. That
  needs a new `?frame=` URL parameter — neither Annotate nor the Player accepts
  one today.

## 9. D · Fight ledger

A dense table, one row per fight (labelled or AI-processed). Sticky header,
sortable columns, click a row to expand.

| Column | Content |
|---|---|
| Fight | `DRAGOJEVIC vs HONDA`, grey sub-line `#52 · 50 fps · 11.9 min` |
| Track | `Manual` or `AI` pill |
| Lifecycle | Five linked dots: Processed → Labelling → Finished → Exported → Scored. Filled = done, ring = current, faint = not yet. "Exported" = `ai/eval/labels/<video>.json` exists; add `Stale` when the database changed after export |
| Role | `Training` · `Eval fixture` · `Unlabelled` · `⚠ Both` (critical: the same bout is used for training and for evaluation — including a re-upload of the same video under another id) |
| Round min | Labelled round time |
| Strikes | Count, plus density per minute (warning under 5/min on a finished fight — probably unfinished) |
| State marks | Count |
| Swaps | `5 · ≥ 4.4%` |
| Excluded | Count |
| Sanity | `7/9` with tiny pass/fail pips (AI runs only) |
| Corner check | `95% · 219 fr` · `Unverified · 17 fr` · `Not run` |
| Strike F1 | Fixtures only; `Not scorable` on manual-track fights |
| Warnings | Count badge; opens the row's list |
| Actions | Icon buttons: Open in Annotate, Open in Player, copy-command menu (`export`, `sanity`, `score`, `corner_accuracy`) |

**Expanded row:** the coverage strip (C4) full width, a mini event-mix bar list
(top 6 actions), the warnings list, last labelled date, labeller name(s), and the
segmentation verdict — source `Clock` or `Detection only`, with the pipeline's
review reason verbatim.

**Sample rows**

| Fight | Track | Lifecycle | Role | Round min | Strikes · /min | Swaps | Sanity | Corner check | F1 | Warn |
|---|---|---|---|---|---|---|---|---|---|---|
| DRAGOJEVIC vs HONDA | Manual | Finished 22 Aug, not exported | Training | 9.4 | 143 · 15.2 | 5 · ≥ 4.4% | — | 58% · 55 fr · swaps | Not scorable | 4 |
| VITASOVIC vs STOSIC | Manual | Labelling | Training | 6.1 of 15 | 58 · 9.5 | 8 · ≥ 16% | — | Not run | Not scorable | 3 |
| MILIDRAGOVIC vs MOOSMAN | Manual | Exported 15 Aug | Training | 2.9 | 12 · 4.1 ⚠ | 0 | — | 93% · 86 fr | Not scorable | 3 |
| NAZHAND vs STAROPOLI | AI | Processed | Unlabelled | — | — | — | 8/9 | 95% · 219 fr | — | 1 |
| JURIC vs NOGUEIRA | AI | Processed | Unlabelled | — | — | — | 7/9 | Unverified · 17 fr | — | 1 |

**Sample warnings**

- DRAGOJEVIC vs HONDA — not exported to git · round 3 span seeded, never adjusted ·
  segmentation needs review ("round count came from fighter detection alone") ·
  bout uploaded 3 times (#46, #48, #52), 2 of those source videos missing on disk.
  Its corner check draws its decisive frames almost entirely from standing
  exchanges, so the ground sequences are unverified. Show that as gaps in the
  expanded row's evidence strip.
- VITASOVIC vs STOSIC — 1 corner-swap span still open (export will skip it) ·
  corner assignment fell back to the legacy path ("ambiguous tape: both slots read
  blue") · rounds 2–3 not reviewed yet.
- MILIDRAGOVIC vs MOOSMAN — low label density (4.1 strikes/min) on a finished
  fight · no labeller recorded · excluded span has no reason.
- NAZHAND vs STAROPOLI — not labelled; candidate evaluation fixture.
- JURIC vs NOGUEIRA — sanity: strike rate implausible (3.1/min, expected 5–60).

## 10. E · Pipeline accuracy — "how good is it, and can I trust the number?"

A provenance line sits under the section title, always visible:
`Pipeline 807c1b6 · constants a41f… · tolerance ±0.25 s (±12 f at 50 fps) ·
2 fixtures · 118 labelled strikes`

### E0. Not measurable yet — today's real state, design it first

Every fight labelled so far was processed on the manual track, so there are no
predictions to score. The section must say so plainly instead of showing zeros:

> **Strike accuracy isn't measurable yet.** The labelled fights have no pipeline
> predictions. Re-run a finished fight through the AI pipeline to make it an
> evaluation fixture — and keep it out of the training set.
> `python main.py fight_videos/<video>` then
> `python -m eval.cli score fight_videos/<video> --json <path>`
> [Choose a fixture ▾] [Copy commands]

Below the message, point to what does work without fixtures: pipeline health (F)
and label quality (G).

### E1. Headline — populated state (illustrative)

A group of stat tiles, not a wall of gauges:

- **Strike detection F1 56.7%** (large), `P 62.9% · R 51.7%`,
  `TP 61 · FP 36 · FN 57`, `118 labelled · 97 predicted`.
- **Human ceiling** `Not measured`, linking to G1. Once measured: a 0–100% track
  with the F1 fill and a tick at the ceiling (e.g. 91.4%).
- **Change** `+7.2 pts vs 53ee95d · +25.5 pts vs baseline/pre-stage-1`. Neutral
  grey with "not comparable" when tolerance or fixture set differ.
- Footnote: "Pooled over fixtures — TP/FP/FN summed, then P/R/F1 computed. Not an
  average of per-fight F1."

### E2. Per fixture

| Fixture | Labelled | Predicted | TP / FP / FN | P | R | F1 | Bias · jitter | Scored at |
|---|---|---|---|---|---|---|---|---|
| NAZHAND vs STAROPOLI | 74 | 61 | 40 / 21 / 34 | 65.6% | 54.1% | 59.3% | +3 f · 4 f | 807c1b6 |
| JURIC vs NOGUEIRA | 44 | 36 | 21 / 15 / 23 | 58.3% | 47.7% | 52.5% | +3 f · 5 f | 807c1b6 |

Show a `Mixed versions` warning when fixtures were scored by different pipeline
versions.

### E3. Classification — matched strikes only

Four stat tiles, each with its own n:

- **Strike family 41.0%** · 39 specific matches
- **Target zone 71.8%** · 39
- **Landed vs missed** `Not measurable` — labels deliberately record no outcome
- **Grappling matches 22** — non-specific predictions (clinch/ground punches and
  knees): counted for detection, excluded from family and target

A collapsed row underneath: **Corner read-back 98.4% · 61**, with a `Circular`
badge and the explanation: "The labeller picks the corner from the pipeline's own
overlay, so a tracker swap is copied into the label and cancels out. Use corner
swaps (C2) and the label-free corner check (F2) instead."

### E4. Family confusion

**Form:** a heatmap, truth rows × predicted columns (jab, cross, hook, uppercut,
elbow, kick), row-normalised %, one sequential hue, the diagonal value in bold
text. Beside it, the top confusions as a short list:
`hook → uppercut 4 · jab → cross 4 · cross → jab 3 · cross → hook 3`.
Note on the elbow row: "No pipeline equivalent — every labelled elbow is a miss."

### E5. Timing

A dot strip of signed offsets (predicted − labelled, in frames) from −12 to +12,
with a zero line. Stats: `bias +3.0 f (60 ms late) · jitter 4.5 f`.
Caption: "Bias is a constant to subtract once, not a reason to widen the
tolerance."

### E6. Fight state

- **Dumbbell rows** (truth dot — predicted dot on one shared axis per row):
  - Transitions per minute: truth 2.1 · predicted 6.8, with a warning badge
    "flaps 3× faster than reality"
  - Median dwell: truth 14.2 s · predicted 3.1 s
- A 3×3 confusion heatmap, STRIKING / CLINCH / GROUND, row-normalised.
- Per-frame accuracy 78.2%, deliberately small, captioned "dominated by the most
  common state".

### E7. Rounds

Per fixture: `Count ✓ 3 = 3`, then per round IoU with start/end offsets.
Sample: R1 IoU 97.9% (start +0.8 s, end −0.4 s) · R2 96.4% (+1.9 s, −2.4 s) ·
R3 `Seeded — not verified`.
Note: "Splitting one round into three still gives a high IoU — the count is what
catches it."

### E8. Trend across pipeline versions

**Form:** a line chart. x = pipeline versions in commit order (short SHA + date),
y = 0–100%, one y-axis.

- F1 in the accent colour: 2 px line, ≥ 8 px markers.
- Precision and recall in de-emphasis grey, direct-labelled at the line ends.
- Human ceiling as a labelled horizontal reference line, once measured.
- The baseline version carries a flag; a different marker glyph wherever
  `constants.py` changed.
- The line breaks with a note wherever tolerance or the fixture set changed.

Sample F1: baseline/pre-stage-1 31.2 · 5ecd0ba 44.0 · 53ee95d 49.5 · 807c1b6 56.7.

### E9. Worst misses and false positives

Two short lists side by side, 8 rows each, missed strikes first — they are the
review queue. Row: clock, frame, corner dot, what was labelled or predicted,
fixture. Clicking a row opens Annotate or the Player at that frame.

- `2:14.36 · f6719 · R · labelled left hook · head · not detected`
- `3:02.10 · f9106 · B · predicted jab_head · no label within ±12 f`

## 11. F · Pipeline health — label-free, works on every processed fight

These checks need no labels. They catch output that is *internally impossible*,
not merely inaccurate, so they run on every AI-processed fight. The corner and
segmentation parts also apply to manual-track fights, which run every stage
except strike detection and the state machine.

### F1. Sanity checks

**Form:** a matrix. Rows = processed fights, columns = the 9 checks, cells = a
status icon: `Pass` · `Fail` · `Not evaluated` (e.g. "no state transitions to
evaluate"). Hover shows the measured value, the detail and the expected band. A
summary column reads `7 / 9`. A `Compare with previous version` toggle adds a
small arrow badge to every cell that changed — flipped to pass (good) or to fail
(critical).

| Check | Expected band |
|---|---|
| Events inside rounds | 0% of strikes outside a round |
| No simultaneous mutual strikes | ≤ 2% of events |
| No duplicate events | 0 |
| State does not flap | ≤ 15 transitions/min |
| State dwell is physical | median ≥ 1.0 s |
| Strike rate is plausible | 5–60 strikes/min |
| No short interior rounds | 0 |
| Round breaks are real breaks | 0 gaps too short |
| Round count fits video length | ≤ what the video can hold |

Sample history (these are the real committed baseline reports for JURIC vs
NOGUEIRA):

- `769e83f` — 2 of 6 pass: mutual strikes 75% ✕, duplicate events 4 ✕,
  19.6 transitions/min ✕, dwell 0.76 s ✕. The 3 round checks didn't exist yet —
  `Not evaluated`.
- `5ecd0ba` — 3 of 4 pass: strike rate 3.1/min ✕. State checks `Not evaluated`
  (no transitions); round checks `Not evaluated`.

### F2. Corner assignment (per fight)

- **Label-free corner check** — `95% correct · 219 decisive frames` → `OK`.
  Below 90% → `Intermittent swaps` (warning). Below 50% → `Inverted` (critical).
  Fewer decisive frames than a minimum (proposed default 30) → `Unverified`,
  whatever the percentage. A thin strip along the fight's timeline shows OK and
  flipped runs, plus the gaps where no frame was decisive (typically ground
  sequences).
- **Assignment path** — `Appearance` · `Legacy fallback — ambiguous tape (both
  slots read blue)` · `Legacy fallback — too few clean frames`.
- **Clean frames per slot** — `412 / 388`.
- **Duplicate-corner invariant** — `OK` or `Violated` (critical: a release
  blocker).
- **Box/skeleton drift** — `0.62% of rows` (the skeleton's torso centre falls
  outside its own box).

Sample: JURIC vs NOGUEIRA `100% · 17 fr → Unverified` · MILIDRAGOVIC vs MOOSMAN
`93% · 86 fr → OK` · NAZHAND vs STAROPOLI `95% · 219 fr → OK` · DRAGOJEVIC vs
HONDA `58% · 55 fr → Intermittent swaps`.

### F3. Segmentation and source video

- **Round source** — `Clock` (scoreboard timer fitted) or `Detection only`
  (warning: "boundaries are a guess"), timer coverage %, round-number coverage %,
  and the pipeline's review reason verbatim.
- **Video integrity** — `reported 35,589 · decoded 35,589 frames ✓` and
  `File on disk ✓ / ✕`. Tooltip: "Labels point at frames of this exact file. A
  missing or re-encoded video detaches every label."

## 12. G · Label quality & action queue

### G1. Can we trust the labels?

Three status cards:

- **Human agreement ceiling** — `Not measured`. "Label one round twice — a second
  person, or yourself a week later — to get a ceiling for every F1." Once
  measured: detection F1, family agreement, corner agreement (expect ~100%; lower
  means a labelling-UI defect) and the most common disagreements.
- **Corner-swap recall** — `Not run`. "Inject a known swap, label the fight
  normally, check the swap got marked." Once run: detected or missed, plus start
  and end edge error in frames.
- **Matching tolerance** — `±0.25 s, pinned`. A range bar from a floor (p95 of
  human timing jitter — needs the agreement run) to a ceiling (p5 of the gap
  between one fighter's consecutive strikes — computable from labels today), with
  the current value marked. Critical when the current value is above the ceiling:
  "fast combinations can shift-match and inflate F1". Sample ceiling: 0.18 s →
  critical.

### G2. Action queue

A prioritised list grouped by severity. Each item: status icon + label, fight,
a one-line explanation, one action (`Open at frame` · `Copy command` ·
`Snooze 7 days`).

- **Critical:** same bout used for training and evaluation · duplicate-corner
  invariant violated · tolerance above the combination ceiling · source video
  missing for a labelled fight
- **Warning:** open span (export skips it) · strikes outside every round span
  (dropped on export) · state mark with a corner attached · labels after the
  fight-end mark · finished but not exported · export older than the latest
  labels · round span seeded and never adjusted · segmentation needs review · low
  label density on a finished fight · one fight above 50% of strikes · class below
  the minimum · corner check unverified or intermittent · failing sanity check
- **Info:** events captured but not exported (takedown attempt/defended,
  submission, knockdown, fight end) · no labeller name · human ceiling not
  measured · swap recall not run

Sample top of queue:

1. Critical · all fights — tolerance ±0.25 s is above the combination ceiling
   (0.18 s) · `Copy command`
2. Critical · #48 DRAGOJEVIC vs HONDA (earlier upload) — source video missing; its
   labels can't be joined back to frames · `Open fight`
3. Warning · VITASOVIC vs STOSIC — corner-swap span open since 4:12 ·
   `Open at frame`
4. Warning · DRAGOJEVIC vs HONDA — finished 22 Aug, not exported ·
   `Copy command`
5. Warning · all fights — one fight holds 67% of strikes; label more of the
   others · `Open ledger`

## 13. Reference drawer — how labels become training data and scores

A right-side drawer, opened from section B's header.

| Palette action | Exports as (family · target) | Scored against | Note |
|---|---|---|---|
| Jab · Cross | jab / cross · head or body | `jab_head` … `cross_body` | lead/rear hand — works for southpaws |
| Left/right hook · left/right uppercut | hook / uppercut · head or body | `hook_*` · `uppercut_*` | the hand is dropped at export |
| Calf kick · Low kick | kick · leg | `low_kick` | |
| Middle kick | kick · body | `middle_kick` | |
| High kick | kick · head | `head_kick` | |
| Elbow | elbow · head or body | — | always a miss until the pipeline detects elbows |
| Clinch knee · Ground knee | knee · non-specific | `clinch_knee` · `ground_knee` | counts for detection only |
| Clinch punch · Ground and pound | punch · non-specific | `clinch_punch` · `ground_punch` | counts for detection only |
| Striking · Clinch · Ground marks | state spans, each running to the next mark or the end of its round | state changes | |
| Takedown landed | takedown | `takedown_initiated` | captured, not yet scored |
| Takedown attempt/defended · Submission · Knockdown · Fight end | not exported | — | |

Drawer footer: "Matching is optimal one-to-one on time within ±0.25 s, ignoring
corner. Only frames inside a labelled round and outside every excluded span
count."

## 14. Visual system

Match the existing app (`frontend/DESIGN_SYSTEM.md`):

- **Background** `#050709` with the drifting cyan / purple / orange ambient orbs
  and ~3% film grain.
- **Glass cards:** fill `rgba(255,255,255,0.04)`, `blur(20px) saturate(160%)`,
  1 px `rgba(255,255,255,0.07)` border, 16 px radius, 18 / 20 px padding.
  **Inner tiles:** `rgba(0,0,0,0.30)`, 1 px `rgba(255,255,255,0.05)` border,
  12 px radius.
- **Type:** Manrope for UI (400–800); Bebas Neue for large stat numbers only;
  section labels 10.5 px, 700, uppercase, 0.12 em tracking; headings 800 with the
  white-to-50% gradient fill.
- **Icons:** Material Symbols Outlined, 14–22 px.
- **Controls:** pills for toggles, glass buttons for secondary actions, the cyan
  gradient primary button for at most one action per view.
- **Motion:** sections fade up on first load (0.5 s, staggered 80 ms). Nothing
  animates on refetch.

**Colour roles** — checked with a palette validator against the card surface
(≈ `#0f1113`), including simulated colour blindness:

| Role | Colours | Rule |
|---|---|---|
| Magnitude — bars, heatmaps, meters | cyan ramp from `#00daf3` | one hue; nominal categories never get a colour each |
| Corner | red `#ff4d4d` · blue `#3aa0ff` | clearly separable for all readers; always paired with an R/B label or the fighter's name |
| Fight state (charts on this page) | STRIKING `#0099b0` · CLINCH `#e64a19` · GROUND `#9085e9` | passes every check. Don't copy the Annotate timeline's CLINCH orange + GROUND red — they're hard to tell apart even with full colour vision, and that red is also the red corner |
| De-emphasis | slate `#94a3b8` | context series: precision/recall lines, "other" |
| Span kinds | round `#a3c900` · corner swap `#7c3aed` · excluded `#64748b` | same as the Annotate timeline |
| Status | good `#0ca30c` · warning `#fab219` · critical `#ef4444` · unverified `#94a3b8` · not measured `#64748b` | reserved meaning, never a series colour. **Always icon + text** (`check_circle`, `warning`, `error`, `help`, `remove`): good and critical collapse for red-green colour-blind readers, and critical is nearly the same red as the red corner |

**Text** wears text tokens (`#f1f5f9`, `#cbd5e1`), never a series colour.
`#475569` (text-disabled) is 2.5:1 on the card surface — never use it for data.
`#64748b` (text-muted) is 4.0:1 — hints and captions only.

**Chart marks:** bars ≤ 24 px thick (8–10 px in dense lists, like the Player's
segmented bar), 4 px rounded data end, square at the baseline · 2 px
surface-coloured gap between stacked segments · 2 px lines · markers ≥ 8 px with
a 2 px surface ring · solid hairline gridlines one step off the surface · one
y-axis per chart · a legend whenever there are two or more series, with direct
labels only where they fit · a `Table` toggle on every chart showing the same
numbers.

**Figures:** large standalone numbers use proportional digits; table columns and
axis ticks use tabular digits. Compact large counts (`12.9K`).

**Avoid** rings or gauges for every metric — a wall of them reads as a sports
scoreboard, not an engineering instrument. A meter shows a value against a target;
a stat tile shows a single number.

## 15. States, interactions, responsive

**States** — design each wherever it applies:

- **Loading** — skeleton on first load only; a refetch holds the previous render
  at reduced opacity.
- **Empty** — no labelled fights: "Upload a fight in Manual mode to start
  labelling" and the Upload button.
- **In progress** — real numbers with an `In progress` tag.
- **Not measurable** — see E0.
- **Unverified / low evidence** — see C1 and F2.
- **Stale** — exported JSON older than the database.
- **Error** — backend unreachable: keep the last data, with a banner naming the
  last successful refresh time.

**Interactions**

- Tooltips on every mark — value first, label second. Keyboard focus shows the
  same content.
- An ⓘ popover beside every metric carries its caveat from §3 in one or two
  sentences.
- Timeline positions, misses, false positives and queue items open
  `/fights/:id/annotate?frame=N` or `/fights/:id?frame=N` (a new parameter).
- Copy-command buttons copy the exact CLI command with the fight's video path and
  show a "Copied" toast.
- Filter state lives in the URL, so a view can be shared.

**Responsive**

- **≥ 1100 px:** hero (5 cols) + tiles (7 cols); B1 in 8 cols beside B2/B3
  stacked in 4; ledger and E full width.
- **640–1099 px:** one column; heatmaps scroll sideways inside their card; the
  ledger moves State marks through Strike F1 into the row expander.
- **< 640 px:** summary only — hero, tiles in a 2-column grid, B1 as a list,
  ledger as cards, E1 or E0; other sections collapsed.

## 16. What to produce

1. Desktop, 1440 px, full page, populated with the sample data.
2. The same page as it is today: section E in its not-measurable state (E0).
3. The fight ledger with DRAGOJEVIC vs HONDA expanded.
4. The top of the page at ~1024 px and at 390 px.
5. A component sheet: status badge (all 5 states), stat tile, hero meter,
   lifecycle dots, heatmap cell with the low-sample tick, coverage strip,
   action-queue item, `Circular` badge, `Not scorable` value.

**Out of scope:** editing labels (Annotate does that) · fighter performance
statistics (the Player does that) · buttons that train or tune anything · pie or
donut charts for the event mix · dual-axis charts.

## Appendix — where each number comes from

Not needed for the visual design; here so the build can follow it.

| Data | Source | Status |
|---|---|---|
| Label counts, targets, corners, activity | `label_events` | Available |
| Rounds, swaps, excluded, open spans; seeded-unchanged check | `label_spans` compared with `rounds` | Available |
| Track, lifecycle, finished marker, segmentation verdict, video check | `fights` (`state`, `labeled_at`, `segmentation_needs_review/_reason`, `reported/decoded_frames`) | Available |
| Predictions to score | `fight_events`, `rounds` | Available |
| Exported ground truth | `ai/eval/labels/<video>.json` | On disk; needs a read endpoint |
| Score and sanity reports with `git_sha`, `constants_sha256`, `tolerance_frames` | `eval.cli score / sanity --json` (e.g. `ai/eval/baselines/*.json`) | Only when run with `--json`; needs a reports folder and an endpoint |
| Human ceiling | `ai/eval/labels/<video>.agreement.json` | Not produced yet |
| Label-free corner check | `python -m eval.corner_accuracy <id>` | Printed only; needs `--json` |
| Assignment path, clean frames, invariant, box drift, timer coverage | pipeline run log | Log only; needs saving per run |
| Swap recall | `eval.cli corner-swap-recall` | Printed only; not run yet |
| Tolerance floor and ceiling | derivable from labels (floor needs the agreement run) | Not built |
| Video on disk, duplicate uploads | filesystem + `fights.video_path` | Derivable in the backend |
