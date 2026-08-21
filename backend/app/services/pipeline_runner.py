import json
import os
import subprocess
from pathlib import Path

import psutil

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

AI_DIR = os.getenv("AI_DIR", str(_PROJECT_ROOT / "ai"))
AI_PYTHON = os.getenv("AI_PYTHON", str(_PROJECT_ROOT / ".venv" / "bin" / "python"))
_TERMINATE_TIMEOUT_S = 10


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


def run_validation_async(video_path: str, fight_id: int, skip_events: bool = False) -> int:
    """Spawn a full-decode validation pass for a freshly-uploaded video
    (non-blocking). Returns the child PID.

    Unlike `run_pipeline_async`, this process writes its own state
    transitions to the DB (VALIDATING → QUEUED/INVALID) via `set_fight_state`
    and, on a clean result, spawns the real pipeline itself and hands off
    `pid` to it — see `eval.cli video --fight-id` / `_validate_and_dispatch`.
    Full decode costs roughly a tenth of real time, so this runs in the
    background rather than blocking the upload response.
    """
    log_dir = Path(AI_DIR) / "runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "upload_pipeline.log", "ab")
    cmd = [AI_PYTHON, "-m", "eval.cli", "video", video_path, "--fight-id", str(fight_id)]
    if skip_events:
        cmd.append("--skip-events")
    proc = subprocess.Popen(
        cmd,
        cwd=AI_DIR,
        stdout=log,
        stderr=log,
    )
    return proc.pid


def run_pipeline_async(video_path: str, skip_events: bool = False) -> int:
    """Spawn the AI pipeline single-file mode (non-blocking). Returns the child PID.

    video_path is relative to AI_DIR (e.g. 'fight_videos/clip.mp4').
    skip_events=True runs detection/tracking/pose/corners/scoreboard/segmentation
    as normal but skips strike/fight-state event detection, for manually-labeled
    fights (see ai/main.py --skip-events).
    """
    log_dir = Path(AI_DIR) / "runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "upload_pipeline.log", "ab")
    cmd = [AI_PYTHON, "main.py", video_path]
    if skip_events:
        cmd.append("--skip-events")
    proc = subprocess.Popen(
        cmd,
        cwd=AI_DIR,
        stdout=log,
        stderr=log,
    )
    return proc.pid


# Command-line markers for the jobs we spawn into the AI venv. A process is only
# ever signalled when its cwd is AI_DIR *and* its command line names one of
# these, so a recycled PID can never take a signal meant for one of our jobs.
# Anything new spawned by this module must add its marker here — a job missing
# from this tuple is silently unkillable, since terminate_pipeline no-ops on it.
_AI_ENTRYPOINTS = (
    "main.py",    # run_pipeline_async — the processing pipeline
    "eval.cli",   # validation pass — `python -m eval.cli video <path>`
)


def _is_our_pipeline_process(proc: psutil.Process) -> bool:
    """Sanity-check that `pid` is still a job we spawned, not an unrelated
    process that reused the same PID after the original one exited."""
    try:
        cwd = proc.cwd()
        cmdline = proc.cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    if Path(cwd).resolve() != Path(AI_DIR).resolve():
        return False
    return any(Path(part).name in _AI_ENTRYPOINTS for part in cmdline)


def is_pipeline_process_alive(pid: int) -> bool:
    """Check whether `pid` is still our running pipeline process."""
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return False
    return proc.is_running() and _is_our_pipeline_process(proc)


def terminate_pipeline(pid: int) -> None:
    """Terminate the pipeline process for `pid`, if it's still ours and running.

    Blocks (up to _TERMINATE_TIMEOUT_S + a grace period) until the process has
    actually exited, escalating from SIGTERM to SIGKILL if needed.
    """
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    if not _is_our_pipeline_process(proc):
        return
    proc.terminate()
    try:
        proc.wait(timeout=_TERMINATE_TIMEOUT_S)
        return
    except psutil.TimeoutExpired:
        pass
    proc.kill()
    try:
        proc.wait(timeout=5)
    except psutil.TimeoutExpired:
        pass
