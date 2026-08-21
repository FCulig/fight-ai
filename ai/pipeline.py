"""
Pipeline orchestration for the fight-ai processing steps.

main.py is a pure argument parser and dispatcher — all business logic
lives here.

Philosophy
----------
- No intermediate files are written.  Every step passes its output to the
  next step in-memory.  PostgreSQL is the only data store.
- In single-file mode (`python main.py fight.mp4`), run_pipeline() upserts
  the fight row, runs the full pipeline, and sets state='completed'.
- In batch mode (`python main.py`), run_batch() registers new videos, then
  calls run_pipeline() for each non-completed fight, passing the fight_id so
  run_pipeline skips the upsert.  run_batch() owns the completed state update.

Pipeline order
--------------
Track A (pose):     1. YOLO detection
                    2. Fighter tracking  (geometry-only, Hungarian matching)
                    3. Pose tracking
                    3b. Corner assignment (glove-tape HSV vote → red/blue remap)
Track B (segments): 1. YOLO detection  (shared with A)
                    4. Scoreboard OCR
                    5. Fight segmentation
Common finish:      6. process_fight   (skipped when any debug flag present)
Debug outputs:      7. Pose debug video        (--verify-pose only)
                    8. Scoreboard debug video  (--verify-scoreboard only)

Skip matrix
-----------
--detection-file      skips step 1 (loads file into detection dict)
--track-file          skips steps 1–2 (loads file into track dict)
--pose-results        skips steps 1–3 (loads file into pose dict)
--scoreboard-samples  skips step 4 (loads file into samples list)
--manifest            skips steps 4–5
--rounds "s,e …"      skips steps 4–5 (explicit round boundaries)
any debug flag        skips step 6
"""

import json
import time
from pathlib import Path
from typing import Optional

from database import set_fight_state, set_segmentation_review
from debug import DebugContext
from models.FightProcessingState import FightProcessingState as S
from video_processing.video_processing import process_video
from video_processing.fight_segmentation import segment_fights


# ---------------------------------------------------------------------------
# Startup plan printer
# ---------------------------------------------------------------------------

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

def _extract_video_meta(video_path: str) -> tuple[int, int, int]:
    """Return (fps_int, width, height) from a video file."""
    import cv2
    cap    = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    fps    = round(cap.get(cv2.CAP_PROP_FPS)) or 30
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return fps, width, height


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


