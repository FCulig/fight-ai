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
│   ├── video_processing.py   # YOLO detection → returns detection dict (no disk write)
│   ├── fight_segmentation.py # Fuses OCR + detection signals → round list
│   ├── scoreboard_overlay/   # Scoreboard overlay OCR package
│   │   ├── __init__.py       # Re-exports + parse_roi_override()
│   │   ├── calibration.py    # Bottom-strip OCR to auto-detect overlay ROI
│   │   ├── extraction.py     # Per-frame OCR sampling + smoothing
│   │   ├── parsers.py        # Org-agnostic round/timer regexes
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
│       └── pose_tracking.py  # YOLOv8x-pose on fighter crops → keypoints
├── fight_processing/
│   ├── fight_processing.py   # State machine + DB writes (fight_events, fighter_frames, rounds)
│   └── fight_processing_util.py
├── models/
│   ├── FightState.py         # Enum: STRIKING=1, CLINCH=2, GROUND=3 (+ GRAPPLING_STATES set)
│   ├── FighterTracker.py     # Constrained 2-slot tracker with Hungarian matching
│   ├── geometry.py           # Shared pure-geometry helpers: get_torso_rectangle,
│   │                         #   calculate_distance_between_fighters, get_fighter_scale.
│   │                         #   Lives here (not in fight_processing) so corner_assignment
│   │                         #   can import them without a layering inversion.
│   └── constants.py          # All thresholds and label IDs
└── database.py               # SQLAlchemy SessionLocal
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

## Entry Points

```
python main.py              # batch mode — scans fight_videos/, processes unprocessed fights
python main.py fight.mp4    # single-file mode
```

