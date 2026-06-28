import json
import os
import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

AI_DIR = os.getenv("AI_DIR", str(_PROJECT_ROOT / "ai"))
AI_PYTHON = os.getenv("AI_PYTHON", str(_PROJECT_ROOT / ".venv" / "bin" / "python"))


def extract_video_meta(video_path: str) -> tuple[int, int, int]:
    """Extract (fps, width, height) from a video file using the AI venv's cv2."""
    script = (
        "import cv2, json, sys; "
        "cap = cv2.VideoCapture(sys.argv[1]); "
        "print(json.dumps({'fps': round(cap.get(cv2.CAP_PROP_FPS)) or 30, "
        "'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "
        "'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))})); "
        "cap.release()"
    )
    abs_path = str((Path(AI_DIR) / video_path).resolve())
    result = subprocess.run(
        [AI_PYTHON, "-c", script, abs_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to extract video metadata: {result.stderr.strip()}")
    meta = json.loads(result.stdout)
    return meta["fps"], meta["width"], meta["height"]


def run_pipeline_async(video_path: str) -> None:
    """Spawn the AI pipeline single-file mode (non-blocking).

    video_path is relative to AI_DIR (e.g. 'fight_videos/clip.mp4').
    """
    log_dir = Path(AI_DIR) / "runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "upload_pipeline.log", "ab")
    subprocess.Popen(
        [AI_PYTHON, "main.py", video_path],
        cwd=AI_DIR,
        stdout=log,
        stderr=log,
    )