def _load_json(path: str) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Unified pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    video_file: str,
    *,
    fight_id: Optional[int]        = None,
    # ---- File overrides (supply to skip that step + all earlier steps) ----
    detection_file: Optional[str]     = None,
    track_file: Optional[str]         = None,
    reid_file: Optional[str]          = None,   # deprecated alias for track_file
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
    verify_pose: Optional[str]        = None,
    verify_scoreboard: bool           = False,
    # ---- Manual-labeling mode ----
    skip_events: bool                 = False,
    # ---- General ----
    debug_level: str                  = "verbose",
) -> dict:
    """
    Run the full fight-ai pipeline with smart step skipping.

    All data is passed in-memory between steps — no intermediate files are
    written.  PostgreSQL is the only data store.

    Args:
        fight_id: When None (single-file mode), a fight row is upserted and
                  state is set to 'completed' on success.  When provided (batch
                  mode), the record already exists; fps is read from it and
                  the completed state is managed by run_batch().

    Returns:
        {"rounds": [...], "quality": {...}}
    """
    verbose    = debug_level != "none"
    debug_root = "runs/scoreboard_overlay"

    # Backwards-compat: --reid-file is an alias for --track-file
    if reid_file and not track_file:
        track_file = reid_file

    # ----------------------------------------------------------------
    # Resolve fps from DB (single-file: upsert; batch: select)
    # ----------------------------------------------------------------
    _single_file_mode = fight_id is None
    fps: int
    red_fighter_id: Optional[int] = None
    blue_fighter_id: Optional[int] = None

    if _single_file_mode:
        from sqlalchemy import text
        from database import SessionLocal
        fps, width, height = _extract_video_meta(video_file)
        db = SessionLocal()
        try:
            row = db.execute(
                text("""
                    INSERT INTO fights (video_path, fps, width, height)
                    VALUES (:path, :fps, :w, :h)
                    ON CONFLICT (video_path) DO UPDATE
                    SET fps    = EXCLUDED.fps,
                        width  = EXCLUDED.width,
                        height = EXCLUDED.height,
                        state  = 'queued'
                    RETURNING id, red_fighter_id, blue_fighter_id
                """),
                {"path": video_file, "fps": fps, "w": width, "h": height},
            ).fetchone()
            fight_id = row.id
            red_fighter_id = row.red_fighter_id
            blue_fighter_id = row.blue_fighter_id
            db.commit()
        finally:
            db.close()
    else:
        from sqlalchemy import text
        from database import SessionLocal
        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT fps, width, height, red_fighter_id, blue_fighter_id "
                     "FROM fights WHERE id = :id"),
                {"id": fight_id},
            ).fetchone()
            fps = row.fps
            width = row.width
            height = row.height
            red_fighter_id = row.red_fighter_id
            blue_fighter_id = row.blue_fighter_id
        finally:
            db.close()

    # ----------------------------------------------------------------
    # In debug modes, try loading rounds from DB — skips OCR + segmentation
    # ----------------------------------------------------------------
    _db_rounds: Optional[list[tuple[int, int]]] = None
    _explicit_rounds = manifest_file is not None or rounds_arg is not None
    if (verify_pose is not None or verify_scoreboard) and not _explicit_rounds:
        from sqlalchemy import text
        from database import SessionLocal
        db = SessionLocal()
        try:
            rows = db.execute(
                text(
                    "SELECT start_frame, end_frame FROM rounds "
                    "WHERE fight_id = :id ORDER BY round_number"
                ),
                {"id": fight_id},
            ).fetchall()
            if rows:
                _db_rounds = [(row.start_frame, row.end_frame) for row in rows]
                print(f"Debug mode: loaded {len(_db_rounds)} round(s) from DB "
                      f"(fight_id={fight_id}) — skipping OCR + segmentation")
        finally:
            db.close()

    # ----------------------------------------------------------------
    # Determine which steps to run
    # ----------------------------------------------------------------

    # Track A — pose
    run_detection_for_pose = track_file is None and pose_results is None
    run_tracking           = track_file is None and pose_results is None
    run_pose               = pose_results is None

    # Track B — segmentation
    has_rounds = manifest_file is not None or rounds_arg is not None or _db_rounds is not None
    run_ocr    = (not skip_scoreboard
                  and scoreboard_samples is None
                  and not has_rounds)
    run_segment = not has_rounds

    # Detection is shared; run if either track needs it
    run_detection_for_seg = detection_file is None and run_segment
    run_detection         = (detection_file is None
                             and (run_detection_for_pose or run_detection_for_seg))

    # Fight processing skipped if any debug flag present
    run_fight = verify_pose is None and not verify_scoreboard

    # ----------------------------------------------------------------
    # Print startup plan
    # ----------------------------------------------------------------
    def _det_label() -> str:
        if detection_file:            return f"SKIP — {detection_file}"
        if not run_detection_for_pose and pose_results:
            return "SKIP — pose results supplied"
        if not run_detection:         return "SKIP — not needed"
        return "RUN"

    def _ocr_label() -> str:
        if skip_scoreboard:           return "SKIP — disabled"
        if scoreboard_samples:        return f"SKIP — {scoreboard_samples}"
        if manifest_file:             return f"SKIP — manifest supplied"
        if rounds_arg:                return "SKIP — rounds explicit"
        if _db_rounds is not None:    return "SKIP — rounds from DB"
        return "RUN" + (" (recalibrate)" if recalibrate else "")

    def _seg_label() -> str:
        if manifest_file:             return f"SKIP — {manifest_file}"
        if rounds_arg:                return "SKIP — rounds explicit"
        if _db_rounds is not None:    return "SKIP — rounds from DB"
        return "RUN"

    def _track_label() -> str:
        if track_file:    return f"SKIP — {track_file}"
        if pose_results:  return "SKIP — pose results supplied"
        return "RUN"

    _print_plan("Fight AI — Processing Pipeline", [
        ("Fight ID",        str(fight_id)),
        ("Video",           video_file),
        ("FPS",             str(fps)),
        ("Detection",       _det_label()),
        ("Tracking",        _track_label()),
        ("Pose",            f"SKIP — {pose_results}" if pose_results else "RUN"),
        ("Corner assign",   "SKIP — pose results supplied" if pose_results else "RUN"),
        ("Scoreboard OCR",  _ocr_label()),
        ("Segmentation",    _seg_label()),
        ("Fight process",   "SKIP — debug flags present" if not run_fight
                             else "RUN (events skipped — manual labeling)" if skip_events
                             else "RUN"),
        ("Verify pose",     verify_pose if verify_pose else "no"),
        ("Verify scrbrd",   "yes" if verify_scoreboard else "no"),
        ("Debug level",     debug_level),
    ])

    ctx     = DebugContext(debug_root, verbose=verbose)
    timings: dict[str, float] = {}

    # In-memory data — each step consumes the previous step's output dict.
    detection_data: Optional[dict] = None
    track_data:     Optional[dict] = None
    pose_data:      Optional[dict] = None

    try:
        # ----------------------------------------------------------------
        # Step 1 — YOLO detection
        # ----------------------------------------------------------------
        t0 = time.perf_counter()
        if run_detection:
            set_fight_state(fight_id, S.DETECTING)
            print(f"Running YOLO detection: {video_file}")
            detection_data = process_video(video_file)
        elif detection_file:
            print(f"Reusing detection results: {detection_file}")
            detection_data = _load_json(detection_file)
        timings["detection"] = time.perf_counter() - t0

        # ----------------------------------------------------------------
        # Step 2 — Fighter tracking (geometry-only, Hungarian matching)
        # ----------------------------------------------------------------
        t0 = time.perf_counter()
        if run_tracking:
            set_fight_state(fight_id, S.TRACKING)
            from video_processing.fighter_tracking.fighter_tracking import track_fighters
            print("Running fighter tracking …")
            track_data = track_fighters(detection_data, video_path=video_file)
        elif track_file:
            print(f"Reusing track results: {track_file}")
            track_data = _load_json(track_file)
        timings["tracking"] = time.perf_counter() - t0

        # ----------------------------------------------------------------
        # Step 3 — Pose tracking
        # ----------------------------------------------------------------
        t0 = time.perf_counter()
        if run_pose:
            set_fight_state(fight_id, S.POSE)
            from video_processing.pose_tracking.pose_tracking import track_poses
            print("Running pose tracking …")
            pose_data = track_poses(track_data, video_path=video_file)
        elif pose_results:
            print(f"Reusing pose results: {pose_results}")
            pose_data = _load_json(pose_results)
        timings["pose"] = time.perf_counter() - t0

        # ----------------------------------------------------------------
        # Step 3b — Corner assignment (glove-tape HSV vote)
        # ----------------------------------------------------------------
        if pose_data is not None and not pose_results:
            set_fight_state(fight_id, S.CORNERS)
            from video_processing.corner_assignment.corner_assignment import assign_corners
            print("Running corner assignment …")
            t0        = time.perf_counter()
            pose_data = assign_corners(pose_data, video_path=video_file)
            timings["corner_assignment"] = time.perf_counter() - t0

        # ----------------------------------------------------------------
        # Step 4 — Scoreboard OCR
        # ----------------------------------------------------------------
        scoreboard_data: Optional[list[dict]] = None
        roi = None

        if run_ocr:
            set_fight_state(fight_id, S.SCOREBOARD)
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

            if roi is None:
                print(
                    "WARNING: Scoreboard overlay not detected — "
                    "falling back to detection-only segmentation.\n"
                    f"  Check {debug_root}/calibration_debug/"
                )
            else:
                t0             = time.perf_counter()
                scoreboard_data = extract_scoreboard_samples(video_file, roi, debug_ctx=ctx)
                timings["scoreboard_ocr"] = time.perf_counter() - t0
                print(f"OCR: {len(scoreboard_data)} samples extracted")

        elif scoreboard_samples:
            print(f"Reusing scoreboard samples: {scoreboard_samples}")
            scoreboard_data = _load_json(scoreboard_samples)
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
        elif _db_rounds is not None:
            rounds = _db_rounds
            print(f"Using rounds from DB: {rounds}")
        else:
            set_fight_state(fight_id, S.SEGMENTING)
            t0         = time.perf_counter()
            seg_result = segment_fights(
                detection_data,
                fps=fps,
                width=width,
                scoreboard_samples=scoreboard_data,
                debug_ctx=DebugContext("runs", verbose=verbose),
            )
            timings["segmentation"] = time.perf_counter() - t0
            rounds                  = seg_result.get("rounds", [])
            quality                 = seg_result.get("quality", {})
            metrics                 = quality.get("metrics", {})

            print(f"\nSegmentation result:")
            print(f"  Rounds : {rounds}")
            print(f"  Source : {metrics.get('segmentation_source', 'unknown')}  "
                  f"(timer coverage {metrics.get('ocr_timer_coverage', 0):.0%}, "
                  f"round coverage {metrics.get('ocr_round_coverage', 0):.0%})")
            print(f"  Excluded (replays): {seg_result.get('excluded_ranges', [])}")
            print(f"  Quality: {quality}")
            if quality.get("needs_review"):
                print(f"  ** NEEDS REVIEW: {quality.get('review_reason', '')}")

            # Record whether the scoreboard actually corroborated these rounds,
            # so a detection-only guess arrives in the annotation UI visibly
            # provisional instead of indistinguishable from a verified one.
            set_segmentation_review(
                fight_id,
                bool(quality.get("needs_review", False)),
                quality.get("review_reason") or None,
            )

        excluded_ranges: list[tuple[int, int]] = seg_result.get("excluded_ranges", [])

        # ----------------------------------------------------------------
        # Step 6 — Fight processing
        # ----------------------------------------------------------------
        if run_fight and skip_events:
            # Manual-labeling mode: write fighter_frames + rounds only, skip
            # the strike/fight-state detection state machine entirely — the
            # user tags those by hand on the Annotate screen. The fight stays
            # in labeling_in_progress until they finish (no COMPLETED here).
            set_fight_state(fight_id, S.LABELING_IN_PROGRESS)
            from fight_processing.fight_processing import write_frames_and_rounds
            print("Writing fighter frames + rounds (event detection skipped) …")
            t0 = time.perf_counter()
            write_frames_and_rounds(pose_data, fight_id=fight_id, fps=fps, rounds=rounds)
            timings["fight_processing"] = time.perf_counter() - t0
        elif run_fight:
            set_fight_state(fight_id, S.ANALYZING)
            from fight_processing.fight_processing import process_fight
            print("Running fight processing …")
            t0 = time.perf_counter()
            process_fight(pose_data, fight_id=fight_id, fps=fps, rounds=rounds,
                          excluded_ranges=excluded_ranges,
                          red_fighter_id=red_fighter_id, blue_fighter_id=blue_fighter_id)
            timings["fight_processing"] = time.perf_counter() - t0

            if _single_file_mode:
                set_fight_state(fight_id, S.COMPLETED)

    except Exception:
        set_fight_state(fight_id, S.FAILED)
        raise

    # ----------------------------------------------------------------
    # Step 7 — Pose debug video
    # ----------------------------------------------------------------
    if verify_pose is not None:
        from video_processing.pose_tracking.pose_verification import verify_pose_tracking

        start_frame: Optional[int] = None
        end_frame:   Optional[int] = None

        if verify_pose != "all":
            if "-" in verify_pose:
                parts       = verify_pose.split("-", 1)
                start_frame = int(float(parts[0]) * fps)
                end_frame   = int(float(parts[1]) * fps)
            else:
                end_frame = int(float(verify_pose) * fps)

        t0 = time.perf_counter()
        verify_pose_tracking(
            pose_data,
            rounds      = rounds,
            fps         = fps,
            video_path  = video_file,
            start_frame = start_frame,
            end_frame   = end_frame,
        )
        timings["verify_pose"] = time.perf_counter() - t0

    # ----------------------------------------------------------------
    # Step 8 — Scoreboard debug video
    # ----------------------------------------------------------------
    if verify_scoreboard and scoreboard_data and roi:
        from video_processing.scoreboard_overlay import build_verification_video
        t0      = time.perf_counter()
        out_vid = build_verification_video(
            video_file, scoreboard_data, roi,
            output_path=f"{debug_root}/verification.mp4",
        )
        timings["verify_scoreboard"] = time.perf_counter() - t0

    return {"rounds": rounds, "excluded_ranges": excluded_ranges, "quality": seg_result.get("quality", {})}


