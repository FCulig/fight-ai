import argparse
import time

from video_processing.video_processing import process_video
from video_processing.fighter_reidentification.fighter_reidentification import track_fighters
from video_processing.fighter_reidentification.reidentification_verification import verify_reidentification
from video_processing.pose_tracking.pose_tracking import track_poses
from video_processing.pose_tracking.pose_verification import verify_pose_tracking
from video_processing.fight_segmentation import segment_fights
from debug import DebugContext
from manifest import build_manifest

parser = argparse.ArgumentParser(description="Process fight detection data.")
parser.add_argument("video_input",         type=str,
                    help="Path to the .mp4 fight video")
parser.add_argument("--detection-file",    type=str,
                    help="Reuse existing detection_results.json (skips YOLO)")
parser.add_argument("--no-db",             action="store_true",
                    help="Skip database writes")
parser.add_argument("--segment",           action="store_true",
                    help="Run fight segmentation instead of full processing")

# Scoreboard overlay flags
parser.add_argument("--scoreboard-samples", type=str, default=None,
                    help="Reuse existing scoreboard samples JSON (skips OCR)")
parser.add_argument("--scoreboard-roi",     type=str, default=None,
                    help="Manual ROI override: 'x,y,w,h' — skips auto-detection")
parser.add_argument("--skip-scoreboard",    action="store_true",
                    help="Disable scoreboard OCR; use detection signals only")
parser.add_argument("--recalibrate",        action="store_true",
                    help="Ignore cached ROI and re-run calibration")
parser.add_argument("--verify-scoreboard",  action="store_true",
                    help="Render scoreboard verification video after OCR extraction")

# Debug control
parser.add_argument("--debug-level",        choices=["none", "normal", "verbose"],
                    default="verbose",
                    help="Debug output verbosity (default: verbose)")

args = parser.parse_args()

video_file = args.video_input
verbose    = args.debug_level != "none"
timings: dict[str, float] = {}
outputs: dict[str, str]   = {}

# ---------------------------------------------------------------------------
# Segmentation path
# ---------------------------------------------------------------------------
if args.segment:
    debug_root = "runs/scoreboard_overlay"
    ctx = DebugContext(debug_root, verbose=verbose)

    # Step 1 — YOLO detection
    t0 = time.perf_counter()
    if args.detection_file:
        print("Using existing detection results:", args.detection_file)
        detection_file = args.detection_file
    else:
        print("Running YOLO detection:", video_file)
        detection_file = process_video(video_file)
    timings["detection"] = time.perf_counter() - t0
    outputs["detection_results"] = detection_file

    # Step 2 — Scoreboard overlay OCR
    scoreboard_samples_file: str | None = None

    if not args.skip_scoreboard:
        from video_processing.scoreboard_overlay import (
            calibrate_scoreboard_overlay,
            extract_scoreboard_samples,
            build_verification_video,
        )

        # Parse manual ROI if provided
        override_roi = None
        if args.scoreboard_roi:
            try:
                override_roi = tuple(int(v) for v in args.scoreboard_roi.split(","))
                if len(override_roi) != 4:
                    raise ValueError
            except ValueError:
                print("ERROR: --scoreboard-roi must be 'x,y,w,h'  (four integers)")
                raise SystemExit(1)

        # Calibrate
        if args.recalibrate:
            import os
            roi_cache = f"{debug_root}/roi.json"
            if os.path.exists(roi_cache):
                os.remove(roi_cache)
                print("Cleared cached ROI — recalibrating")

        t0  = time.perf_counter()
        roi = calibrate_scoreboard_overlay(
            video_file,
            override_roi=override_roi,
            debug_ctx=ctx,
        )
        timings["scoreboard_calibration"] = time.perf_counter() - t0
        outputs["roi"] = f"{debug_root}/roi.json"

        if roi is None:
            print(
                "WARNING: Scoreboard overlay not detected. "
                "Falling back to detection-only segmentation.\n"
                f"  Check debug images in {debug_root}/calibration_debug/\n"
                "  Or supply --scoreboard-roi x,y,w,h to override."
            )
        else:
            # Reuse existing samples or run OCR
            if args.scoreboard_samples:
                print("Using existing scoreboard samples:", args.scoreboard_samples)
                scoreboard_samples_file = args.scoreboard_samples
                timings["scoreboard_ocr"] = 0.0
            else:
                t0 = time.perf_counter()
                samples = extract_scoreboard_samples(
                    video_file, roi, debug_ctx=ctx
                )
                timings["scoreboard_ocr"] = time.perf_counter() - t0
                scoreboard_samples_file   = f"{debug_root}/samples.json"
                outputs["scoreboard_samples"] = scoreboard_samples_file
                print(f"OCR: {len(samples)} samples extracted")

            # Optional verification video
            if args.verify_scoreboard and scoreboard_samples_file:
                from video_processing.scoreboard_overlay.extraction import load_samples
                from video_processing.scoreboard_overlay.calibration import load_roi as _load_roi
                _samples = load_samples(scoreboard_samples_file)
                _roi     = _load_roi(f"{debug_root}/roi.json", video_file)
                if _samples and _roi:
                    t0 = time.perf_counter()
                    out_vid = build_verification_video(
                        video_file, _samples, _roi,
                        output_path=f"{debug_root}/verification.mp4",
                    )
                    timings["verification_video"] = time.perf_counter() - t0
                    outputs["verification_video"] = out_vid

    # Step 3 — Segmentation
    t0     = time.perf_counter()
    result = segment_fights(
        detection_file,
        scoreboard_samples_file=scoreboard_samples_file,
        debug_ctx=DebugContext("runs", verbose=verbose),
    )
    timings["segmentation"] = time.perf_counter() - t0
    outputs["segmentation_debug"] = "runs/segmentation_debug/"

    print("\nSegmentation result:")
    print(f"  Rounds : {result['rounds']}")
    print(f"  Quality: {result['quality']}")

    build_manifest(
        video_path   = video_file,
        cli_args     = vars(args),
        step_timings = timings,
        output_paths = outputs,
        summary      = {
            "round_count": len(result["rounds"]),
            "rounds":      result["rounds"],
            "quality":     result["quality"],
        },
    )

# ---------------------------------------------------------------------------
# Full pipeline path (unchanged)
# ---------------------------------------------------------------------------
else:
    from fight_processing.fight_processing import process_fight
    results = process_video(video_file)

    #track_fighters("runs/detection_results.json")
    #verify_reidentification("runs/output_reidentification.json")
    #track_poses("runs/output_reidentification.json")

    verify_pose_tracking("runs/pose_results.json")

    #process_fight("runs/pose_results.json", save_to_db=not args.no_db)
