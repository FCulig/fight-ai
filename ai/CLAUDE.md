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
│   ├── fighter_reidentification/
│   │   └── fighter_reidentification.py  # torchreid ReID, assigns class_id 0/1
│   └── pose_tracking/
│       └── pose_tracking.py  # YOLOv8x-pose on fighter crops → keypoints
├── fight_processing/
│   ├── fight_processing.py   # State machine + DB writes (fight_events, fighter_frames, rounds)
│   └── fight_processing_util.py
├── models/
│   ├── FightState.py         # Enum: STRIKING=1, GRAPPLING=2
│   ├── IdentityMemory.py     # EMA cosine-similarity ReID tracker (max 2 fighters)
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
| ReID | `track_fighters()` | reid dict |
| Pose tracking | `track_poses()` | pose dict |
| Scoreboard OCR | `extract_scoreboard_samples()` | samples dict |
| Segmentation | `segment_fights()` | rounds list |
| Fight processing | `process_fight()` | — (writes to DB) |

`fps` is read once from the `fights` row (extracted from the video at registration time)
and threaded in-memory to every step that needs it. No step re-reads fps from disk.

**Developer skip-flags** (`--detection-file`, `--reid-file`, `--pose-results`,
`--scoreboard-samples`) load a developer-supplied file into the in-memory dict at the
appropriate step. The pipeline never *produces* these files.

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
- Grappling detection: torso-rect distance < `DISTANCE_GRAPPLING_THRESHOLD` (20px) for `MIN_GRAPPLING_THRESHOLD` (3) consecutive frames → `FightState.GRAPPLING`
- When a fighter is not visible (missing/invalid keypoints): frame is skipped via `is_frame_valid()`, current state is persisted unchanged
- ReID: `IdentityMemory` caps at 2 IDs, uses EMA (0.9) + cosine similarity (threshold 0.75), force-assigns to closest when at capacity
- Keypoints: 17-point COCO format. Frame is only valid when both fighters have all 17 keypoints present

## Environment
- `.env` file required with `DATABASE_URL=postgresql://...`
- Model weights: `video_processing/weights.pt` (custom YOLO), `yolo26x-pose.pt` (pose, expected in working dir)
- Videos placed in `fight_videos/` for batch processing
