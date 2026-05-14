"""
Pipeline orchestration for the fight-ai processing steps.

main.py is a pure argument parser and dispatcher — all business logic
(step ordering, fallback handling, timing, manifest writing) lives here.

Two entry points:
  run_segmentation_pipeline — full-fight video → detected rounds
  run_full_pipeline         — stepwise processing for a trimmed round clip
"""

import time
from typing import Optional

from debug import DebugContext
from manifest import build_manifest
from video_processing.video_processing import process_video
from video_processing.fight_segmentation import segment_fights


# ---------------------------------------------------------------------------
# Segmentation pipeline
# ---------------------------------------------------------------------------

def run_segmentation_pipeline(
    video_file: str,
    *,
    detection_file: Optional[str] = None,
    scoreboard_samples: Optional[str] = None,
    scoreboard_roi: Optional[str] = None,
    skip_scoreboard: bool = False,
    recalibrate: bool = False,
    verify_scoreboard: bool = False,
    debug_level: str = "verbose",
) -> dict:
    """
    Segment a full fight video into rounds.

    Steps
    -----
    1. YOLO detection  (skipped when detection_file is provided)
    2. Scoreboard overlay calibration + OCR  (skipped when skip_scoreboard=True)
    3. Fight segmentation fusing detection + OCR signals
    4. Manifest write

    Returns the segment_fights() result dict:
        {"rounds": [...], "quality": {...}}
    """
    verbose    = debug_level != "none"
    debug_root = "runs/scoreboard_overlay"
    ctx        = DebugContext(debug_root, verbose=verbose)
    timings: dict[str, float] = {}
    outputs: dict[str, str]   = {}

    # ------------------------------------------------------------------
    # Step 1 — YOLO detection
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    if detection_file:
        print(f"Reusing detection results: {detection_file}")
    else:
        print(f"Running YOLO detection on: {video_file}")
        detection_file = process_video(video_file)
    timings["detection"] = time.perf_counter() - t0
    outputs["detection_results"] = detection_file

    # ------------------------------------------------------------------
    # Step 2 — Scoreboard overlay OCR
    # ------------------------------------------------------------------
    scoreboard_samples_file: Optional[str] = None

    if not skip_scoreboard:
        from video_processing.scoreboard_overlay import (
            calibrate_scoreboard_overlay,
            extract_scoreboard_samples,
            build_verification_video,
            load_samples,
            load_roi,
            parse_roi_override,
        )

        override_roi = None
        if scoreboard_roi:
            override_roi = parse_roi_override(scoreboard_roi)

        t0  = time.perf_counter()
        roi = calibrate_scoreboard_overlay(
            video_file,
            override_roi=override_roi,
            recalibrate=recalibrate,
            debug_ctx=ctx,
        )
        timings["scoreboard_calibration"] = time.perf_counter() - t0
        outputs["roi"] = f"{debug_root}/roi.json"

        if roi is None:
            print(
                "WARNING: Scoreboard overlay not detected — "
                "falling back to detection-only segmentation.\n"
                f"  Check debug images in {debug_root}/calibration_debug/"
            )
        else:
            if scoreboard_samples:
                print(f"Reusing scoreboard samples: {scoreboard_samples}")
                scoreboard_samples_file = scoreboard_samples
                timings["scoreboard_ocr"] = 0.0
            else:
                t0      = time.perf_counter()
                samples = extract_scoreboard_samples(video_file, roi, debug_ctx=ctx)
                timings["scoreboard_ocr"]     = time.perf_counter() - t0
                scoreboard_samples_file       = f"{debug_root}/samples.json"
                outputs["scoreboard_samples"] = scoreboard_samples_file
                print(f"OCR: {len(samples)} samples extracted")

            if verify_scoreboard and scoreboard_samples_file:
                _samples = load_samples(scoreboard_samples_file)
                _roi     = load_roi(f"{debug_root}/roi.json", video_file)
                if _samples and _roi:
                    t0      = time.perf_counter()
                    out_vid = build_verification_video(
                        video_file, _samples, _roi,
                        output_path=f"{debug_root}/verification.mp4",
                    )
                    timings["verification_video"] = time.perf_counter() - t0
                    outputs["verification_video"] = out_vid

    # ------------------------------------------------------------------
    # Step 3 — Segmentation
    # ------------------------------------------------------------------
    t0     = time.perf_counter()
    result = segment_fights(
        detection_file,
        scoreboard_samples_file=scoreboard_samples_file,
        debug_ctx=DebugContext("runs", verbose=verbose),
    )
    timings["segmentation"]       = time.perf_counter() - t0
    outputs["segmentation_debug"] = "runs/segmentation_debug/"

    print("\nSegmentation result:")
    print(f"  Rounds : {result['rounds']}")
    print(f"  Quality: {result['quality']}")

    # ------------------------------------------------------------------
    # Step 4 — Manifest
    # ------------------------------------------------------------------
    build_manifest(
        video_path   = video_file,
        cli_args     = {"mode": "segment", "detection_file": detection_file,
                        "skip_scoreboard": skip_scoreboard},
        step_timings = timings,
        output_paths = outputs,
        summary      = {
            "round_count": len(result["rounds"]),
            "rounds":      result["rounds"],
            "quality":     result["quality"],
        },
    )

    return result


# ---------------------------------------------------------------------------
# Full pipeline (stepwise, for trimmed round clips)
# ---------------------------------------------------------------------------

def run_full_pipeline(video_file: str, *, no_db: bool = False) -> None:
    """
    Run the full processing pipeline on a trimmed round clip.

    Steps (uncomment as each step is wired up):
      1. process_video  — YOLO detection
      2. track_fighters — ReID
      3. track_poses    — pose estimation
      4. process_fight  — state machine + DB writes
    """
    from video_processing.pose_tracking.pose_verification import verify_pose_tracking
    from fight_processing.fight_processing import process_fight

    process_video(video_file)

    # track_fighters("runs/detection_results.json")
    # verify_reidentification("runs/output_reidentification.json")
    # track_poses("runs/output_reidentification.json")

    verify_pose_tracking("runs/pose_results.json")

    # process_fight("runs/pose_results.json", save_to_db=not no_db)