# ---------------------------------------------------------------------------
# Batch processor
# ---------------------------------------------------------------------------

def run_batch(
    fight_videos_dir: str = "fight_videos",
    debug_level: str      = "verbose",
) -> None:
    """
    Default entry point when no video argument is given.

    1. Creates fight_videos_dir if absent and returns early with a hint.
    2. Scans for .mp4 / .mkv / .mov files and registers any new ones in the
       fights table (DO NOTHING on conflict — existing rows are never touched).
    3. Queries all non-completed fights and runs run_pipeline() for each.
    4. On success: sets state='completed'.
       On failure: sets state='failed', logs the traceback; retried on next run.
    """
    import cv2
    dir_path = Path(fight_videos_dir)
    if not dir_path.exists():
        dir_path.mkdir(parents=True, exist_ok=True)
        print(
            f"Created {fight_videos_dir}/ — "
            "place .mp4 / .mkv / .mov files here and re-run."
        )
        return

    extensions  = {".mp4", ".mkv", ".mov"}
    video_files = [p for p in dir_path.rglob("*") if p.suffix.lower() in extensions]

    if not video_files:
        print(f"No video files found in {fight_videos_dir}/")
        return

    print(f"Found {len(video_files)} video file(s) in {fight_videos_dir}/")

    # ------------------------------------------------------------------
    # Register new videos (DO NOTHING on conflict)
    # ------------------------------------------------------------------
    from sqlalchemy import text
    from database import SessionLocal
    db = SessionLocal()
    try:
        for vf in video_files:
            cap = cv2.VideoCapture(str(vf))
            if not cap.isOpened():
                print(f"WARNING: Cannot open {vf} — skipping registration")
                continue
            fps_raw = cap.get(cv2.CAP_PROP_FPS)
            width   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            fps = round(fps_raw) if fps_raw > 0 else 30

            db.execute(
                text("""
                    INSERT INTO fights (video_path, fps, width, height)
                    VALUES (:path, :fps, :w, :h)
                    ON CONFLICT (video_path) DO NOTHING
                """),
                {"path": str(vf), "fps": fps, "w": width, "h": height},
            )
        db.commit()

        rows = db.execute(
            text(
                "SELECT id, video_path, fps, width, height "
                "FROM fights WHERE state NOT IN "
                "('completed', 'labeling_in_progress', 'labeling_complete', "
                "'validating', 'invalid') "
                "ORDER BY id"
            )
        ).fetchall()
    finally:
        db.close()

    if not rows:
        print("All fights already processed — nothing to do.")
        return

    print(f"\n{len(rows)} fight(s) pending processing:")
    for row in rows:
        print(f"  [id={row.id}] {row.video_path}")

    for row in rows:
        print(f"\n{'='*60}")
        print(f"Processing fight id={row.id}: {row.video_path}")
        try:
            run_pipeline(
                video_file  = row.video_path,
                fight_id    = row.id,
                debug_level = debug_level,
            )

            set_fight_state(row.id, S.COMPLETED)
            print(f"Fight {row.id} processed successfully.")

        except Exception:
            import traceback
            traceback.print_exc()
            set_fight_state(row.id, S.FAILED)
            print(
                f"ERROR: Fight {row.id} failed — "
                "state set to 'failed', will retry on next run."
            )
