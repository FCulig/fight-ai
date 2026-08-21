[← Back to Stage 0 index](02-stage0-labelling.md) · [Plan index](../PLAN.md)

**Depends on:** [Prerequisite P1–P3](01-prerequisite.md) complete. Not
technically blocked by [0c(5)](02b-label-schema.md#0c-5), but do that first
regardless — see the [Stage 0 index](02-stage0-labelling.md) for why.
**Blocks:** [0c(2)](02b-label-schema.md#0c-2) and [0d](02c-labelling-ui.md#0d) key off the `labeled_at` marker this chunk adds. [0b](#0b) blocks nothing else in Stage 0 but is required before real upload traffic is safe.

---

## 0a/0b — Upload tracks and validation

✅ **DONE.** `VALIDATING`/`INVALID` states, `labeled_at` column, full-decode
validator (`eval.cli video --fight-id`) with pid handoff and
`_AI_ENTRYPOINTS` wiring, `run_batch`/`_ACTIVE_PIPELINE_STATES` exclusions,
and frontend INVALID reason + delete/re-upload UI are all implemented and
verified end-to-end (clean-path dispatch, truncated/unopenable-file paths,
pid ownership transfer, delete mid-VALIDATING).

<a id="0a"></a>
### 0a. Two upload tracks

`mode: 'manual' | 'ai'` is already wired from `UploadDialog.tsx` through
`uploadFight()` to `POST /fights/upload` ([fights.py:105](../backend/app/api/routes/fights.py)),
where it selects `run_pipeline_async(skip_events=...)`. Each track already has its
own states. Two things are still missing: the two validation states ([0b](#0b)), and a
**durable marker for "this fight has ground truth"** — see below.

**AI track** — existing `FightProcessingState`, plus the two new ones:

```
VALIDATING → QUEUED → DETECTING → … → ANALYZING → COMPLETED
     ↘ INVALID                                   ↘ FAILED
```

**Manual track** — for videos uploaded to become ground truth. The two labelling
states already exist; only the two shared validation states are new:

```
VALIDATING → LABELING_IN_PROGRESS → LABELING_COMPLETE
     ↘ INVALID
```

⚠️ **There is no `UPLOADING` state, and there cannot be one.** An earlier draft
of this plan opened both tracks with `UPLOADING`, which is unreachable: the
`fights` row is not created until *after* the bytes have landed and
`extract_video_meta` has succeeded ([fights.py:139-167](../backend/app/api/routes/fights.py)),
so there is no row to hold the state during the upload. Upload progress is a
client-side concern and stays one.

Note that it is currently *not* reported either — `uploadFight` posts a
`FormData` through `fetch` ([api.ts:77](../frontend/src/services/api.ts)), and
`fetch` exposes no upload-progress events, so `UploadDialog` can only show a
boolean spinner. If a percentage is wanted, swap that one call to
`XMLHttpRequest` and read `xhr.upload.onprogress`. That is a self-contained
frontend change, unrelated to the pipeline, and is **not** a prerequisite for
anything else here.

`LABELING_IN_PROGRESS → LABELING_COMPLETE` is **user-triggered** and already
built: `FightEndModal` → `POST /fights/{id}/finish-labeling`
([fights.py:217](../backend/app/api/routes/fights.py)). It gains two things
here — the "all rounds fully annotated" precondition ([0d](02c-labelling-ui.md#0d))
and setting `labeled_at` (below).

`INVALID` must stay distinct from `FAILED` — "the source video is broken" and
"the pipeline crashed" need different UI and different remedies.

**A manual-track video still runs a reduced pipeline**, between `VALIDATING` and
`LABELING_IN_PROGRESS` — everything except the two components being replaced:

```
detection → tracking → pose → corner assignment → scoreboard OCR → segmentation
          → write fighter_frames + rounds
   ✗ strike detection   ✗ state machine
```

This is not a convenience — it is how a labelled fight becomes training data.
The Stage 2 model learns from `fighter_frames.keypoints`; the labels say "red
threw a hook at frame 1620" but the **keypoints are the input features**. A
labelled fight without pose has labels and nothing to learn from. It also gives
the labelling UI its overlay.

**OCR and segmentation stay on.** They produce the `rounds` rows that seed the
labeller's round bounds (see [0d](02c-labelling-ui.md#0d)) — confirming or nudging
a boundary is far cheaper than marking two per round from scratch, and it yields
ground-truth rounds to score segmentation against. Only strike detection and the
state machine are suppressed, because those are the outputs being labelled and a
predicted answer on screen would anchor the labeller.

**Already implemented**, and this is what `skip_events` does today:
`write_frames_and_rounds` ([fight_processing.py:162](../ai/fight_processing/fight_processing.py))
persists boxes, keypoints and rounds while emitting no `fight_events` and running
no state machine; `pipeline.py` selects it at
[:443](../ai/pipeline.py). No new pipeline mode is needed.

⚠️ **Corner assignment is the risk to design around.** The human declares
"red = Batur" at upload, but `assign_corners()` decides which *pixels* are red in
each frame — and that is one of the unreliable components. If it swaps corners
mid-clinch, the skeleton persisted as red is actually the other fighter while the
human's label says "red threw a hook": **silent training-data corruption caused
by the exact bug being fixed.** Mitigation: the labelling UI draws the
corner-coloured overlay, so a swap is visible and the labeller marks that stretch
with a `corner_swap` span ([0d](02c-labelling-ui.md#0d) — *not* `excluded`, which
would discard the clinch frames the model most needs). Labelling then doubles as
corner-assignment QA, and the swap spans are themselves a signal for
[Stage 1](03-stage1-artifacts.md). **This mitigation is an untested assumption
about human attention — [0g](02d-label-quality.md#0g) measures it before it is
relied on at volume.**

#### `state` is not a durable record of having been labelled

The two tracks are not exclusive: once a video reaches `LABELING_COMPLETE`, it
can be re-submitted through the **full** AI pipeline to produce predictions to
score against. That is how a labelled fight becomes an evaluation fixture.
Training and evaluation sets stay disjoint — no fight is ever both — so a
training fight is never re-run and keeps its state untouched.

Evaluation fixtures are the problem. `run_pipeline` single-file upserts
`ON CONFLICT (video_path) DO UPDATE SET … state = 'queued'`
([pipeline.py:183](../ai/pipeline.py)), so re-running **overwrites
`LABELING_COMPLETE`** — and `finish_labeling` only transitions *from*
`labeling_in_progress` ([fight_service.py:161](../backend/app/services/fight_service.py)),
so there is no way back. An evaluation fixture would permanently lose the only
record that it was ever hand-labelled, and any export guard keyed on `state`
would refuse it forever.

**Fix: a nullable `labeled_at TIMESTAMP` column on `fights`,** set by
`finish_labeling` alongside the state transition and never written by the
pipeline. `state` then means only "where is this in the pipeline right now";
`labeled_at IS NOT NULL` means "this fight has finalised ground truth", and it
survives any number of pipeline re-runs. Every guard in
[0c(2)](02b-label-schema.md#0c-2) and [0d](02c-labelling-ui.md#0d) keys off
`labeled_at`, not `state`. `FightLabels` already carries a `labeled_at`
field ([schema.py:141](../ai/eval/schema.py)), so the column matches the JSON
schema rather than adding a second vocabulary.

`run_batch` is already safe — it excludes labelling states
([pipeline.py:581](../ai/pipeline.py)). Only single-file mode resets state, and
after this change that reset is harmless.

<a id="0b"></a>
### 0b. Validation on upload

`POST /fights/upload` ([fights.py:100](../backend/app/api/routes/fights.py))
currently validates with `extract_video_meta`
([:154](../backend/app/api/routes/fights.py)), which reads only the **container
header**. That is precisely the thing that lies about a truncated or partially
corrupt download: the header reports a full duration, the decoder stops partway
through, and the pipeline processes a fraction of the fight and reports success.
Nothing downstream notices.

**Fix:** full-decode validation between upload and whichever track follows.

- **Reuse `eval/videocheck.py`'s `check_video`,** which already returns reported
  vs. decoded frame counts and a `truncated` flag.
- **Async, not blocking.** Full decode is the only reliable test but costs
  roughly a tenth of real time — ~2.5 min for a 25-min fight. Upload returns
  `201` immediately with `state=VALIDATING`; the result arrives over the existing
  `/fights/stream` SSE channel via `set_fight_state`.

⚠️ **The validator needs an entry point that writes to the DB — `eval.cli video`
is not one.** An earlier draft said to "spawn it exactly the way
`run_pipeline_async` spawns `main.py` — no new machinery." That does not work.
`run_pipeline_async` is fire-and-forget: it returns a pid and **nobody ever
reaps the child or reads its exit code**
([pipeline_runner.py:52](../backend/app/services/pipeline_runner.py)). It works
only because `pipeline.py` reports its own progress through `set_fight_state`.
`python -m eval.cli video` reports nothing to the DB — it prints a report and
returns an exit status into a log file. Spawned that way, nothing would ever
transition `VALIDATING → QUEUED` / `INVALID`, nothing would persist the frame
counts, and nothing would start the pipeline on success.

**Fix: a small `ai/` entry point** (`validate_video.py`, or an `eval.cli`
subcommand that takes `--fight-id`) which calls `check_video`, writes the counts
and the resulting state through the existing `set_fight_state`, and on a clean
result spawns the pipeline itself. It runs in the AI venv, so
`from database import set_fight_state` is a direct import and the transitions
reach the SSE stream with no backend involvement — the same mechanism
`pipeline.py` already uses. The alternative — an `asyncio.create_subprocess_exec`
task in the backend that awaits the exit code — also works, but splits state
authorship across two processes for no gain.

Whichever is chosen, add its command-line marker to `_AI_ENTRYPOINTS` in
`pipeline_runner.py` (see the pid section below).
- **Persist the reason.** Store reported-vs-decoded frame counts on the `fights`
  row. `INVALID` on its own is not actionable.
- **Surface it in the UI.** An `INVALID` fight must show *why* it was rejected —
  "container reports 8.2 min, only 2.7 min decodes (67% missing); the file is an
  incomplete download" — with the option to delete and re-upload. A bare
  "invalid" badge sends people hunting through logs.
- File cleanup on rejection follows the existing pattern at
  [fights.py:145](../backend/app/api/routes/fights.py).

⚠️ **`pid` now refers to two different processes, and delete must not kill the
wrong one.** Today the upload handler spawns the pipeline and stores its pid in
one breath ([fights.py:174](../backend/app/api/routes/fights.py)), and
`DELETE /fights/{id}` kills whatever `pid` holds
([fights.py:241](../backend/app/api/routes/fights.py)). Inserting async
validation ahead of the pipeline breaks that invariant three ways: during
`VALIDATING` the pid is the *validator*, between validation and pipeline start
there is no live process at all, and after the handoff the pid must be
re-pointed at the pipeline.

Required behaviour:

- `set_fight_pid` is called by whichever stage is currently running, and the
  validator's pid is replaced — not merely overwritten on success — when the
  pipeline is spawned.
- On a clean validation exit, clear `pid` to `NULL` before spawning, so no window
  exists where `pid` names a dead process.

**Already handled, do not re-implement:** stale and absent pids. `NULL` is
already a no-op — `delete_fight` only calls `terminate_pipeline` when the pid is
non-`NULL` ([fights.py:241](../backend/app/api/routes/fights.py)) — and
`terminate_pipeline` already catches `psutil.NoSuchProcess`, verifies ownership
before signalling, and escalates `SIGTERM → SIGKILL` with bounded waits
([pipeline_runner.py:84](../backend/app/services/pipeline_runner.py)). A dead or
recycled pid neither raises nor reaches an unrelated process.

**Done:** *"deleting a fight mid-`VALIDATING` kills the validator"* would have
silently failed against that ownership check, which required `main.py` in the
command line and so classified the validator as "not ours" — `terminate_pipeline`
would have returned without signalling. The check is now driven by
`_AI_ENTRYPOINTS`, a tuple of markers covering every job this module spawns
(`main.py` and the validator), narrow enough that a recycled pid is still
rejected. **Any new AI-venv job spawned from `pipeline_runner.py` must add its
marker there, or it is silently unkillable.**

⚠️ **The new states must also be added to the two places that enumerate states,
neither of which is in this file's diagrams.**

- **`run_batch`** selects `WHERE state NOT IN ('completed',
  'labeling_in_progress', 'labeling_complete')`
  ([pipeline.py:579](../ai/pipeline.py)). Add `'validating'` and `'invalid'`.
  Left alone, batch mode races the validator on a fight that is still being
  decoded, and re-processes every file already rejected as broken — forever, on
  every run.
- **`_ACTIVE_PIPELINE_STATES`** drives the startup pid reconciliation
  ([fight_service.py:111](../backend/app/services/fight_service.py)). Add
  `'validating'`. Left alone, a fight whose validator died with a backend restart
  is never reconciled and sits in `VALIDATING` permanently, with no path out.

`'failed'` is deliberately absent from the `run_batch` exclusion list today, so a
failed fight is retried on the next batch run. `'invalid'` must **not** inherit
that behaviour: a truncated file does not become untruncated on retry.

---

## Verification

Build a deliberately truncated fixture
(`head -c $((SIZE/3)) good.mp4 > truncated.mp4`) so this is reproducible rather
than dependent on any particular file.

- Upload a good video in **AI** mode → `VALIDATING → QUEUED → … → COMPLETED`.
- Upload a good video in **manual** mode → `VALIDATING → LABELING_IN_PROGRESS`.
  Confirm `fighter_frames` are written with non-null `keypoints` (the Stage 2
  features) and `rounds` **are** inserted from segmentation (they seed the
  labeller's round bounds), while `fight_events` stays **empty**.
- Upload the truncated fixture → `VALIDATING → INVALID`, not offered for
  labelling, `run_pipeline_async` never fires, and the UI shows the
  reported-vs-decoded frame counts as the reason with a delete/re-upload action.
- Delete a fight while it is still `VALIDATING` → the validator process is killed,
  the file and row are removed, and nothing signals an unrelated pid. (The
  ownership check now recognises the validator; confirm the *new* entry point's
  command line actually matches `_AI_ENTRYPOINTS` — a mismatch fails silently,
  with `terminate_pipeline` returning as if the process were already gone.)
- Delete a fight whose `pid` names a process that has already exited → no error,
  no signal sent. (Already true; guard against regression.)
- `run_batch` with a `VALIDATING` fight and an `INVALID` fight in the table picks
  up **neither**, and re-running it does not re-process the `INVALID` one.
- Kill the backend mid-`VALIDATING`, restart it → the fight is reconciled to
  `FAILED` rather than sitting in `VALIDATING` forever.
- All transitions arrive over the existing `/fights/stream` SSE — including the
  ones written by the validator, which reach it through `set_fight_state` +
  `pg_notify` exactly as `pipeline.py`'s do.

---

Next: [0c(1)–(4) — Make the labels trainable, the rest](02b-label-schema.md#0c-1)
(you already did [0c(5)](02b-label-schema.md#0c-5) before this chunk)
