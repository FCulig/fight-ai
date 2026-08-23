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
│   ├── fight_processing.py   # State machine + DB writes (fight_events, fighter_frames, rounds)
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
│   ├── labels_db.py          # Builds FightLabels from label_events/label_spans (Postgres)
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
  `determine_fight_state` classifier and everything `detect_strikes` reads. Run
  `python -m eval.cli score <video>` before and after and put both numbers in
  the commit message; score's FIGHT STATE and STRIKE DETECTION sections are what
  measure these. These thresholds are heavily coupled — several existing values
  are compensating for bugs elsewhere rather than describing anything physical
  (see `eval/README.md`), so tuning by eye on one video reliably makes another
  worse.
- **The rule stops there — do not demand a `score` delta for the rest.**
  Segmentation (`MIN_FIGHT_END_GAP_SECS` … `ROUND_DISENGAGED_RATIO`) and
  scoreboard overlay (`SCOREBOARD_*`) constants are out of scope. Scoreboard OCR
  has no `score` section at all. Segmentation does have one (ROUNDS), but its
  ground truth is currently untrustworthy: `label_spans` of kind `round` are
  **seeded from the pipeline's own `rounds` output** the first time the Annotate
  page opens a fight (`backend/app/services/label_span_service.py`), so unless a
  human has actually moved those boundaries, round IoU reads ~1.000 against the
  prediction itself and a genuine improvement scores as a regression. Check that
  the span differs from the `rounds` row before believing a round-IoU number.
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

1. `DELETE FROM fight_events / fighter_frames / rounds WHERE fight_id = :id` — makes
   re-running idempotent (no duplicate rows on retry or single-file re-run).
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
               --   set once by finish_labeling and never touched by the pipeline —
               --   state alone is NOT that marker, since re-running a labelled fight
               --   through the AI pipeline (to score it) resets state but not this.
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
fight_events   (id, fight_id → fights, frame, description,
                fighter_id → fighters nullable, action nullable, success nullable, state nullable)
               -- PIPELINE PREDICTIONS ONLY. process_fight() DELETEs and rewrites this
               --   table on every run — never write hand labels here.
label_events   (id, fight_id → fights, frame, corner nullable, action nullable,
                target nullable, success nullable, description, labeler nullable, created_at)
               -- HAND LABELS ONLY, written by the Annotate frontend (backend
               --   label_event_service.py / routes). `corner` matches
               --   fighter_frames.corner (0=red, 1=blue). Never touched by the
               --   pipeline — this is what makes re-running the AI pipeline over a
               --   labelled fight safe.
label_spans    (id, fight_id → fights, kind, start_frame, end_frame nullable, value nullable, created_at)
               -- kind: 'round' (human-confirmed round bounds, seeded from the
               --   `rounds` table) | 'corner_swap' (labeller-marked red/blue flip,
               --   applied at export time, fighter_frames itself untouched) |
               --   'excluded' (replay/camera-cut span, value=reason).
               --   end_frame NULL means a start/end toggle is still open.
