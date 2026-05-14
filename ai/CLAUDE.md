# Fight AI — Python Video Processing Library

## Workflow
- Always apply changes directly to the local working directory
- Never open PRs or suggest creating pull requests

## What it does
Accepts MMA fight videos, runs ML inference to detect fight events (grappling, state transitions), and writes results to PostgreSQL. Data is later served to the backend for video playback.

## Project Structure
```
ai/
├── main.py                   # Argument parser + dispatcher ONLY — no business logic
├── pipeline.py               # All orchestration logic for both pipeline modes
├── debug.py                  # DebugContext — centralised debug output router
├── manifest.py               # Writes runs/manifest.json at end of each run
├── video_processing/
│   ├── video_processing.py   # YOLO detection → runs/detection_results.json
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
│   ├── fight_processing.py   # State machine + DB event writes
│   └── fight_processing_util.py
├── models/
│   ├── FightState.py         # Enum: STRIKING=1, GRAPPLING=2
│   ├── IdentityMemory.py     # EMA cosine-similarity ReID tracker (max 2 fighters)
│   └── constants.py          # All thresholds and label IDs
└── database.py               # SQLAlchemy SessionLocal
```

## Architecture Rules
- **`main.py` is a pure argument parser and dispatcher.** It contains no business
  logic whatsoever — only `argparse` setup and calls to `pipeline.py` functions.
  Do not add conditional logic, file path construction, timing, or imports of
  processing modules to `main.py`.
- **`pipeline.py` owns all orchestration.** Step ordering, fallback handling,
  timing measurement, output path construction, and manifest writing all live here.
- **`debug.py / DebugContext`** is the single route for all debug output (images,
  JSON snapshots, log lines). Never add scattered `print`/`cv2.imwrite` for debug
  purposes — use `ctx.save_image`, `ctx.save_json`, `ctx.log` instead.
- **`constants.py`** is the single source of truth for all numeric thresholds.
  Never hardcode a threshold or frame-count in a processing module.

## Processing Pipeline
1. `video_processing.py` — custom YOLO (`weights.pt`, conf=0.25) detects fighters + referee, saves `runs/detection_results.json`
2. `fighter_reidentification.py` — torchreid (`osnet_x1_0`) assigns stable `class_id` 0 (red) or 1 (blue) via `IdentityMemory`
3. `pose_tracking.py` — crops each fighter bbox, runs `yolo26x-pose.pt`, shifts keypoints back to frame coordinates, saves `runs/pose_results.json`
4. `fight_processing.py` — reads pose results, runs state machine, writes `fight_events` rows to PostgreSQL on state transitions

## Key Conventions
- Fighter labels: `fighter_red=0`, `fighter_blue=1`, `referee=2` (see `constants.py`)
- Torso rectangle: built from COCO keypoints `[5,6,11,12]` (left/right shoulder, left/right hip) — primary grappling signal
- Grappling detection: torso-rect distance < `DISTANCE_GRAPPLING_THRESHOLD` (20px) for `MIN_GRAPPLING_THRESHOLD` (3) consecutive frames → `FightState.GRAPPLING`
- When a fighter is not visible (missing/invalid keypoints): frame is skipped via `is_frame_valid()`, current state is persisted unchanged
- ReID: `IdentityMemory` caps at 2 IDs, uses EMA (0.9) + cosine similarity (threshold 0.75), force-assigns to closest when at capacity
- Keypoints: 17-point COCO format. Frame is only valid when both fighters have all 17 keypoints present

## Database
- PostgreSQL via SQLAlchemy. Session from `database.SessionLocal`
- Fight events written to `fight_events(frame, description)` on state change

## Environment
- `.env` file required with `DATABASE_URL=postgresql://...`
- Model weights: `video_processing/weights.pt` (custom YOLO), `yolo26x-pose.pt` (pose, expected in working dir)
- Frames extracted to `frames/frame_N.jpg` before ReID step
- Outputs written to `runs/` directory
