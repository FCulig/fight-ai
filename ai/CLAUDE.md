# Fight AI — Python Video Processing Library

## Workflow
- Always apply changes directly to the local working directory
- Never open PRs or suggest creating pull requests

## What it does
Accepts MMA fight videos, runs ML inference to detect fight events (grappling, state transitions), and writes all results to PostgreSQL. **PostgreSQL is a hard runtime dependency** — there is no no-DB path; the pipeline cannot run without a reachable `DATABASE_URL`.

## Project Structure
```
ai/
├── main.py                   # Argument parser + dispatcher ONLY — no business logic
├── pipeline.py               # All orchestration logic for both pipeline modes
├── debug.py                  # DebugContext — centralised debug output router
├── manifest.py               # Builds run summary (returned in-memory, never written to disk)
├── video_processing/
│   ├── fighter_detection/
│   │   └── fighter_detection.py # XL pose model supplies EVERY box + skeleton; the
│   │                         #   nano detector (weights.pt) is only a MASK saying
│   │                         #   which detected people are the fighters, since
│   │                         #   yolo26x-pose is COCO person-only and cannot tell a
│   │                         #   fighter from the referee. Nano's red/blue class head
│   │                         #   is IGNORED — corner is assign_corners' job.
│   ├── fight_segmentation.py # Fuses clock + OCR + detection signals → round list
│   ├── round_clock.py        # Fits the scoreboard countdown (slope known a priori =
│   │                         #   -1/fps, so only the intercept is estimated) → the
│   │                         #   authoritative round COUNT. See "Round segmentation".
│   ├── scoreboard_overlay/   # Scoreboard overlay OCR package
│   │   ├── __init__.py       # Re-exports + parse_roi_override()
│   │   ├── calibration.py    # Bottom-strip OCR to auto-detect overlay ROI
│   │   ├── extraction.py     # Per-frame OCR sampling + smoothing
│   │   ├── parsers.py        # Org-agnostic round/timer parsing. Two routes to the
│   │   │                     #   round: explicit prefix ("R1"/"ROUND 1") and, when
│   │   │                     #   the overlay shows a bare digit, box GEOMETRY —
│   │   │                     #   find_round_digit_box() locates the 1-char box beside
│   │   │                     #   the timer. Calibration unions that box into the ROI,
│   │   │                     #   or the crop clips the digit and it is never readable.
│   │   ├── debug.py          # Heatmap / crop / matplotlib visualisation helpers
│   │   └── scoreboard_verification.py  # Renders annotated verification MP4
│   ├── fighter_tracking/
│   │   └── fighter_tracking.py  # Geometry-only tracker (Hungarian + IoU), assigns provisional track_id 0/1
│   ├── corner_assignment/
│   │   └── corner_assignment.py # Per-frame appearance-anchored re-ID: bootstraps templates from
│   │                            #   clean separated frames, then assigns corner per frame via
│   │                            #   tape + torso-histogram distance with hysteresis.
│   │                            #   Falls back to legacy tape-vote when colors are indistinguishable.
│   └── pose_tracking/
│       └── pose_verification.py # Renders the --verify-pose debug MP4. The pose
│                             #   *model* now runs inside fighter_detection; only this
│                             #   debug renderer is left in this package.
├── fight_processing/
│   ├── fight_processing.py   # State machine + strike model pass + DB writes (fight_events, fighter_frames, rounds)
│   └── fight_processing_util.py
├── models/
│   ├── FightState.py         # Enum: STRIKING=1, CLINCH=2, GROUND=3 (+ GRAPPLING_STATES set)
│   ├── FighterTracker.py     # Constrained 2-slot tracker with Hungarian matching
│   ├── geometry.py           # Shared pure-geometry helpers: get_torso_rectangle,
│   │                         #   calculate_distance_between_fighters, get_fighter_scale.
│   │                         #   All three return None on insufficient keypoint
│   │                         #   confidence rather than computing on a hallucinated
│   │                         #   coordinate — callers must treat None as "unusable
│   │                         #   this frame". Lives here (not in fight_processing) so
│   │                         #   corner_assignment can import them without a layering
│   │                         #   inversion.
│   └── constants.py          # All thresholds and label IDs
├── eval/                     # Evaluation harness — see eval/README.md
│   ├── schema.py             # Ground-truth label format (also the training set
│   │                         #   format for the planned skeleton action model)
│   ├── labels_db.py          # Builds FightLabels from fight_events rows with source='label' (Postgres)
│   ├── corner_swap_check.py  # Inject/measure corner-swap labelling recall (plan 0g)
│   ├── corner_accuracy.py    # Label-free: does stored `corner` match the kit colour?
│   │                         #   The only check that catches a red/blue inversion —
│   │                         #   python -m eval.corner_accuracy <fight_id>
│   ├── predictions.py        # Reads pipeline output back out of PostgreSQL
│   ├── score.py              # Strike P/R/F1, state accuracy, round IoU, agreement scoring
│   ├── sanity.py             # Label-free artifact checks
│   ├── videocheck.py         # Full-decode video integrity check (truncation detection)
│   ├── report_io.py          # JSON persistence for sanity/score reports
│   ├── cli.py                # python -m eval.cli {export,video,sanity,score,agreement,
│   │                         #   inject-swap,corner-swap-recall,summary}
│   └── labels/               # Hand-labelled ground truth — COMMITTED to git
├── action_model/             # Stage 2 skeleton action model (plan/04) — the
│   │                         #   pipeline's ONLY strike detector.
│   ├── config.py             # Window/taxonomy contract (copied into each checkpoint)
│   ├── windows.py            # Pose-window builder shared by training and inference
│   ├── inference.py          # load_model + dense detect_strikes (peak picking/NMS)
│   ├── weights/strike_model.pt # The checkpoint process_fight loads (committed)
│   ├── dataset.py            # fight_events(F, corner) -> fighter_frames windows.
│   │                         #   Trains ONLY on purpose='training_data' +
│   │                         #   is_verified IS TRUE labels; corner_swaps NOT applied.
│   ├── model.py              # Small temporal CNN: family (+none) and target heads
│   └── train.py              # python -m action_model.train -> runs/action_model/<ts>/
│                             #   Validation = purpose='reference' fights ONLY, never a
│                             #   slice of a training fight; best-val epoch is kept.
└── database.py               # SQLAlchemy SessionLocal; also set_fight_state,
                               #   set_video_check, set_fight_pid — the only way any
                               #   AI-venv process (pipeline or upload validator) writes
                               #   fights.state/pid, so the SSE stream stays in sync
```

