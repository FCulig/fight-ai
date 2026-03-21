# Fight AI — Video Processing Library

A Python library that processes MMA fight videos to detect fight events (grappling states, takedown attempts) and store them in PostgreSQL for backend consumption.

## How It Works

Raw video → YOLO fighter detection → ReID tracking → Pose estimation → Grappling detection → PostgreSQL

### Pipeline Steps

1. **Fighter Detection** (`video_processing/video_processing.py`)
   Custom-trained YOLO model detects fighters and referee in each frame.

2. **Re-Identification** (`video_processing/fighter_reidentification/`)
   torchreid (`osnet_x1_0`) assigns stable identities (red=0, blue=1) to each fighter across frames using cosine similarity + EMA embeddings.

3. **Pose Estimation** (`video_processing/pose_tracking/`)
   Each fighter's bounding box is cropped and run through `yolo26x-pose.pt`. Keypoints are shifted back to full-frame coordinates.

4. **Fight State Detection** (`fight_processing/`)
   Torso rectangles (built from shoulder/hip keypoints) are compared per frame. When fighters' torsos are within a distance threshold for 3+ consecutive frames, the state transitions to `GRAPPLING`. State changes are written to PostgreSQL.

## Project Structure

```
ai/
├── video_processing/
│   ├── video_processing.py
│   ├── fighter_reidentification/
│   └── pose_tracking/
├── fight_processing/
│   ├── fight_processing.py
│   └── fight_processing_util.py
├── models/
│   ├── FightState.py        # Enum: STRIKING, GRAPPLING
│   ├── IdentityMemory.py    # ReID tracker
│   └── constants.py         # Thresholds and label IDs
└── databse.py               # SQLAlchemy session
```

## Setup

### Prerequisites
- Python 3.10+
- PostgreSQL running locally

### Install dependencies

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows
pip install -r requirements.txt
```

### Environment variables

Copy `.env.example` to `.env` and fill in your database URL:

```
DATABASE_URL=postgresql://postgres:secret@localhost:5432/postgres
```

### Model weights

Place the following model files in the project:
- `video_processing/weights.pt` — custom YOLO fighter detection model
- `yolo26x-pose.pt` — YOLOv8x pose estimation model (in working directory)

## Running

> Note: the pipeline currently runs in steps. Each step reads from and writes to `runs/`.

```bash
# Step 1: Detect fighters
python -c "from video_processing.video_processing import process_video; process_video('your_video.mp4')"

# Step 2: ReID tracking (requires frames extracted to frames/frame_N.jpg)
python -c "from video_processing.fighter_reidentification.fighter_reidentification import track_fighters; track_fighters('runs/detection_results.json')"

# Step 3: Pose estimation
python -c "from video_processing.pose_tracking.pose_tracking import track_poses; track_poses('runs/output_reidentification.json')"

# Step 4: Fight state processing → DB writes
python -c "from fight_processing.fight_processing import process_fight; process_fight('runs/pose_results.json')"
```

## Database Schema

```sql
CREATE TABLE fight_events (
    id SERIAL PRIMARY KEY,
    frame INTEGER,
    description TEXT
);
```

## Key Parameters

| Constant | Value | Description |
|---|---|---|
| `DISTANCE_GRAPPLING_THRESHOLD` | 20px | Torso-rect distance below which fighters are considered grappling |
| `MIN_GRAPPLING_THRESHOLD` | 3 frames | Consecutive frames required to trigger state transition |
| ReID sim threshold | 0.75 | Cosine similarity cutoff for matching fighter identity |
| ReID EMA | 0.9 | Embedding update rate |

## Fight State Logic

- Starts in `STRIKING` state
- Transitions to `GRAPPLING` when torso distance < threshold for N consecutive frames
- If a fighter is not visible (missing keypoints), the current state is held — no reset
- State changes are written to the DB with the frame number
