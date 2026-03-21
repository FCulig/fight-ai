# Fight AI — Python Video Processing Library

## What it does
Accepts MMA fight videos, runs ML inference to detect fight events (grappling, state transitions), and writes results to PostgreSQL. Data is later served to the backend for video playback.

## Project Structure
```
ai/
├── video_processing/         # Step 1-5: YOLO detection, ReID, pose tracking
│   ├── video_processing.py   # Entry: runs custom YOLO, saves detection JSON
│   ├── fighter_reidentification/
│   │   └── fighter_reidentification.py  # torchreid ReID, assigns class_id 0/1
│   └── pose_tracking/
│       └── pose_tracking.py  # YOLOv8x-pose on fighter crops → keypoints
├── fight_processing/         # Step 6-8: feature extraction, grappling detection, DB writes
│   ├── fight_processing.py   # Main loop: state machine, DB event writes
│   └── fight_processing_util.py  # Torso rect, distance calc, state determination
├── models/
│   ├── FightState.py         # Enum: STRIKING=1, GRAPPLING=2
│   ├── IdentityMemory.py     # EMA cosine-similarity ReID tracker (max 2 fighters)
│   └── constants.py          # LABEL_ID, MIN_GRAPPLING_THRESHOLD, DISTANCE_GRAPPLING_THRESHOLD
└── databse.py                # SQLAlchemy SessionLocal
```

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
