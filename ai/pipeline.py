"""
Pipeline orchestration for the fight-ai processing steps.

main.py is a pure argument parser and dispatcher — all business logic
lives here.

Philosophy
----------
- If just a video is supplied, every step runs in order.
- Supplying a file for a later step skips that step and all earlier steps
  on the same track (see skip matrix below).
- Debug flags (--verify-pose, --verify-scoreboard) run AFTER the main
  pipeline and cause process_fight to be skipped.

Pipeline order
--------------
Track A (pose):     1. YOLO detection
                    2. ReID
                    3. Pose tracking
Track B (segments): 1. YOLO detection  (shared with A)
                    4. Scoreboard OCR
                    5. Fight segmentation
Common finish:      6. process_fight   (skipped when any debug flag present)
Debug outputs:      7. Pose debug video        (--verify-pose only)
                    8. Scoreboard debug video  (--verify-scoreboard only)

Skip matrix
-----------
--detection-file   skips step 1
--reid-file        skips steps 1–2
--pose-results     skips steps 1–3
--scoreboard-samples  skips step 4
--manifest         skips steps 4–5
--rounds "s,e …"   skips steps 4–5 (explicit round boundaries)
any debug flag     skips step 6
"""

import json
import time
from typing import Optional

from debug import DebugContext
from manifest import build_manifest
from video_processing.video_processing import process_video
from video_processing.fight_segmentation import segment_fights


# ---------------------------------------------------------------------------
# Startup plan printer
# ---------------------------------------------------------------------------

def _fps_from_video(video_path: str) -> float:
    """Read fps directly from a video file."""
    import cv2
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps if fps > 0 else 50.0


def _print_plan(title: str, rows: list[tuple[str, str]]) -> None:
    """Print a bordered summary block before a pipeline run starts."""
    label_width   = max(len(label) for label, _ in rows)
    content_width = max(
        len(title),
        max(label_width + 3 + len(value) for label, value in rows),
    )
    border = "═" * (content_width + 4)
    print(f"\n╔{border}╗")
    print(f"║  {title:<{content_width}}  ║")
    print(f"╠{border}╣")
    for label, value in rows:
        line = f"{label:<{label_width}} : {value}"
        print(f"║  {line:<{content_width}}  ║")
    print(f"╚{border}╝\n")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_rounds_arg(rounds_str: str) -> list[tuple[int, int]]:
    """Parse 'start1,end1 start2,end2 …' into a list of (start, end) tuples."""
    rounds = []
    for pair in rounds_str.strip().split():
        s, e = pair.split(",")
        rounds.append((int(s), int(e)))
    return rounds


def _load_rounds_from_manifest(path: str) -> list[tuple[int, int]]:
    data = json.load(open(path))
    return [tuple(r) for r in data["summary"]["rounds"]]


def _skip_label(supplied: Optional[str], reason: str) -> str:
    return f"SKIP — {supplied}" if supplied else f"SKIP — {reason}"