```

`fight_events` carries both the free-form `description` (NOT NULL) and structured
columns for querying: `fighter_id` (FK to `fighters`, resolved from the fight's
corner assignment), `action` (strike type / `round_start` / `clinch_initiated` …),
`success` (True=landed, False=missed, NULL=unknown — grappling/unconfirmed/non-strike),
`state` (STRIKING/CLINCH/GROUND on a state-change row, else NULL — the structured
counterpart of the free-text "Fight state changed to FightState.X" description;
`eval/predictions.py` reads this column directly and only falls back to a regex over
`description` for rows written before it existed).
The red→`red_fighter_id` / blue→`blue_fighter_id` mapping is read from the `fights`
row and threaded into `process_fight`; when corners are unassigned, `fighter_id` is NULL.

Indexes:
```sql
ix_fighter_frames_fight_frame   ON fighter_frames (fight_id, frame)
ix_rounds_fight_id              ON rounds (fight_id)
ix_fight_events_fight_id        ON fight_events (fight_id)
ix_fight_events_fighter_id      ON fight_events (fighter_id)
ix_fight_events_fighter_action  ON fight_events (fighter_id, action)
ix_label_events_fight_id        ON label_events (fight_id)
ix_label_spans_fight_id         ON label_spans (fight_id)
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
  - `GRAPPLING_STATES = {CLINCH, GROUND}` is the set that replaces the old binary `GRAPPLING` check everywhere (clinch-strike detection, contact-gate skipping).
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

     **`_is_clean_frame` uses `STRIKING_CORE_KEYPOINT_INDICES`, not `STRIKE_KEYPOINT_INDICES`.** Demanding all 15 strike joints required confident knees and ankles, which a broadcast camera occludes constantly — it returned **zero** clean frames across all 18,518 frames of `NAZHANDvsSTAROPOLI`, so the appearance path never ran and every tracker identity swap went uncorrected. Same relaxation, same reason, as `frame_validity` (see "Frame validity").

     **The slot→corner mapping is a bijection and hysteresis commits it atomically.** Confirming each slot on its own counter let one slot's flip commit while the other's was still pending, leaving *both* slots on the same corner in between; Pass 2 also has to relabel detections that produced no descriptor, or they keep a raw tracker slot id and collide with a relabelled opponent. Both bugs were live — fight 31 has 755 stored frames with duplicate corner ids. The `Invariant OK: no duplicate corner ids` line at the end of the step is what catches this; treat a `WARNING` there as a release blocker, not a diagnostic.
- **Frame validity** — graded via `frame_validity(detections, fight_state) → "FULL" | "PARTIAL" | "INVALID"` in `fight_processing_util.py`:
  - `FULL` — both fighters have all strike-relevant joints (head, shoulders, elbows, wrists, hips, knees, ankles — `STRIKE_KEYPOINT_INDICES`) above `KEYPOINT_MIN_CONFIDENCE`. Open-range striking runs as normal.
  - `PARTIAL` — both fighters detected, below the strict `FULL` bar but with enough of the right joints to run strike detection:
    - in `GRAPPLING_STATES`, the per-joint bar is relaxed to `GRAPPLING_MIN_VISIBLE_KEYPOINTS` confident joints — only grappling strike detection (`detect_strikes(..., grappling=True)`) runs;
    - in `STRIKING`, both fighters' **core trunk joints** (`STRIKING_CORE_KEYPOINT_INDICES` = head + shoulders + hips) must be confident — open-range `detect_strikes(..., grappling=False)` runs with the full contact gate. The core joints alone give the torso centre, torso rectangle, head centre and scale (everything the contact gate needs from a defender); the attacking arm is gated per-limb inside `detect_strikes`, so a blurred wrist no longer discards the whole frame. **This is what lets open-range punches register** — requiring all 15 joints up front dropped ~95% of standing frames (legs/ankles are routinely occluded in a broadcast view), including the exact impact frames.
    - In both cases the per-limb confidence gate inside `detect_strikes` suppresses limbs with occluded joints.
  - `INVALID` — fewer than 2 fighters, or joint completeness below even the relaxed bar. Frame is skipped.
  - `is_frame_valid()` remains as a thin `FULL`-only bool wrapper for `pose_verification.py` (which has no `fight_state` context).
  - **Known limitation:** when the *defender* is fully occluded (1 detection), the frame is still `INVALID` — `detect_strikes` needs both fighters' torso centers. Recovering fully-occluded-defender ground frames is a follow-up task.

### Strike detection

Strike detection runs in `fight_processing_util.detect_strikes()` on every valid frame and fires for both striking and grappling fight states. All thresholds are **scale- and fps-invariant**:

