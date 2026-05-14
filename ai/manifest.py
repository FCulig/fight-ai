"""
Writes runs/manifest.json at the end of each pipeline run.

Captures video metadata, CLI args, per-step timings, output paths, and
summary metrics so runs can be compared reliably.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2


def build_manifest(
    video_path: str,
    cli_args: dict,
    step_timings: dict[str, float],
    output_paths: dict[str, str],
    summary: dict,
    output_file: str = "runs/manifest.json",
) -> dict:
    """
    Build and write a manifest for the current run.

    Args:
        video_path:    Path to source video.
        cli_args:      Parsed CLI arguments as a plain dict.
        step_timings:  {'step_name': elapsed_seconds} per pipeline step.
        output_paths:  {'artifact_name': 'runs/...'} for every output file.
        summary:       High-level results (round count, quality flag, etc.).
        output_file:   Where to write the manifest JSON.

    Returns:
        The manifest dict.
    """
    video_meta: dict = {}
    try:
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            fc  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_meta = {
                "fps":          fps,
                "width":        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height":       int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "frame_count":  fc,
                "duration_sec": fc / fps if fps > 0 else None,
            }
        cap.release()
    except Exception as exc:
        video_meta = {"error": str(exc)}

    manifest = {
        "run_at":       datetime.now().isoformat(),
        "python":       sys.version,
        "video":        {"path": str(video_path), **video_meta},
        "args":         cli_args,
        "timings_sec":  step_timings,
        "outputs":      output_paths,
        "summary":      summary,
    }

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest written → {output_file}")
    return manifest