# ---------------------------------------------------------------------------
# Unified pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    video_file: str,
    *,
    # ---- File overrides (supply to skip that step + all earlier steps) ----
    detection_file: Optional[str]     = None,
    reid_file: Optional[str]          = None,
    pose_results: Optional[str]       = None,
    scoreboard_samples: Optional[str] = None,
    manifest_file: Optional[str]      = None,
    # ---- Scoreboard options ----
    scoreboard_roi: Optional[str]     = None,
    skip_scoreboard: bool             = False,
    recalibrate: bool                 = False,
    # ---- Explicit rounds (skips OCR + segmentation) ----
    rounds_arg: Optional[str]         = None,
    # ---- Debug flags (also skip process_fight) ----
    # verify_pose: None = skip, "all" = full video, "60" = first 60s, "30-90" = range
    verify_pose: Optional[str]        = None,
    verify_scoreboard: bool           = False,
    # ---- General ----
    no_db: bool                       = False,
    debug_level: str                  = "verbose",
) -> dict:
    """
    Run the full fight-ai pipeline with smart step skipping.

    Returns {"rounds": [...], "quality": {...}}.
    """
    verbose    = debug_level != "none"
    debug_root = "runs/scoreboard_overlay"

    # ----------------------------------------------------------------
    # Determine which steps to run
    # ----------------------------------------------------------------

    # Track A — pose
    run_detection_for_pose = reid_file is None and pose_results is None
    run_reid               = reid_file is None and pose_results is None
    run_pose               = pose_results is None

    # Track B — segmentation
    has_rounds = manifest_file is not None or rounds_arg is not None
    run_ocr    = (not skip_scoreboard
                  and scoreboard_samples is None
                  and not has_rounds)
    run_segment = not has_rounds

    # Detection is shared; run if either track needs it
    run_detection_for_seg = detection_file is None and run_segment
    run_detection         = (detection_file is None
                             and (run_detection_for_pose or run_detection_for_seg))

    # Fight processing skipped if any debug flag present
    run_fight = not no_db and verify_pose is None and not verify_scoreboard

    # ----------------------------------------------------------------
    # Print startup plan
    # ----------------------------------------------------------------
    def _det_label() -> str:
        if detection_file:            return f"SKIP — {detection_file}"
        if not run_detection_for_pose and pose_results:
            return f"SKIP — pose results supplied"
        if not run_detection:         return "SKIP — not needed"
        return "RUN"

    def _ocr_label() -> str:
        if skip_scoreboard:       return "SKIP — disabled"
        if scoreboard_samples:    return f"SKIP — {scoreboard_samples}"
        if manifest_file:         return f"SKIP — manifest supplied"
        if rounds_arg:            return "SKIP — rounds explicit"
        return "RUN" + (" (recalibrate)" if recalibrate else "")

    def _seg_label() -> str:
        if manifest_file:  return f"SKIP — {manifest_file}"
        if rounds_arg:     return "SKIP — rounds explicit"
        return "RUN"

    _print_plan("Fight AI — Processing Pipeline", [
        ("Video",           video_file),
        ("Detection",       _det_label()),
        ("ReID",            f"SKIP — {reid_file}" if reid_file
                            else ("SKIP — pose results supplied" if pose_results
                                  else "RUN")),
        ("Pose",            f"SKIP — {pose_results}" if pose_results else "RUN"),
        ("Scoreboard OCR",  _ocr_label()),
        ("Segmentation",    _seg_label()),
        ("Fight process",   "SKIP — debug flags present" if not run_fight
                            else ("SKIP — no-db" if no_db else "RUN")),
        ("Verify pose",     verify_pose if verify_pose else "no"),
        ("Verify scrbrd",   "yes" if verify_scoreboard else "no"),
        ("Debug level",     debug_level),
    ])

    ctx     = DebugContext(debug_root, verbose=verbose)
    timings: dict[str, float] = {}
    outputs: dict[str, str]   = {}

    # ----------------------------------------------------------------
    # Step 1 — YOLO detection
    # ----------------------------------------------------------------
    t0 = time.perf_counter()
    if run_detection:
        print(f"Running YOLO detection: {video_file}")
        detection_file = process_video(video_file)
    elif detection_file:
        print(f"Reusing detection results: {detection_file}")
    timings["detection"]             = time.perf_counter() - t0
    outputs["detection_results"]     = detection_file or "skipped"

    # ----------------------------------------------------------------
    # Step 2 — ReID
    # ----------------------------------------------------------------
    t0 = time.perf_counter()
    if run_reid:
        from video_processing.fighter_reidentification.fighter_reidentification import track_fighters
        print("Running ReID tracking …")
        track_fighters(detection_file, video_path=video_file)
        reid_file = "runs/output_reidentification.json"
    elif reid_file:
        print(f"Reusing ReID results: {reid_file}")
    timings["reid"]              = time.perf_counter() - t0
    outputs["reid_results"]      = reid_file or "skipped"

    # ----------------------------------------------------------------
    # Step 3 — Pose tracking
    # ----------------------------------------------------------------
    t0 = time.perf_counter()
    if run_pose:
        from video_processing.pose_tracking.pose_tracking import track_poses
        print("Running pose tracking …")
        track_poses(reid_file, video_path=video_file)
        pose_results = "runs/pose_results.json"
    elif pose_results:
        print(f"Reusing pose results: {pose_results}")
    timings["pose"]          = time.perf_counter() - t0
    outputs["pose_results"]  = pose_results or "skipped"

    # ----------------------------------------------------------------
    # Step 4 — Scoreboard OCR
    # ----------------------------------------------------------------
    scoreboard_samples_file: Optional[str] = scoreboard_samples
    roi = None

    if run_ocr:
        from video_processing.scoreboard_overlay import (
            calibrate_scoreboard_overlay,
            extract_scoreboard_samples,
            load_roi,
            parse_roi_override,
        )
        override_roi = parse_roi_override(scoreboard_roi) if scoreboard_roi else None

        t0  = time.perf_counter()
        roi = calibrate_scoreboard_overlay(
            video_file,
            override_roi=override_roi,
            recalibrate=recalibrate,
            debug_ctx=ctx,
        )
        timings["scoreboard_calibration"] = time.perf_counter() - t0
        outputs["roi"]                    = f"{debug_root}/roi.json"

        if roi is None:
            print(
                "WARNING: Scoreboard overlay not detected — "
                "falling back to detection-only segmentation.\n"
                f"  Check {debug_root}/calibration_debug/"
            )
        else:
            t0      = time.perf_counter()
            samples = extract_scoreboard_samples(video_file, roi, debug_ctx=ctx)
            timings["scoreboard_ocr"]     = time.perf_counter() - t0
            scoreboard_samples_file       = f"{debug_root}/samples.json"
            outputs["scoreboard_samples"] = scoreboard_samples_file
            print(f"OCR: {len(samples)} samples extracted")

    elif scoreboard_samples:
        print(f"Reusing scoreboard samples: {scoreboard_samples}")
        # Load the cached ROI so scoreboard verification can use it later
        from video_processing.scoreboard_overlay import load_roi
        roi = load_roi(f"{debug_root}/roi.json", video_file)

    # ----------------------------------------------------------------
    # Step 5 — Fight segmentation / load rounds
    # ----------------------------------------------------------------
    rounds:     list[tuple[int, int]] = []
    seg_result: dict                  = {}

    if rounds_arg:
        rounds = _parse_rounds_arg(rounds_arg)
        print(f"Using explicit rounds: {rounds}")
    elif manifest_file:
        rounds = _load_rounds_from_manifest(manifest_file)
        print(f"Loaded rounds from {manifest_file}: {rounds}")
    else:
        t0         = time.perf_counter()
        seg_result = segment_fights(
            detection_file,
            scoreboard_samples_file=scoreboard_samples_file,
            debug_ctx=DebugContext("runs", verbose=verbose),
        )
        timings["segmentation"]       = time.perf_counter() - t0
        rounds                        = seg_result.get("rounds", [])
        outputs["segmentation_debug"] = "runs/segmentation_debug/"
        print(f"\nSegmentation result:")
        print(f"  Rounds : {rounds}")
        print(f"  Quality: {seg_result.get('quality', {})}")

    # ----------------------------------------------------------------
    # Step 6 — Fight processing
    # ----------------------------------------------------------------
    if run_fight:
        from fight_processing.fight_processing import process_fight
        print("Running fight processing …")
        t0 = time.perf_counter()
        process_fight(pose_results, rounds=rounds, save_to_db=not no_db)
        timings["fight_processing"] = time.perf_counter() - t0

    # ----------------------------------------------------------------
    # Step 7 — Pose debug video
    # ----------------------------------------------------------------
    if verify_pose is not None:
        from video_processing.pose_tracking.pose_verification import verify_pose_tracking

        # Determine fps for second→frame conversion
        if pose_results:
            pose_fps = json.load(open(pose_results)).get("fps") or _fps_from_video(video_file)
        else:
            pose_fps = _fps_from_video(video_file)

        start_frame: Optional[int] = None
        end_frame:   Optional[int] = None

        if verify_pose != "all":
            if "-" in verify_pose:
                parts = verify_pose.split("-", 1)
                start_frame = int(float(parts[0]) * pose_fps)
                end_frame   = int(float(parts[1]) * pose_fps)
            else:
                end_frame = int(float(verify_pose) * pose_fps)

        t0 = time.perf_counter()
        verify_pose_tracking(
            pose_results,
            rounds      = rounds,
            video_path  = video_file,
            start_frame = start_frame,
            end_frame   = end_frame,
        )
        timings["verify_pose"] = time.perf_counter() - t0

    # ----------------------------------------------------------------
    # Step 8 — Scoreboard debug video
    # ----------------------------------------------------------------
    if verify_scoreboard and scoreboard_samples_file and roi:
        from video_processing.scoreboard_overlay import build_verification_video, load_samples
        _samples = load_samples(scoreboard_samples_file)
        if _samples:
            t0      = time.perf_counter()
            out_vid = build_verification_video(
                video_file, _samples, roi,
                output_path=f"{debug_root}/verification.mp4",
            )
            timings["verify_scoreboard"] = time.perf_counter() - t0
            outputs["verification_video"] = out_vid

    # ----------------------------------------------------------------
    # Manifest
    # ----------------------------------------------------------------
    build_manifest(
        video_path   = video_file,
        cli_args     = {
            "detection_file":      detection_file,
            "reid_file":           reid_file,
            "pose_results":        pose_results,
            "scoreboard_samples":  scoreboard_samples,
            "manifest_file":       manifest_file,
            "skip_scoreboard":     skip_scoreboard,
            "verify_pose":         verify_pose,
            "verify_scoreboard":   verify_scoreboard,
            "no_db":               no_db,
        },
        step_timings = timings,
        output_paths = outputs,
        summary      = {
            "round_count": len(rounds),
            "rounds":      rounds,
            "quality":     seg_result.get("quality", {}),
        },
    )

    return {"rounds": rounds, "quality": seg_result.get("quality", {})}