- **Scale reference (`get_fighter_scale`):** torso length (shoulder midpoint → hip midpoint) in pixels, per fighter per frame. Falls back to shoulder width when the torso is foreshortened (torso length < `TORSO_SCALE_MIN_RATIO × shoulder width`) or hips aren't confident. Returns `None` when shoulders themselves aren't confident — the denominator of every normalised threshold below, so `detect_strikes` skips the whole frame rather than compute on a hallucinated scale (see `models/geometry.py`). Used to normalise all distance and velocity thresholds so they are invariant to camera zoom and fighter distance.
- **Velocity:** distal-joint displacement against a **per-limb confident baseline** (the last frame in which *that* limb's joints were confident, stored in `strike_state[fighter][limb]["vel_base"]`), minus torso displacement over the same interval (removes locomotion), converted to px/sec (× `fps`) then normalised by attacker scale → `scale/sec`. Compared against `PUNCH_VELOCITY_RATIO` / `KICK_VELOCITY_RATIO`. The baseline is reset when older than ~0.3 s (`max(1, round(fps*0.3))` frames) so a long occlusion never produces a stale spike.
- **Contact distance:** normalised by *defender* scale, compared against `HEAD_CONTACT_RATIO` / `TORSO_CONTACT_RATIO` / `LEG_CONTACT_RATIO`.

**Three gates must all pass to record a strike:**

1. **Extension / angle** — straight arm (angle > `ARM_EXTENSION_THRESHOLD` = 140°) *or* bent arm (`PUNCH_BENT_ANGLE_MIN`–`PUNCH_BENT_ANGLE_MAX` = 60–139°) for punches; straight leg for kicks. The bent-arm path catches hooks and uppercuts.
2. **Scale-normalised velocity** — must exceed the ratio threshold for `STRIKE_EXTENSION_SECS` (converted to frames via fps) consecutive frames.
3. **Contact proximity** — wrist/ankle must be within the ratio threshold of the target body zone. In grappling mode this open-range proximity gate is replaced by a **directional gate** (see below): a relaxed proximity sanity-check plus a velocity-alignment-toward-target check, because raw proximity no longer discriminates a strike from pummeling once fighters are entangled.

**Per-limb keypoint confidence gating:** if any of the three joints (proximal/mid/distal) for a limb is below `KEYPOINT_MIN_CONFIDENCE`, that limb is skipped for the frame. Prevents velocity spikes from hallucinated keypoint coordinates during occlusion.

**Keypoint smoothing:** raw pose coordinates are fed through a One-Euro filter (`make_keypoint_smoother` in `fight_processing_util.py`) per joint per axis before any velocity computation. Parameters: `ONE_EURO_MIN_CUTOFF`, `ONE_EURO_BETA`, `ONE_EURO_D_CUTOFF` in `constants.py`. Smoothers are created once per fighter at the start of `process_fight` and persist across frames. Joints below `KEYPOINT_MIN_CONFIDENCE` are passed through *without* updating the filter state — occluded/hallucinated coordinates must not corrupt the One-Euro history and bleed into later frames when the joint reappears.

**Grappling / clinch / ground strikes:** when `current_fight_state in GRAPPLING_STATES`, `detect_strikes` is called with `grappling=True` (and `ground=True` when the state is `GROUND`). Lower velocity ratios (`GRAPPLING_PUNCH_VELOCITY_RATIO`, `GRAPPLING_KICK_VELOCITY_RATIO`) are used, the open-range contact gate is replaced by the **directional gate**, and events are emitted immediately. The directional gate rejects wrestling/pummeling false positives: a grappling strike must (a) pass a relaxed proximity sanity-check (`GRAPPLING_HEAD_CONTACT_RATIO` / `GRAPPLING_TORSO_CONTACT_RATIO`) **and** (b) have its end-effector velocity aligned toward the nearest target zone (cosine > `GRAPPLING_STRIKE_DIRECTION_MIN`). Swimming for underhooks, framing, gripping and posturing move the hand laterally or pull it back, so they fall below the alignment threshold. To make grappling detection stricter, raise `GRAPPLING_STRIKE_DIRECTION_MIN` (toward 1.0) and/or `GRAPPLING_PUNCH_VELOCITY_RATIO`. Labels: `clinch_punch` / `clinch_knee` in standing clinch, `ground_punch` / `ground_knee` (ground-and-pound) when on the ground. PARTIAL frames (relaxed joint bar) also run this grappling path.

**Velocity uses raw `fps` (not gap-normalized):** `detect_strikes` computes velocity as the displacement from the limb's last-confident baseline to the current frame, multiplied by `fps` — **never divided by the frame gap.** Because the punching wrist blurs and drops below `KEYPOINT_MIN_CONFIDENCE` at impact, those frames are skipped per-limb and the baseline holds, so the displacement naturally spans the blur and captures the full strike. **This is intentional and the velocity thresholds (`PUNCH_VELOCITY_RATIO`, etc.) are tuned against it** — dividing by the gap to get the true per-frame average pushes real open-range punches below threshold and they stop being detected. Do not "normalize" velocity by the frame gap. (The baseline is per-limb and confidence-gated, so it never uses an occluded/hallucinated coordinate — earlier this relied on the strict `FULL` bar guaranteeing a confident previous frame.)

**Punch classification (`classify_punch_type`):**
- Straight path + lead hand (same side as foot closer to opponent) → `jab`
- Straight path + rear hand → `cross`
- Bent path + wrist moving mostly upward → `uppercut`
- Bent path + wrist moving mostly laterally → `hook`

Final open-range punch event type: `{punch_type}_{target}` e.g. `jab_head`, `cross_body`, `hook_head`, `uppercut_head`. Kick types remain `head_kick`, `middle_kick`, `low_kick`.

**Head-vs-body target classification (open-range punches):** once a punch is *accepted* (wrist within `HEAD_CONTACT_RATIO` of the head **or** `TORSO_CONTACT_RATIO` of the torso rect — unchanged acceptance reach), the `_head`/`_body` label is decided by the **nearest anatomical region**, not a head-first priority. Each candidate distance is "how far *outside* the region the wrist is" (0 when inside): the head circle (`get_head_radius`, centred on `get_head_center`) vs the torso rectangle (`distance_to_rect`). Label is `_head` when `head_region_dist <= torso_region_dist`, else `_body`. This fixes the prior failure where a head shot landing just outside the point-radius head zone fell through to the torso test and was mislabelled `_body` simply because the head sits directly above the torso rectangle's top edge.
- `get_head_center` is **confidence-gated**: it averages only the confident points among nose + ears, falling back to the nose, then to a point `HEAD_ABOVE_SHOULDER_RATIO × scale` above the shoulder midpoint. A hallucinated far ear (common side-on) no longer drags the head centre toward the torso and corrupts the split.
- `get_head_radius` uses the ear-to-ear span × `HEAD_RADIUS_EAR_FACTOR` when both ears are confident, else `HEAD_RADIUS_SCALE_RATIO × scale`, clamped to `[HEAD_RADIUS_MIN_RATIO, HEAD_RADIUS_MAX_RATIO] × scale`.
- Kicks still use the original head/middle/low priority ladder, but benefit from the improved confidence-gated head centre.

**Landed vs. attempted (`RECOIL_LOOKAHEAD_SECS`, `RECOIL_VELOCITY_RATIO`):** for each candidate open-range strike, `process_fight` defers the event write into a `pending_strikes` queue. After `RECOIL_LOOKAHEAD_SECS` (converted to frames via fps) it checks whether the defender's head moved at > `RECOIL_VELOCITY_RATIO × defender_scale / sec` — a proxy for head recoil on impact. The final event description is suffixed with `(landed)`, `(missed)`, or `(unconfirmed)` for strikes at the very end of the video.

**`process_fight` signature:** `process_fight(pose_data, fight_id, fps, rounds=None, excluded_ranges=None, red_fighter_id=None, blue_fighter_id=None)` — `fps` is required, sourced from the `fights` row and passed by `pipeline.py`. Strike/state detection is gated to frames inside `rounds` and outside every `excluded_ranges` span (mid-round replays — see above); `fighter_frames` are still written for the whole video regardless.

**Event vocabulary in `fight_events.description`:**

| Type | Example description |
|------|---------------------|
| Open-range punch | `fighter_red threw a jab_head (landed)` |
| Open-range kick  | `fighter_blue threw a middle_kick (missed)` |
| Clinch punch     | `fighter_red threw a clinch_punch` |
| Clinch knee      | `fighter_blue threw a clinch_knee` |
| Ground punch     | `fighter_red threw a ground_punch` |
| Ground knee      | `fighter_blue threw a ground_knee` |
| Fight state (clinch) | `Fight state changed to FightState.CLINCH, clinch initiated by fighter_red` |
| Fight state (ground) | `Fight state changed to FightState.GROUND, takedown initiated by fighter_red` |
| Round boundary   | `Round 1 started` / `Round 1 ended` |

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