## Architecture Rules
- **`main.py` is a pure argument parser and dispatcher.** It contains no business
  logic — only `argparse` setup and a single call to `run_pipeline()` or `run_batch()`.
  Do not add conditional logic, file path construction, timing, or imports of
  processing modules to `main.py`.
- **`pipeline.py` owns all orchestration** via `run_pipeline()` (single-file) and
  `run_batch()` (multi-file). Step ordering, skip logic, fallback handling, timing,
  and manifest building live here.
- **`debug.py / DebugContext`** is the single route for all debug output (images,
  JSON snapshots, log lines). Never add scattered `print`/`cv2.imwrite` for debug
  purposes — use `ctx.save_image`, `ctx.save_json`, `ctx.log` instead.
- **`constants.py`** is the single source of truth for all numeric thresholds.
  Never hardcode a threshold or frame-count in a processing module.
- **Never change a fight-state or strike-detection threshold in `constants.py`
  without measuring it.** This covers the block running from
  `FIGHT_STATE_SMOOTHING_WINDOW_SECS` down to `HEAD_ABOVE_SHOULDER_RATIO` — the
  `determine_fight_state` classifier, `STRIKE_PROB_THRESHOLD`/`STRIKE_NMS_SECS`
  (the strike model's peak picking) and the recoil check. Run
  `python -m eval.cli score-pair --labels-fight-id <reference> --predictions-fight-id <ai_labeled twin>`
  before and after and put both numbers in the commit message; score's FIGHT
  STATE and STRIKE DETECTION sections are what measure these. The same goes for
  **retraining the strike model** (`action_model/weights/strike_model.pt`) —
  and re-sweep the two strike thresholds after a retrain, they are tuned to
  one checkpoint's probability calibration.
- **The rule stops there — do not demand a `score` delta for the rest.**
  Segmentation (`MIN_FIGHT_END_GAP_SECS` … `ROUND_DISENGAGED_RATIO`) and
  scoreboard overlay (`SCOREBOARD_*`) constants are out of scope. Scoreboard OCR
  has no `score` section at all. Segmentation does have one (ROUNDS), but its
  ground truth is currently untrustworthy: `fight_events` rows of kind `round`
  (source='label') are **seeded from the pipeline's own `rounds` output** the
  first time the Annotate page opens a fight (`backend/app/services/event_service.py`),
  so unless a human has actually moved those boundaries, round IoU reads ~1.000
  against the prediction itself and a genuine improvement scores as a
  regression. Check that the span differs from the `rounds` row before
  believing a round-IoU number.
- **Measure those against the subsystem instead.** A scoreboard OCR change is
  validated by timer coverage plus a label-free consistency check: the clock is
  linear, so `k = frame/fps + seconds_remaining` is constant within a round and
  a misread lands off that intercept. Establish the intercepts from readings the
  current settings already accept, then confirm newly admitted readings agree —
  that tests for false positives out-of-sample without needing any labels. Note
  EasyOCR's line confidence is *not* a usable quality signal here: a ≤1px change
  to the calibrated ROI moves it by a median of 0.117 (max 0.433), and the floor
  feeds back into the ROI, since calibration only unions boxes that clear it.
- `python -m eval.cli sanity <video>` needs no labels and should be run on every
  processed video regardless of which constant changed.

## Entry Points

```
python main.py              # batch mode — scans fight_videos/, processes unprocessed fights
python main.py fight.mp4    # single-file mode
```

### Batch mode (`run_batch`)
1. Creates `fight_videos/` if absent and prints a hint, then returns early.
2. Scans for `.mp4` / `.mkv` / `.mov`. For each file extracts `fps`, `width`, `height`
   via `cv2.VideoCapture` and upserts a `fights` row (`ON CONFLICT DO NOTHING` — never
   disturbs an existing row's state or metadata).
3. Queries `SELECT … FROM fights WHERE state NOT IN ('completed', 'labeling_in_progress',
   'labeling_complete', 'validating', 'invalid')`. `'failed'` is deliberately included
   (retried on the next run); `'validating'`/`'invalid'` are excluded so batch mode
   never races the upload validator or reprocesses a file already rejected as truncated.
4. Calls `run_pipeline(video_file, fight_id=row.id, …)` for each.
5. On success: `set_fight_state(fight_id, COMPLETED)`.
6. On exception: logs traceback, continues to next fight (row stays at whatever state
   the exception left it in — typically `FAILED`, set by the caller).

**Accepted limitation:** a file replaced at the same path is not re-detected by batch
(row already exists, `DO NOTHING`). Re-running such a video requires single-file mode,
whose upsert resets `state` to `'queued'`.

### Single-file mode (`run_pipeline` with `fight_id=None`)
Upserts the fight record (`ON CONFLICT DO UPDATE SET fps/width/height, state='queued'`)
so any existing child rows are treated as stale, then runs the full pipeline through
`set_fight_state` transitions (`QUEUED → DETECTING → … → ANALYZING → COMPLETED`, or
`LABELING_IN_PROGRESS` when `--skip-events` is passed for the manual-labelling track).

**Upload validation runs before either mode reaches `main.py`.** The backend spawns
`eval.cli video --fight-id <id>` first (state `VALIDATING`), which full-decodes the
video, and on a clean result spawns `main.py` itself and hands `pid` off to it — see
`eval/cli.py`'s `_validate_and_dispatch` and plan 0b. A truncated file is marked
`INVALID` and `main.py` never runs.

## Pipeline — fully in-memory data flow

**No intermediate data files are ever written.** Each step returns its output dict and
the next step consumes it directly. PostgreSQL is the only persistent data store.

| Step | Function | Returns |
|------|----------|---------|
| Fighter detection | `detect_fighters()` | detection dict (XL boxes + keypoints, fighters only, ≤2/frame) |
| Fighter tracking | `track_fighters()` | track dict (provisional track_id 0/1) |
| Corner assignment | `assign_corners()` | pose dict (class_id remapped to red=0/blue=1) |
| Scoreboard OCR | `extract_scoreboard_samples()` | samples dict |
| Segmentation | `segment_fights()` | rounds list |
| Fight processing | `process_fight()` | — (writes to DB) |

`fps` is read once from the `fights` row (extracted from the video at registration time)
and threaded in-memory to every step that needs it. No step re-reads fps from disk.

**Detection and pose are one step.** They used to be two: a nano detector
(`yolov8n`, 3.0M params, 640px) emitted the boxes that survived to the database,
and `yolo26x-pose` ran afterwards over every frame purely to have its keypoints
copied onto them — its own, much better, boxes were discarded. Worse, the nano
box was the *lookup key* for those keypoints (attached only above an IoU floor),
so a bad nano box did not merely degrade the box, it dropped the skeleton
entirely and the row reached `fighter_frames` with a box and no keypoints.
Skeletons are the training signal, so that was silent data loss concentrated on
the hardest frames. The XL model now supplies both, and a box and its skeleton
can no longer disagree about who they describe.

**Developer skip-flags** (`--detection-file`, `--track-file`, `--pose-results`,
`--scoreboard-samples`) load a developer-supplied file into the in-memory dict at the
appropriate step. The pipeline never *produces* these files.
`--reid-file` is a deprecated alias for `--track-file`.

**Diagnostic outputs** (`--verify-pose` / `--verify-scoreboard` debug videos and
scoreboard calibration debug images) are opt-in artifacts and are not part of the data
flow. They remain as explicitly-requested disk outputs and cause `process_fight` to be
skipped.

## Round segmentation — the clock is authoritative

`segment_fights()` combines three signals. **They are not peers** — the order below
is a strict authority ranking, and inverting it is what made round counts unreliable:

1. **Scoreboard clock** (`round_clock.derive_rounds_from_clock`) — decides the round
   **count** and **identity**. The timer is the only deterministic signal in the
   pipeline: it advances one second per second of video, so its slope against frame
   number is known a priori (`-1/fps`) and only the intercept is fitted, by median.
   That makes it robust from ~3 readings anywhere in the round instead of needing
   continuous coverage — which matters because broadcast overlays vanish during
   replays, corner shots and ground close-ups.
2. **Round number** — corroborates the clock and pins boundaries. Nothing may
   *depend* on it: plenty of overlays render a bare digit or omit it entirely.
3. **Fighter presence + engagement** — refines edges the clock could not pin, and is
   the sole signal when OCR fails.

**Detection alone cannot decide a round count.** It splits wherever "both fighters
visible and close together" fails for `MIN_ROUND_GAP_SECS`, which a ground scramble or
a camera cutaway produces routinely. When it is the only signal,
`enforce_round_plausibility()` applies physical constraints that need no OCR:

- only the **last** round may be short — only the last round can end in a finish, so a
  short non-final segment is a walkout or a tracking dropout and is *dropped* (merging
  it would drag the real round's start back across the walkout);
- gaps below `MIN_ROUND_BREAK_SECS` are detection dropouts inside one round, not
  breaks, so the halves are rejoined;
- the video must be long enough to hold the rounds claimed.

**Edges are only trusted where they were observed.** `ClockRound.start_anchored` /
`end_anchored` record whether a reading was actually seen near the top of the round or
near 0:00. An unanchored edge is extrapolation past all evidence — a round whose
overlay appeared late cannot say where it began, and a round ended by a knockout never
reaches 0:00, so clock-zero would fall *after* the fight stopped. `_reconcile_with_clock`
takes those edges from detection instead.

**The result carries its own verdict.** `quality.needs_review` / `review_reason` say
whether the scoreboard actually corroborated the round list, keyed on how many
mutually-consistent readings back each round (`ROUND_CLOCK_HEALTHY_SUPPORT`) rather
than on raw OCR coverage — an overlay visible 8% of the time still pins its rounds
exactly when every reading agrees. `pipeline.py` persists this via
`database.set_segmentation_review`, and the Annotate page shows a banner. Without it a
detection-only guess reaches the database indistinguishable from a verified one, which
is how a 3-round split of a 1-round fight went unnoticed until a human spotted it.

`eval/sanity.py` re-checks the same physical constraints label-free, so a regression
shows up in `python -m eval.cli sanity <video>` rather than in the annotation UI.

## `fight_processing.py` — single-transaction, idempotent write

`process_fight(pose_data: dict, fight_id: int, fps: int, rounds: list)` writes all
fight data in **one DB transaction**:

1. `DELETE FROM fight_events WHERE fight_id = :id AND source = 'prediction'` (plus
   unscoped deletes on `fighter_frames`/`rounds`) — makes re-running idempotent
   (no duplicate rows on retry or single-file re-run) without ever touching a
   hand-labelled `fight_events` row (`source = 'label'`), even though both now
   live in the same table. In practice a fight is never re-run once it exists
   (see "DB Schema" below), so this scoping is defensive insurance rather than
   a live concern — but it's what makes the merge safe if that ever changes.
2. Bulk-insert `rounds` into the `rounds` table.
3. Per-frame loop: collect bbox detections for `class_id` 0/1 into a batch list;
   flush every 1 000 rows via `db.flush()` (not `db.commit()`) to release memory
   without ending the transaction.
4. One `db.commit()` at the very end — either every row lands or none does.

The `processed = true` flag update is always the **caller's** responsibility
(`run_pipeline` for single-file, `run_batch` for batch), and only runs after this
transaction commits successfully.

## Frame-numbering contract

**Frames are 1-based.** The Nth frame of the video is frame N (first frame = 1).

- **Writer** (`process_fight`): `frame_number = index + 1` for `fighter_frames`,
  `fight_events`, and round boundaries.
- **Frontend** (`FighterOverlay`): `currentFrame = Math.floor(currentTime * fps) + 1`,
  using the `fps` returned in `FightResponse`.

`fps` is stored as an integer on the `fights` row (`round(cap.get(cv2.CAP_PROP_FPS))`)
and is the single source of truth for every frame↔seconds conversion. Never re-read fps
from disk or from a video file after registration.

## DB Schema

```sql
fighters       (id, first_name, last_name, nickname nullable, created_at)
fights         (id, video_path UNIQUE, fps, width, height, created_at,
                state, pid nullable, labeled_at nullable,
                reported_frames nullable, decoded_frames nullable,
                segmentation_needs_review, segmentation_review_reason nullable,
                red_fighter_id → fighters nullable, blue_fighter_id → fighters nullable)
               -- state: validating|invalid|queued|detecting|tracking|pose|corners|
               --   scoreboard|segmenting|analyzing|completed|failed|
               --   labeling_in_progress|labeling_complete
               -- labeled_at: durable "this fight has finalised ground truth" marker,
               --   set once by finish_labeling and never touched by the pipeline.
               -- reported_frames/decoded_frames: full-decode validation result,
               --   shown in the UI when state=invalid
               -- segmentation_needs_review/_reason: segmentation's own verdict on
               --   whether its round list was corroborated by the scoreboard, written
               --   by database.set_segmentation_review. Never touched by labelling.
               --   Surfaced as a banner on the Annotate page — see "Round segmentation".
rounds         (id, fight_id → fights, round_number, start_frame, end_frame)
               UNIQUE (fight_id, round_number)
fighter_frames (id, fight_id → fights, frame, corner, x1, y1, x2, y2, confidence, keypoints)
               -- `corner` is the appearance corner index (0=red, 1=blue), formerly `fighter_id`
fight_events   (id, fight_id → fights, source, kind, frame, end_frame nullable,
                description nullable, fighter_id → fighters nullable, corner nullable,
                action nullable, target nullable, success nullable, state nullable,
                value nullable, labeler nullable, created_at, is_verified nullable)
               -- is_verified: Training Data QA's verdict on a source='label'
               --   kind='point' row (True=confirmed, False=declined, NULL=not
               --   reviewed). Written only via backend PUT .../events/{id}/verify
               --   — never by this pipeline or by Annotate's own writes.
               --   training_data fights only: the backend returns 409 for a
               --   verdict on any other purpose. `reference` labels are held-out
               --   ground truth and are never QA'd (is_verified stays NULL).
               -- ONE table for both pipeline predictions and hand labels — told
               --   apart by two columns, not by which table a row is in:
               -- source: 'prediction' (written only by process_fight()/
               --   write_frames_and_rounds(), raw SQL, always 'prediction'+'point')
               --   | 'label' (written only by the Annotate frontend via
               --   backend event_service.py / routes, always source='label').
               --   process_fight()'s DELETE-and-rewrite is scoped
               --   `WHERE fight_id = :id AND source = 'prediction'`, so it can
               --   never destroy a hand-labelled row even though they share a
               --   table. Two CHECK constraints back this up structurally:
               --   `corner` only allowed when source='label', `fighter_id`
               --   only allowed when source='prediction'.
               -- kind: 'point' (a strike/state-change/round-boundary event at
               --   one `frame`; description required only for action=
               --   'fight_end', NULL otherwise — see below) | 'round' (human-
               --   confirmed round bounds — for source='label', seeded from
               --   the `rounds` table; `write_frames_and_rounds()` also writes
               --   real segmentation-derived round_start/round_end as
               --   source='prediction' kind='point' rows — a `training_data`/
               --   `reference` fight is NOT uniformly source='label') |
               --   'corner_swap' (labeller-marked red/blue flip; a slot->person
               --   map, NOT applied to the label->keypoint join — fighter_frames
               --   untouched, see plan/02c "Corner override") | 'excluded'
               --   (replay/camera-cut span, value=reason). end_frame NULL on a
               --   range kind means a start/end toggle is still open; always
               --   NULL on kind='point'.
               -- `corner` matches fighter_frames.corner (0=red, 1=blue) — both
               --   are track-slot pointers, not people: the labeller clicks the
               --   overlay box, so a swap is copied into the label and the two
               --   stay consistent. `fighter_id` is the opposite: a resolved
               --   identity (FK), only ever written by the pipeline.
```

`fight_events` carries structured columns for querying — `fighter_id` (FK to
`fighters`, resolved from the fight's corner assignment — prediction-only),
`action` (strike type / `round_start` / `clinch_initiated` …), `success` (True=landed,
False=missed, NULL=unknown — grappling/unconfirmed/non-strike), `state` (STRIKING/
CLINCH/GROUND on a state-change row, else NULL) — and `description`, which
`_insert_event()` **always passes as `None`** from every call site in this
module: the pipeline can never emit `fight_end` (the one action still
requiring a description), so nothing it writes needs one. `eval/predictions.py`
reads `action`/`success`/`state` directly and takes a strike's corner from
`fighter_id` against the fights row's `red_fighter_id`/`blue_fighter_id`
(`"unknown"` when corners were unassigned); its description regex only still
matters for legacy rows. Until that corner lookup existed it recognised strikes
by the regex alone, so every current-code fight scored 0 predicted strikes —
treat any `eval_runs` row with `tp + fp = 0` from before 2026-09-14 as that bug.
The frontend reconstructs the display text
on demand from these same columns (plus the `rounds` table, for round
markers) — see `frontend/src/utils/describeEvent.ts` and
`backend/CLAUDE.md`'s "Description is reconstructed, not stored".
The red→`red_fighter_id` / blue→`blue_fighter_id` mapping is read from the `fights`
row and threaded into `process_fight`; when corners are unassigned, `fighter_id` is NULL.

Indexes:
```sql
ix_fighter_frames_fight_frame   ON fighter_frames (fight_id, frame)
ix_rounds_fight_id              ON rounds (fight_id)
ix_fight_events_fight_id        ON fight_events (fight_id)
ix_fight_events_fighter_id      ON fight_events (fighter_id)
ix_fight_events_fighter_action  ON fight_events (fighter_id, action)
ix_fight_events_fight_source    ON fight_events (fight_id, source)
ix_fight_events_fight_kind      ON fight_events (fight_id, kind)
```

## Key Conventions
- `LABEL_ID`: `fighter_red=0`, `fighter_blue=1`, `referee=2` (see `constants.py`).
  These are **corner ids as written to `fighter_frames.corner`**, decided by
  `assign_corners` from appearance — not detector classes. The nano model happens
  to share the numbering, but `fighter_detection` collapses its 0/1 into a single
  "fighter" concept and never propagates the distinction.
- Torso rectangle: built from COCO keypoints `[5,6,11,12]` (left/right shoulder, left/right hip) — primary grappling signal
- **Fight-state classification (`determine_fight_state`) is three-way** — `STRIKING` / `CLINCH` / `GROUND`:
  - **Proximity axis** — torso-rect distance, normalised by average fighter scale, ≥ `DISTANCE_GRAPPLING_RATIO` (0.11) → `STRIKING`; below it the fighters are entangled (clinch or ground). When the distance or either fighter's scale is unusable (unconfident keypoints), no candidate is read at all for that frame — an unknown distance is never treated as "far apart".
  - **Posture axis** (`is_fighter_grounded`) — when entangled, `GROUND` if *either* fighter reads as grounded (knockdown / sprawl / scramble), else `CLINCH`. Primary signal: torso vector tilt from vertical > `TORSO_VERTICAL_ANGLE_THRESHOLD` (50°) — scale-invariant, always evaluated. Backup signal: head→ankle vertical span ÷ fighter scale < `GROUND_VERTICAL_SPAN_RATIO` (1.2) — only used when nose + both ankles are confident and a scale is available, since a hallucinated occluded ankle (routine in a standing clinch) collapses this ratio and misreads GROUNDED while standing.
  - **Temporal smoothing** — a majority vote (the categorical equivalent of a median filter) over a `FIGHT_STATE_SMOOTHING_WINDOW_SECS` (0.5s) rolling window of raw per-frame candidates, and a transition only commits once the smoothed candidate differs from the current state **and** at least `FIGHT_STATE_MIN_DWELL_SECS` (0.75s) has passed since the last transition.
  - `GRAPPLING_STATES = {CLINCH, GROUND}` is the set that replaces the old binary `GRAPPLING` check everywhere (the relaxed `frame_usable` bar, `clinch_*`/`ground_*` strike actions, skipping the recoil check).
  - **Strike/state detection only runs inside a detected round** — `process_fight`'s frame loop skips walkouts, between-round rest and the post-fight broadcast wrapper entirely (still writes `fighter_frames` for the whole video, for the frontend overlay).
  - **Mid-round replays are also excluded.** `fight_segmentation.detect_replay_ranges()` scans the scoreboard OCR samples for a run of `MIN_REPLAY_SAMPLES` (3) consecutive readings tagged `parse_error = "timer_smoothed_out"` by `scoreboard_overlay/extraction.py`'s `_smooth_samples()` — i.e. the on-screen timer jumped backward relative to the round's established direction, which is what a slow-motion replay clip looks like to the OCR. `segment_fights()` returns these as `excluded_ranges` alongside `rounds`; `pipeline.py` threads them into `process_fight(..., excluded_ranges=...)`, gated in the frame loop the same way as the round check. Requires OCR to actually be calibrating on the source video — falls back to `[]` (no exclusion) when scoreboard detection fails, same as segmentation's own OCR fallback.
- **Fighter identity pipeline (two-stage):**
  0. `fighter_detection.detect_fighters()`: the XL pose model detects every person in the frame with a box and 17 keypoints; the nano detector supplies a per-frame **mask** of fighter regions, and pose persons are matched one-to-one against it (Hungarian, `FIGHTER_SELECT_IOU_FLOOR`) to pick out the fighters. The referee and cornermen find no mask region and are dropped. Nano's red/blue class head is deliberately unused: it is an independent per-frame colour guess with no temporal consistency, which is the reason step 2 exists. Ignoring it also collapses a real failure mode — ultralytics NMS is class-aware by default, so a fighter the nano model is torn between red and blue on can survive NMS *twice*, as two overlapping boxes; one-to-one matching folds that pair back onto the single person it always was.
  1. `FighterTracker` (geometry-only, `models/FighterTracker.py`): constrained 2-slot tracker with IoU + centroid-distance cost matrix solved by Hungarian matching. Assigns a stable *provisional* `track_id` (0 or 1) per frame. Clinch frames (inter-fighter IoU > `CLINCH_IOU_THRESHOLD`) freeze velocity updates to prevent identity swaps. Keypoints ride along on the detection they arrived attached to — there is no box↔skeleton association step left to get wrong.
  2. `assign_corners()` (`video_processing/corner_assignment/`): **per-frame appearance-anchored re-ID.** Pass 1 reads the video once, builds per-detection descriptors (glove-tape `net_red`/`tape_total` + torso HSV hue histogram), identifies *clean frames* (fighters separated ≥ `DISTANCE_GRAPPLING_RATIO × avg fighter scale`, both well-posed, tape present), and bootstraps per-corner appearance templates from those frames. Pass 2 (no second video read — over cached descriptors) assigns each detection to a template using normalized tape + Bhattacharyya histogram distance with a hysteresis gate (`CORNER_SWAP_CONFIRM_SECS` converted to frames via the video's fps, consecutive frames before committing a flip). `corner` in `fighter_frames` now legitimately follows appearance across a mid-clinch tracker slot swap. Falls back to a whole-fight paired tape vote / model-class-vote path when template separation is below `CORNER_TEMPLATE_MIN_SEPARATION` (similar colors).

     **Verify with `python -m eval.corner_accuracy <fight_id>`.** It is label-free and needs no re-run — it reads the stored `corner` back and checks it against the fighters' kit colour. Corner assignment is the one output with a 50% failure mode that leaves everything self-consistent, so nothing else in `eval/` catches it: `sanity.py` checks structure, `score.py` needs labels, and hand labels inherit the error. Run it on every processed fight; treat `[FAIL]` (whole-fight inversion) and `[WARN]` (intermittent — uncorrected tracker swaps) as real, and treat "no decisive frames" as *unverified*, not as a pass.

     **When even the tape vote has too little evidence, corner is UNDETERMINED.** The fallback used to break that tie with the detector's red/blue class vote; `fighter_detection` no longer propagates it, so the mapping is left as identity and logged as unverified. Identity mapping keeps the two corners distinct and self-consistent — it does *not* claim they are the right way round, and a whole-fight inversion looks identical from inside the pipeline. `python -m eval.corner_accuracy <fight_id>` is what catches it.

     **Colour is only ever read relatively.** The red HSV band unavoidably overlaps skin, so an absolute red-pixel count is not a corner signal: before this was fixed, *every* fight in `runs/upload_pipeline.log` came back with both tracks overwhelmingly "red", and 29% of a whole `JURICvsNOGUEIRA` frame classified as red tape. Three rules keep that from deciding a corner, and none of them should be relaxed without re-measuring:
     - the wrist crop is sized to the **glove** (`TAPE_PATCH_RATIO`, small forearm multiplier) and gated at `TAPE_MIN_SATURATION = 150`, above the skin band;
     - counts are converted to **coverage fractions** of the sampled crop, never summed as raw pixels across the fight — a sum ranks fighters by how long each spent in close-up, which is exactly how `MILIDRAGOVICvsMOOSMAN` was assigned backwards for its whole length;
     - the two fighters are compared **within one frame** (they share lighting, exposure and skin tone, so the difference is the part that carries colour) and each frame contributes **one vote**.

     **`_is_clean_frame` uses `STRIKING_CORE_KEYPOINT_INDICES`, not `STRIKE_KEYPOINT_INDICES`.** Demanding all 15 strike joints required confident knees and ankles, which a broadcast camera occludes constantly — it returned **zero** clean frames across all 18,518 frames of `NAZHANDvsSTAROPOLI`, so the appearance path never ran and every tracker identity swap went uncorrected. Same relaxation, same reason, as `frame_usable` (see "Frame usability").

     **The slot→corner mapping is a bijection and hysteresis commits it atomically.** Confirming each slot on its own counter let one slot's flip commit while the other's was still pending, leaving *both* slots on the same corner in between; Pass 2 also has to relabel detections that produced no descriptor, or they keep a raw tracker slot id and collide with a relabelled opponent. Both bugs were live — fight 31 has 755 stored frames with duplicate corner ids. The `Invariant OK: no duplicate corner ids` line at the end of the step is what catches this; treat a `WARNING` there as a release blocker, not a diagnostic.
- **Frame usability** — `frame_usable(detections, fight_state) → bool` in `fight_processing_util.py` gates the fight-state machine (and the recoil head/hip history):
  - both fighters must be detected;
  - in `STRIKING`, both fighters' **core trunk joints** (`STRIKING_CORE_KEYPOINT_INDICES` = head + shoulders + hips) must be confident — requiring all 15 joints (`STRIKE_KEYPOINT_INDICES`) instead dropped ~95% of standing frames, since a broadcast camera occludes legs constantly;
  - in `GRAPPLING_STATES`, at least `GRAPPLING_MIN_VISIBLE_KEYPOINTS` confident joints each (fighters occlude each other in a tangle).
  - `is_frame_valid()` remains as the strict all-15-joints bool for `pose_verification.py` (which has no `fight_state` context).
  - The strike model is **not** gated by this — it only needs the attacker's skeleton at the centre frame, and handles a missing opponent or occluded joints itself (present/confidence channels).

### Strike detection — the action model

Strikes come from the trained skeleton action model in `action_model/` (see its
package docstring and `plan/04-stage2-model.md`), which **replaced the hand-tuned
rule cascade** (`detect_strikes`, `classify_punch_type`, the velocity/contact/
direction gates and their ~20 constants — all deleted 2026-09-26).

- **Training data:** only QA-confirmed (`is_verified IS TRUE`) hand labels from
  `purpose='training_data'` fights. **Validation:** `purpose='reference'` fights
  only, never data carved from a training fight. `python -m action_model.train`,
  then `--promote` copies the run's checkpoint to `action_model/weights/strike_model.pt`,
  the file the pipeline loads (committed, like `video_processing/weights.pt`).
- **Input:** a 1.2 s window (31 samples at a fixed 25 Hz, so 24/50 fps fights
  look the same) of the attacker's and opponent's 17 raw keypoints, centred on
  the attacker's torso, divided by `get_fighter_scale`, mirrored so the opponent
  is to the right. `action_model/windows.py` builds windows for both training and
  inference — one implementation, so they can't drift apart. `load_model`
  refuses a checkpoint built against a different `action_model/config.py`.
- **Output:** family (`none`/jab/cross/hook/uppercut/kick/knee — hand-agnostic;
  jab/cross are lead/rear) and target (head/body/leg).
- **Detection** (`action_model/inference.detect_strikes`): after the frame loop,
  `process_fight` scans every round minus replay ranges, for both fighters, one
  window per 1/25 s. `1 − P(none)` peaks ≥ `STRIKE_PROB_THRESHOLD` become
  strikes; each suppresses weaker peaks by the same fighter within
  `STRIKE_NMS_SECS`.
- **Action mapping** (`_strike_action` in `fight_processing.py`): punches →
  `{family}_{head|body}`, kicks → `head_kick`/`middle_kick`/`low_kick`, knees →
  `clinch_knee`/`ground_knee`. Punches thrown while the fight state is
  CLINCH/GROUND are written as non-specific `clinch_punch`/`ground_punch`: no
  QA-verified label has been a grappling punch, so the model's family there is
  untrained.
- **Measured** on reference fight 60 via its ai_labeled twin 62
  (`score-pair`, ±0.24 s): rule cascade P 57.1% / R 37.0% / F1 44.9%, family
  53.6%, target 61.4% → model P 48.2% / R 69.2% / F1 56.8%, family 53.2%, target
  84.4%. The thresholds were tuned on that same fight — there is no second
  reference fight yet, so treat these as optimistic.

**Keypoint smoothing:** raw pose coordinates are fed through a One-Euro filter (`make_keypoint_smoother` in `fight_processing_util.py`) per joint per axis; the smoothed skeletons feed the recoil check's head positions and the takedown-initiator hip history (the strike model reads raw keypoints — that's what it was trained on). Parameters: `ONE_EURO_MIN_CUTOFF`, `ONE_EURO_BETA`, `ONE_EURO_D_CUTOFF` in `constants.py`. Joints below `KEYPOINT_MIN_CONFIDENCE` are passed through *without* updating the filter state, so an occluded/hallucinated coordinate can't corrupt the history.

**Landed vs. attempted (`RECOIL_LOOKAHEAD_SECS`, `RECOIL_VELOCITY_RATIO`):** the model does not predict it. For each open-range strike, `_landed()` checks whether the defender's head (confidence-gated `get_head_center`) moved at > `RECOIL_VELOCITY_RATIO × defender_scale / sec` over `RECOIL_LOOKAHEAD_SECS` after the strike frame, reading the first usable frame at or after the lookahead. `success` is True/False, or None ("unconfirmed") when the defender's head isn't readable at contact or within 4× the lookahead. Grappling strikes always get None. No labels carry landed/missed yet, so this is unmeasured.

**`process_fight` signature:** `process_fight(pose_data, fight_id, fps, rounds=None, excluded_ranges=None, red_fighter_id=None, blue_fighter_id=None)` — `fps` is required, sourced from the `fights` row and passed by `pipeline.py`. Strike/state detection is gated to frames inside `rounds` and outside every `excluded_ranges` span (mid-round replays — see above); `fighter_frames` are still written for the whole video regardless. The strike model is loaded once per process on first call.

**Event vocabulary (structured columns — `description` is always NULL for these; the table below is what the frontend reconstructs, not what's stored):**

| Type | `action` | `fighter_id` | `success` | `state` |
|------|----------|--------------|-----------|---------|
| Open-range punch | `jab_head` / `cross_body` / `hook_head` / `uppercut_body` … | attacker | True/False/None (recoil proxy) | — |
| Open-range kick  | `head_kick` / `middle_kick` / `low_kick` | attacker | True/False/None | — |
| Clinch punch     | `clinch_punch` | attacker | None | — |
| Clinch knee      | `clinch_knee` | attacker | None | — |
| Ground punch     | `ground_punch` | attacker | None | — |
| Ground knee      | `ground_knee` | attacker | None | — |
| Fight state (clinch) | `clinch_initiated` (or NULL if no initiator determined) | initiator (nullable) | — | `CLINCH` |
| Fight state (ground) | `takedown_initiated` (or NULL) | initiator (nullable) | — | `GROUND` |
| Fight state (other)  | NULL | NULL | — | `STRIKING`/… |
| Round boundary   | `round_start` / `round_end` | — | — | — |

Each row also writes the structured columns: `action` holds the strike `type`
(`jab_head`, `middle_kick`, `clinch_punch`, …) or an event code (`round_start`,
`round_end`, `clinch_initiated`, `takedown_initiated`); `fighter_id` is the
attacker/initiator resolved via the corner→`fighters` mapping (NULL for round
events or unassigned corners); `success` is True/False for confirmed open-range
strikes (landed/missed) and NULL for grappling, end-of-video unconfirmed, and
non-strike events.

## Environment
- `.env` file required with `DATABASE_URL=postgresql://...`
- Model weights: `yolo26x-pose.pt` (XL pose — supplies every box and skeleton;
  expected in the working dir) and `video_processing/weights.pt` (custom nano
  YOLO — used *only* as the fighter/referee mask). Retraining the mask model
  single-class ("fighter" vs not) would lose nothing the pipeline uses: its
  red/blue head is already ignored.
- Videos placed in `fight_videos/` for batch processing
