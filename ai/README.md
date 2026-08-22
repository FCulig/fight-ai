# Fight AI — Video Processing Library

A Python library that processes MMA fight videos to detect fight events (grappling states, takedown attempts) and store them in PostgreSQL for backend consumption.

## How It Works

Raw video → YOLO fighter detection → Geometry tracking → Pose estimation → Corner assignment → Grappling detection → PostgreSQL

### Pipeline Steps

1. **Fighter Detection** (`video_processing/video_processing.py`)
   Custom-trained YOLO model detects fighters and referee in each frame.

2. **Fighter Tracking** (`video_processing/fighter_tracking/`)
   A constrained 2-slot online tracker (`models/FighterTracker.py`) assigns each fighter a stable *provisional* track ID (0 or 1) across frames. Matching is geometry-only — a cost matrix blending IoU against the slot's velocity-predicted box with normalised centroid distance, resolved by Hungarian assignment. No video frames are read and no appearance embeddings are computed. Unmatched slots coast on their last velocity and are pruned after `TRACK_MAX_MISSING_SECS`; while the two boxes overlap heavily (a clinch) velocity is frozen to prevent identity swaps. The original YOLO class is preserved as `model_class_id` for later fallback.

   These IDs are provisional: track 0/1 is *not* red/blue. Corner labelling happens in step 4.

3. **Pose Estimation** (`video_processing/pose_tracking/`)
   Each fighter's bounding box is cropped and run through `yolo26x-pose.pt`. Keypoints are shifted back to full-frame coordinates.

4. **Corner Assignment** (`video_processing/corner_assignment/`)
   Rewrites provisional track IDs into final red/blue corner labels using a glove-tape HSV vote, falling back to a majority model-class vote when the two corners' colours are too similar to separate.

5. **Fight State Detection** (`fight_processing/`)
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

Then process each detected round through the Tracking → Pose → Corner assignment → Fight State pipeline.

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
│   ├── fighter_tracking/          # Geometry-only 2-slot tracker
│   ├── corner_assignment/         # Provisional track IDs → red/blue corners
│   └── pose_tracking/
├── fight_processing/
│   ├── fight_processing.py
│   └── fight_processing_util.py
├── models/
│   ├── FightState.py              # Enum: STRIKING=1, GRAPPLING=2
│   ├── FighterTracker.py          # IoU + centroid Hungarian 2-slot tracker
│   └── constants.py               # All thresholds and label IDs
└── database.py                    # SQLAlchemy SessionLocal
```

## Glossary

| Term | Definition |
|---|---|
| **ROI** (Region of Interest) | A rectangular crop of the video frame. In this project it refers to the bounding box around the scoreboard overlay — the portion of the broadcast frame containing the round number and countdown timer (e.g. bottom-left corner at x=1620, y=980, w=280, h=60). The pipeline detects this rectangle once during calibration and reuses it for all subsequent OCR samples, avoiding the cost of processing the full frame every time. |
| **Scoreboard overlay** | The persistent on-screen graphic broadcast over the fight footage showing the current round number and countdown timer (e.g. `R1 4:32`). Present in all major MMA TV broadcasts regardless of organisation. |
| **Segmentation** | The process of splitting a full fight video (including walkouts, corner breaks, and replays) into individual round clips by detecting when each round starts and ends. |
| **OCR** (Optical Character Recognition) | Extracting text from an image. Used here to read the round number and timer directly from the scoreboard overlay. |

## Setup

### Prerequisites
- Python 3.10+
- PostgreSQL running locally

### Install dependencies

Choose the requirements file that matches your platform:

```bash
python -m venv .venv

# macOS (Apple Silicon uses MPS, Intel uses CPU)
source .venv/bin/activate
pip install -r requirements-cpu.txt

# Windows without NVIDIA GPU
.venv\Scripts\activate
pip install -r requirements-cpu.txt

# Linux / Windows with NVIDIA GPU (CUDA 12.6)
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements-cuda.txt
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

`run_pipeline()` chains the stages in-memory — each hands the next a Python dict, and no intermediate stage artifact is written to `runs/` (only `manifest.json` and debug output land there). The stages therefore take dicts, not paths, and are not usefully callable as standalone shell one-liners. Drive the pipeline through the CLI instead:

```bash
python main.py fight.mp4 --segment
```

To skip early stages, hand the pipeline a previously captured artifact and it will load that dict from JSON rather than recomputing it:

```bash
# Skip YOLO
python main.py fight.mp4 --detection-file runs/detection_results.json

# Skip YOLO + tracking
python main.py fight.mp4 --track-file runs/track_results.json

# Skip YOLO + tracking + pose
python main.py fight.mp4 --pose-results runs/pose_results.json
```

> These are load-only dev overrides: the pipeline reads these files but never writes them, so the paths are whatever you saved earlier. `--reid-file` is a deprecated alias for `--track-file`.

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
| `TRACK_IOU_WEIGHT` | 0.6 | Share of the tracking cost matrix from the IoU term |
| `TRACK_DISTANCE_WEIGHT` | 0.4 | Share of the tracking cost matrix from the centroid-distance term |
| `TRACK_MAX_MISSING_SECS` | 0.6s | How long a slot coasts unmatched before it is pruned |
| `CLINCH_IOU_THRESHOLD` | 0.3 | Inter-fighter IoU above which velocity is frozen to avoid ID swaps |

## Fight State Logic

- Starts in `STRIKING` state
- Transitions to `GRAPPLING` when torso distance < threshold for N consecutive frames
- If a fighter is not visible (missing keypoints), the current state is held — no reset
- State changes are written to the DB with the frame number

## TODO

- [ ] **Automate model weight distribution** — model weights (`weights.pt`, `yolo26x-pose.pt`) are currently uploaded manually on each deployment. Implement a download script (e.g. `download_models.py`) that fetches weights from cloud storage (S3, HuggingFace Hub, etc.) so setup can be fully automated. Add `*.pt` to `.gitignore` once this is in place.

- [ ] **Allow for filtering of fight events** - implement event category or something like that in order to allow for filter events on the event feed. This could also be used for easier statistics.