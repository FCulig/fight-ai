# Fight-AI: making punch / kick / fight-state tracking reliable

## How this plan is organized

This used to be one 1300-line file. It's now split into chunks under `plan/`,
one per execution phase, so each can be worked and checked off independently.
This file (`PLAN.md`) stays as the index: the measured problem, what already
exists, and the map below.

Every cross-reference between chunks (`P4`, `0c(5)`, `Stage 1 step 8`, …) is a
real markdown link, either to an anchor in the same file or to
`plan/<file>.md#<anchor>` in another. Anchors use the plan's own item codes
(`p1`, `c1`, `0c-5`, `st1-8`, …) via inline `<a id="…">` tags, not
auto-generated heading slugs — so they don't break if a heading's wording
changes later. Click through; nothing here is a dead pointer.

## Execution order

| # | Chunk | Depends on | Unblocks | Needs labels? | Status |
|---|---|---|---|---|---|
| 0 | [Blocking checklist (C1–C4)](plan/00-checklist.md) | — | Prerequisite | no | ✅ DONE |
| 1 | [Prerequisite — freeze the baseline (P1–P5)](plan/01-prerequisite.md) | Checklist | Stage 0, 1, 2 | no (P4 later) | ✅ P1–P3 done · ⏳ P4–P5 blocked on labels |
| 2 | [Stage 0 — Labelling framework (0a–0g)](plan/02-stage0-labelling.md) — itself split into [0c(5)](plan/02b-label-schema.md#0c-5), [0a/0b](plan/02a-upload-tracks.md), [0c(1–4)](plan/02b-label-schema.md), [0d](plan/02c-labelling-ui.md), [0e/0f/0g](plan/02d-label-quality.md), **in that order** — 0c(5) jumps the queue because it closes a live data-loss bug | Prerequisite P1–P3 | Stage 1 steps 6/8, P4, Stage 2 | — (produces them) | ✅ DONE (tooling) · ⏳ actual labelling is on the user |
| 3 | [Stage 1 — Fix the artifacts (steps 1–8)](plan/03-stage1-artifacts.md) | Prerequisite (steps 1–5,7); + Stage 0 (steps 6,8) | Stage 2 (benefits, not required) | mixed — see chunk | ✅ steps 1–5,7 done · ⏳ steps 6,8 blocked on labels |
| 4 | [Stage 2 — Skeleton action model](plan/04-stage2-model.md) | Stage 0 (training data) | — | yes | ⏳ blocked on labelled training data |
| — | [Also worth doing](plan/05-also-worth-doing.md) | none | none | no | ✅ DONE |

Read top to bottom the first time. After that, jump straight to whichever
chunk you're executing — each one states its own dependencies and what it
unblocks at the top, so you don't need to hold the whole graph in your head.

⚠️ **The one rule that spans chunks:** nothing in Stage 0, 1 or 2 starts until
[Prerequisite P1–P3](plan/01-prerequisite.md) are done, and those don't start
until the [Blocking checklist](plan/00-checklist.md) is ticked. That gate exists
because every number below was measured on the current working tree — see
Context.

---

## Context

Strike and fight-state tracking in `ai/` barely works. The pipeline is a
hand-tuned geometric rule cascade over 2D monocular keypoints with ~40 coupled
constants in `models/constants.py`, 13 commits of blind tuning, and no ground
truth or evaluation of any kind.

Measured on a 163-second processed fight sample — see the ⚠️ under the table
before reading any number in it.

| Symptom | Measured |
|---|---|
| Strikes outside the only detected round | **75 of 94 (80%)** |
| Events in frames where **both** fighters strike simultaneously | **60 of 94 (64%)** |
| Fight-state transitions | 55 in 163s — median dwell **0.62s** |
| `FULL`-validity frames | 30 of 8147 (0.4%) |
| Contact gate acceptance | 22 of 129 candidates; rejected median **1.57 torso-lengths** from the head |

<details>
<summary><b>Provenance</b></summary>

From a pipeline run's stdout in `ai/runs/`. Rows 4–5 are printed verbatim by
`_print_standing_punch_diag` ([fight_processing.py:67](ai/fight_processing/fight_processing.py)).
Rows 1–3 were derived by parsing the `threw a X at frame N` and `Fight state
changed to FightState.X at frame N` lines against the detected round bounds,
then **re-derived independently from `fight_events` in Postgres** by
`eval/sanity.py` — both agree. Reproduce on any processed fight with
`python -m eval.cli sanity <video>`.
</details>

⚠️ **These numbers come from a video the harness itself classifies as corrupt,
and that video is no longer on disk.** The source was
`BATURvsSTAMATOVIC.mp4`, which [eval/README.md](ai/eval/README.md) records as 67%
truncated — the container advertises 24712 frames and the decoder yields 8147,
which is exactly the 8147 in row 4 and the 163 seconds in the heading. Row 1 is
the most confounded of the five: "the only detected round" is partly an artifact
of segmenting a file that claims 8.2 minutes and decodes 2.7, so the 80% figure
is not clean evidence that round gating is missing (though the missing gate is
real — see [Stage 1 step 3](plan/03-stage1-artifacts.md#st1-3), which is
verified by reading the code, not the number). Rows 2 and 3 describe the
pose-sharing and hysteresis bugs, both of which are structural and hold
regardless of the source file; their *magnitudes* are not trustworthy.

The table stands as the reason this work exists. It does **not** stand as the
baseline. [C4](plan/00-checklist.md#c4) re-measures on an intact video before
anything is frozen.

Two fighters do not punch on the same frame 30 times, and fight state does not
alternate every 0.6s. These are artifacts with specific causes, not thresholds
that need nudging. More tuning cannot fix them, and without measurement nobody
can tell whether a change helped.

**Intended outcome:** a reusable framework for building ground-truth datasets
and measuring against them — including a measured bound on the ground truth's
own reliability — and a pipeline whose strike detection is a trained skeleton
action model rather than a rule cascade, with every threshold change justified
by a number.

**Decisions already made:** [Stage 2](plan/04-stage2-model.md) is a trained
skeleton action model, not a VLM-verifier approach. Labelling happens in the
**existing frontend**, not a standalone tool. Manually-labelled videos get their
**own state machine**, separate from AI-processed ones.

---

## Status — what already exists

**The manual-labelling infrastructure is built and works.** `mode: 'ai' |
'manual'` is wired end-to-end: `POST /fights/upload` →
`run_pipeline_async(skip_events=True)` → `ai/main.py --skip-events` →
`write_frames_and_rounds()` → `LABELING_IN_PROGRESS` → `POST
/fights/{id}/finish-labeling` → `LABELING_COMPLETE`. Manual fights **do** get
`fighter_frames` with keypoints — the one thing training cannot do without.
`run_batch` correctly skips labelling states. PID tracking with startup
reconciliation, the keyboard palette (`taxonomy.ts`), undo, the annotation
timeline and `FightEndModal` all exist.

**The state-broadcast channel is built and is track-agnostic.**
`ai/database.py:set_fight_state` writes `fights.state` and fires
`pg_notify('fight_state', …)` in one transaction;
[fight_state_listener.py](backend/app/utils/fight_state_listener.py) holds a
`LISTEN fight_state` connection on a background thread and fans every payload
out to the `/fights/stream` SSE subscribers. **Anything that writes a state and
notifies appears on SSE with no further work** — which is what makes
[0b](plan/02a-upload-tracks.md#0b)'s validation states cheap: a validator
running inside the AI venv can import `set_fight_state` directly and its
transitions reach the UI for free.

Stage 0a is therefore **done except for the durable ground-truth marker** (see
[0a](plan/02a-upload-tracks.md#0a)). Stage 0b is **not started**: upload still
validates from the container header alone, and `VALIDATING` / `INVALID` do not
exist in `FightProcessingState`. Beyond that what remains is the label
*schema*: what gets recorded is not yet sufficient to train on (see
[0c](plan/02b-label-schema.md#0c)).

Stage 0's scoring harness is **already built and verified** in `ai/eval/`
(uncommitted): `schema.py` (label format, doubles as the Stage 2 training
format), `predictions.py` (reads pipeline output back out of Postgres),
`score.py` (Hungarian-matched strike P/R/F1, state accuracy, round IoU),
`sanity.py` (label-free artifact checks), `videocheck.py`, `cli.py`, `README.md`.
No new dependencies — `scipy`, `numpy`, `opencv-python` were already in
`requirements-base.txt`.

`ai/eval/label.py` (OpenCV labelling tool) is superseded by the frontend and
**should be deleted**, along with its `label` subcommand in `cli.py`. Everything
else is independent of where labels come from and stays.

---

## Chunks

1. [⛔ Blocking user checklist (C1–C4)](plan/00-checklist.md) — done by hand, before anything else.
2. [Prerequisite — freeze the baseline (P1–P5)](plan/01-prerequisite.md)
3. [Stage 0 — The labelling framework (0a–0g)](plan/02-stage0-labelling.md)
4. [Stage 1 — Fix the artifacts (steps 1–8)](plan/03-stage1-artifacts.md)
5. [Stage 2 — Skeleton action model](plan/04-stage2-model.md)
6. [Also worth doing](plan/05-also-worth-doing.md)