### Batch mode (`run_batch`)
1. Creates `fight_videos/` if absent and prints a hint, then returns early.
2. Scans for `.mp4` / `.mkv` / `.mov`. For each file extracts `fps`, `width`, `height`
   via `cv2.VideoCapture` and upserts a `fights` row (`ON CONFLICT DO NOTHING` — never
   disturbs an existing row's flag or metadata).
3. Queries `SELECT … FROM fights WHERE processed = false ORDER BY id`.
4. Calls `run_pipeline(video_file, fight_id=row.id, …)` for each.
5. On success: `UPDATE fights SET processed = true, processed_at = NOW()`.
6. On exception: logs traceback, continues to next fight (row stays `processed = false`).

**Accepted limitation:** a file replaced at the same path is not re-detected by batch
(row already exists, `DO NOTHING`). Re-running such a video requires single-file mode,
whose upsert resets the `processed` flag.

### Single-file mode (`run_pipeline` with `fight_id=None`)
Upserts the fight record (`ON CONFLICT DO UPDATE SET fps/width/height/processed=false`)
so any existing child rows are treated as stale, then runs the full pipeline. After
`process_fight` succeeds, `run_pipeline` itself issues
`UPDATE fights SET processed = true, processed_at = NOW()`.

## Pipeline — fully in-memory data flow

**No intermediate data files are ever written.** Each step returns its output dict and
the next step consumes it directly. PostgreSQL is the only persistent data store.

| Step | Function | Returns |
|------|----------|---------|
| YOLO detection | `process_video()` | detection dict |
| Fighter tracking | `track_fighters()` | track dict (provisional track_id 0/1) |
| Pose tracking | `track_poses()` | pose dict (+ keypoints) |
| Corner assignment | `assign_corners()` | pose dict (class_id remapped to red=0/blue=1) |
| Scoreboard OCR | `extract_scoreboard_samples()` | samples dict |
| Segmentation | `segment_fights()` | rounds list |
| Fight processing | `process_fight()` | — (writes to DB) |

`fps` is read once from the `fights` row (extracted from the video at registration time)
and threaded in-memory to every step that needs it. No step re-reads fps from disk.

**Developer skip-flags** (`--detection-file`, `--track-file`, `--pose-results`,
`--scoreboard-samples`) load a developer-supplied file into the in-memory dict at the
appropriate step. The pipeline never *produces* these files.
`--reid-file` is a deprecated alias for `--track-file`.

**Diagnostic outputs** (`--verify-pose` / `--verify-scoreboard` debug videos and
scoreboard calibration debug images) are opt-in artifacts and are not part of the data
flow. They remain as explicitly-requested disk outputs and cause `process_fight` to be
skipped.

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
fights         (id, video_path UNIQUE, fps, width, height, created_at, processed, processed_at)
rounds         (id, fight_id → fights, round_number, start_frame, end_frame)
               UNIQUE (fight_id, round_number)
fighter_frames (id, fight_id → fights, frame, fighter_id, x1, y1, x2, y2, confidence)
fight_events   (id, fight_id → fights nullable, frame, description)
```

Indexes:
```sql
ix_fighter_frames_fight_frame ON fighter_frames (fight_id, frame)
ix_rounds_fight_id            ON rounds (fight_id)
ix_fight_events_fight_id      ON fight_events (fight_id)
```

## Key Conventions
- Fighter labels: `fighter_red=0`, `fighter_blue=1`, `referee=2` (see `constants.py`)
- Torso rectangle: built from COCO keypoints `[5,6,11,12]` (left/right shoulder, left/right hip) — primary grappling signal
- **Fight-state classification (`determine_fight_state`) is three-way** — `STRIKING` / `CLINCH` / `GROUND`:
  - **Proximity axis** — torso-rect distance ≥ `DISTANCE_GRAPPLING_THRESHOLD` (20px) → `STRIKING`; below it the fighters are entangled (clinch or ground).
  - **Posture axis** (`is_fighter_grounded`, scale-invariant, OR of two signals) — when entangled, `GROUND` if *either* fighter reads as grounded (knockdown / sprawl / scramble), else `CLINCH`. Signals: torso vector tilt from vertical > `TORSO_VERTICAL_ANGLE_THRESHOLD` (50°), **or** head→ankle vertical span ÷ fighter scale < `GROUND_VERTICAL_SPAN_RATIO` (1.2).
  - **Hysteresis** — per-candidate consecutive-frame counters (`{"striking","clinch","ground"}`). STRIKING/CLINCH transition after `MIN_GRAPPLING_THRESHOLD` (3) frames; GROUND after the slower `MIN_GROUND_THRESHOLD` (5).
  - `GRAPPLING_STATES = {CLINCH, GROUND}` is the set that replaces the old binary `GRAPPLING` check everywhere (clinch-strike detection, contact-gate skipping).
- **Fighter identity pipeline (two-stage):**
  1. `FighterTracker` (geometry-only, `models/FighterTracker.py`): constrained 2-slot tracker with IoU + centroid-distance cost matrix solved by Hungarian matching. Assigns a stable *provisional* `track_id` (0 or 1) per frame. Clinch frames (inter-fighter IoU > `CLINCH_IOU_THRESHOLD`) freeze velocity updates to prevent identity swaps. Each detection also carries `model_class_id` (the original YOLO class) for the fallback below.
  2. `assign_corners()` (`video_processing/corner_assignment/`): **per-frame appearance-anchored re-ID.** Pass 1 reads the video once, builds per-detection descriptors (glove-tape `net_red`/`tape_total` + torso HSV hue histogram), identifies *clean frames* (fighters separated ≥ `DISTANCE_GRAPPLING_THRESHOLD`, both well-posed, tape present), and bootstraps per-corner appearance templates from those frames. Pass 2 (no second video read — over cached descriptors) assigns each detection to a template using normalized tape + Bhattacharyya histogram distance with a hysteresis gate (`CORNER_SWAP_CONFIRM_FRAMES` consecutive frames before committing a flip). `fighter_id` in `fighter_frames` now legitimately follows appearance across a mid-clinch tracker slot swap. Falls back to the original whole-fight tape-vote / model-class-vote path when template separation is below `CORNER_TEMPLATE_MIN_SEPARATION` (similar colors).
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

- **Scale reference (`get_fighter_scale`):** torso length (shoulder midpoint → hip midpoint) in pixels, per fighter per frame. Falls back to shoulder width when the torso is foreshortened. Used to normalise all distance and velocity thresholds so they are invariant to camera zoom and fighter distance.
- **Velocity:** distal-joint displacement against a **per-limb confident baseline** (the last frame in which *that* limb's joints were confident, stored in `strike_state[fighter][limb]["vel_base"]`), minus torso displacement over the same interval (removes locomotion), converted to px/sec (× `fps`) then normalised by attacker scale → `scale/sec`. Compared against `PUNCH_VELOCITY_RATIO` / `KICK_VELOCITY_RATIO`. The baseline is reset when older than ~0.3 s (`max(1, round(fps*0.3))` frames) so a long occlusion never produces a stale spike.
- **Contact distance:** normalised by *defender* scale, compared against `HEAD_CONTACT_RATIO` / `TORSO_CONTACT_RATIO` / `LEG_CONTACT_RATIO`.

**Three gates must all pass to record a strike:**

1. **Extension / angle** — straight arm (angle > `ARM_EXTENSION_THRESHOLD` = 140°) *or* bent arm (`PUNCH_BENT_ANGLE_MIN`–`PUNCH_BENT_ANGLE_MAX` = 60–139°) for punches; straight leg for kicks. The bent-arm path catches hooks and uppercuts.
2. **Scale-normalised velocity** — must exceed the ratio threshold for `STRIKE_EXTENSION_FRAMES` consecutive frames.
3. **Contact proximity** — wrist/ankle must be within the ratio threshold of the target body zone. Skipped entirely in grappling mode (fighters are already touching).

**Per-limb keypoint confidence gating:** if any of the three joints (proximal/mid/distal) for a limb is below `KEYPOINT_MIN_CONFIDENCE`, that limb is skipped for the frame. Prevents velocity spikes from hallucinated keypoint coordinates during occlusion.

**Keypoint smoothing:** raw pose coordinates are fed through a One-Euro filter (`make_keypoint_smoother` in `fight_processing_util.py`) per joint per axis before any velocity computation. Parameters: `ONE_EURO_MIN_CUTOFF`, `ONE_EURO_BETA`, `ONE_EURO_D_CUTOFF` in `constants.py`. Smoothers are created once per fighter at the start of `process_fight` and persist across frames. Joints below `KEYPOINT_MIN_CONFIDENCE` are passed through *without* updating the filter state — occluded/hallucinated coordinates must not corrupt the One-Euro history and bleed into later frames when the joint reappears.

**Grappling / clinch / ground strikes:** when `current_fight_state in GRAPPLING_STATES`, `detect_strikes` is called with `grappling=True` (and `ground=True` when the state is `GROUND`). Lower velocity ratios (`GRAPPLING_PUNCH_VELOCITY_RATIO`, `GRAPPLING_KICK_VELOCITY_RATIO`) are used, the contact gate is skipped, and events are emitted immediately. Labels: `clinch_punch` / `clinch_knee` in standing clinch, `ground_punch` / `ground_knee` (ground-and-pound) when on the ground. PARTIAL frames (relaxed joint bar) also run this grappling path.

**Velocity uses raw `fps` (not gap-normalized):** `detect_strikes` computes velocity as the displacement from the limb's last-confident baseline to the current frame, multiplied by `fps` — **never divided by the frame gap.** Because the punching wrist blurs and drops below `KEYPOINT_MIN_CONFIDENCE` at impact, those frames are skipped per-limb and the baseline holds, so the displacement naturally spans the blur and captures the full strike. **This is intentional and the velocity thresholds (`PUNCH_VELOCITY_RATIO`, etc.) are tuned against it** — dividing by the gap to get the true per-frame average pushes real open-range punches below threshold and they stop being detected. Do not "normalize" velocity by the frame gap. (The baseline is per-limb and confidence-gated, so it never uses an occluded/hallucinated coordinate — earlier this relied on the strict `FULL` bar guaranteeing a confident previous frame.)

**Punch classification (`classify_punch_type`):**
- Straight path + lead hand (same side as foot closer to opponent) → `jab`
- Straight path + rear hand → `cross`
- Bent path + wrist moving mostly upward → `uppercut`
- Bent path + wrist moving mostly laterally → `hook`

Final open-range punch event type: `{punch_type}_{target}` e.g. `jab_head`, `cross_body`, `hook_head`, `uppercut_head`. Kick types remain `head_kick`, `middle_kick`, `low_kick`.

**Landed vs. attempted (`RECOIL_LOOKAHEAD_FRAMES`, `RECOIL_VELOCITY_RATIO`):** for each candidate open-range strike, `process_fight` defers the event write into a `pending_strikes` queue. After `RECOIL_LOOKAHEAD_FRAMES` frames it checks whether the defender's head moved at > `RECOIL_VELOCITY_RATIO × defender_scale / sec` — a proxy for head recoil on impact. The final event description is suffixed with `(landed)`, `(missed)`, or `(unconfirmed)` for strikes at the very end of the video.

**`process_fight` signature:** `process_fight(pose_data, fight_id, fps, rounds=None)` — `fps` is a required parameter (previously missing), sourced from the `fights` row and passed by `pipeline.py`.

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

## Environment
- `.env` file required with `DATABASE_URL=postgresql://...`
- Model weights: `video_processing/weights.pt` (custom YOLO), `yolo26x-pose.pt` (pose, expected in working dir)
- Videos placed in `fight_videos/` for batch processing
