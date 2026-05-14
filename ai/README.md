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

## Full-Fight Upload Processing

For end-user uploads of complete fight videos (including walkouts and multiple rounds), the system automatically detects fight start/end and splits into rounds using two fused signals:

1. **Scoreboard overlay OCR** — reads the round number and countdown timer directly from the broadcast graphic. Primary signal; works for any TV broadcast regardless of organisation.
2. **YOLO fighter presence + engagement** — fallback when the overlay is unavailable or unreadable.

### Pipeline Steps

1. **YOLO detection** — detects fighters and referee in every frame.
2. **Scoreboard calibration** — auto-detects the overlay region by OCR-scanning the bottom 38 % of sampled frames and finding where the timer (`M:SS`) appears consistently.
3. **Scoreboard OCR extraction** — samples at 2 fps, parses round number and timer, smooths results.
4. **Fight segmentation** — fuses OCR + detection signals through hysteresis state machines; snaps round boundaries to OCR-detected round transitions.

Then process each detected round through the ReID → Pose → Fight State pipeline.

### Usage

```bash
# Standard run — full auto, no arguments needed
python main.py fight.mp4 --segment
```

#### All flags

| Flag | Default | Description |
|---|---|---|
| `--segment` | off | Run fight segmentation instead of full round processing |
| `--detection-file PATH` | — | Reuse an existing `detection_results.json` (skips YOLO re-run) |
| `--scoreboard-samples PATH` | — | Reuse existing OCR samples JSON (skips OCR re-run) |
| `--scoreboard-roi x,y,w,h` | — | Manually specify the scoreboard overlay region (skips auto-detect) |
| `--skip-scoreboard` | off | Disable OCR entirely; use detection signals only |
| `--recalibrate` | off | Delete the cached ROI and re-run overlay auto-detection |
| `--verify-scoreboard` | off | Render a short annotated verification video to inspect OCR quality |
| `--no-db` | off | Skip PostgreSQL writes (full pipeline mode only) |
| `--debug-level` | `verbose` | `none` / `normal` / `verbose` — controls debug image and JSON output |

#### Debug outputs

All debug artefacts are written under `runs/` and `runs/scoreboard_overlay/`:

| File | What it shows |
|---|---|
| `runs/scoreboard_overlay/calibration_debug/strip_frame_*.jpg` | Each sampled strip with OCR detections drawn — first place to check if calibration fails |
| `runs/scoreboard_overlay/calibration_debug/selected_roi.jpg` | Reference frame with the winning ROI highlighted |
| `runs/scoreboard_overlay/calibration_debug/calibration_log.txt` | Per-box match log from calibration |
| `runs/scoreboard_overlay/samples.json` | Smoothed per-sample round + timer readings |
| `runs/scoreboard_overlay/timer_plot.png` | Round/timer series over time — visual sanity check |
| `runs/scoreboard_overlay/verification.mp4` | 1 fps annotated video showing OCR readings per frame (`--verify-scoreboard`) |
| `runs/segmentation_debug/timeline.png` | Fused in-round probability + detected round bands |
| `runs/segmentation_debug/signal_series.csv` | Per-frame OCR and detection signals |
| `runs/manifest.json` | Full run record: video metadata, step timings, output paths, quality summary |

#### Typical developer iteration flow

```bash
# First run — auto-detects overlay, runs full OCR, segments
python main.py fight.mp4 --segment --verify-scoreboard

# Inspect runs/scoreboard_overlay/calibration_debug/strip_frame_*.jpg
# and runs/scoreboard_overlay/timer_plot.png

# Re-run segmentation reusing cached detection + OCR (fast)
python main.py fight.mp4 --segment \
  --detection-file runs/detection_results.json \
  --scoreboard-samples runs/scoreboard_overlay/samples.json

# Force fresh overlay detection (e.g. after tuning constants)
python main.py fight.mp4 --segment --recalibrate
```

## Project Structure

```
ai/
├── main.py                        # Argument parser + dispatcher (no business logic)
├── pipeline.py                    # Orchestration for both pipeline modes
├── debug.py                       # DebugContext — centralised debug output
├── manifest.py                    # Writes runs/manifest.json per run
├── video_processing/
│   ├── video_processing.py        # YOLO detection → runs/detection_results.json
│   ├── fight_segmentation.py      # Fuses OCR + detection signals → round list
│   ├── scoreboard_overlay/        # Scoreboard OCR package
│   │   ├── calibration.py         # Auto-detects overlay ROI via bottom-strip OCR
│   │   ├── extraction.py          # Per-frame OCR sampling + smoothing
│   │   ├── parsers.py             # Org-agnostic round/timer regexes
│   │   ├── debug.py               # Visualisation helpers
│   │   └── scoreboard_verification.py
│   ├── fighter_reidentification/
│   └── pose_tracking/
├── fight_processing/
│   ├── fight_processing.py
│   └── fight_processing_util.py
├── models/
│   ├── FightState.py              # Enum: STRIKING=1, GRAPPLING=2
│   ├── IdentityMemory.py          # EMA cosine-similarity ReID tracker
│   └── constants.py               # All thresholds and label IDs
└── database.py                    # SQLAlchemy SessionLocal
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

## TODO

- [ ] **Automate model weight distribution** — model weights (`weights.pt`, `yolo26x-pose.pt`) are currently uploaded manually on each deployment. Implement a download script (e.g. `download_models.py`) that fetches weights from cloud storage (S3, HuggingFace Hub, etc.) so setup can be fully automated. Add `*.pt` to `.gitignore` once this is in place.

- [ ] **Allow for filtering of fight events** - implement event category or something like that in order to allow for filter events on the event feed. This could also be used for easier statistics.