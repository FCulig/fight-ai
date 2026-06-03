"""
Entry point — argument parsing and dispatch only.
All business logic lives in pipeline.py.
"""

import argparse

from pipeline import run_batch, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fight AI video processing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Batch mode — scan fight_videos/, process all unprocessed fights
  python main.py

  # Single-file mode — process one video
  python main.py fight.mp4

  # Skip YOLO (reuse an existing detection file)
  python main.py fight.mp4 --detection-file runs/detection_results.json

  # Skip YOLO + ReID (reuse an existing reid file)
  python main.py fight.mp4 --reid-file runs/output_reidentification.json

  # Skip YOLO + ReID + Pose (reuse an existing pose file)
  python main.py fight.mp4 --pose-results runs/pose_results.json

  # Skip OCR + segmentation (supply an existing manifest)
  python main.py fight.mp4 --manifest runs/manifest.json

  # Render pose debug video (also skips process_fight)
  python main.py fight.mp4 --verify-pose

  # Render pose debug video, reuse all heavy steps
  python main.py fight.mp4 --pose-results runs/pose_results.json --manifest runs/manifest.json --verify-pose

Note: all skip flags load the developer-supplied file as a read-only override.
The pipeline never writes intermediate files — PostgreSQL is the only data store.
        """,
    )

    p.add_argument("video_input", nargs="?", default=None,
                   help="Path to the .mp4 fight video. "
                        "Omit to run in batch mode (scans fight_videos/).")

    # ---- File overrides (read-only dev shortcuts to skip expensive steps) ----
    g = p.add_argument_group("file overrides — supply to skip steps")
    g.add_argument("--detection-file", type=str, default=None,
                   metavar="PATH",
                   help="Load detection dict from file — skips YOLO")
    g.add_argument("--track-file", type=str, default=None,
                   metavar="PATH",
                   help="Load track dict from file — skips YOLO + tracking")
    g.add_argument("--reid-file", type=str, default=None,
                   metavar="PATH",
                   help="Deprecated alias for --track-file")
    g.add_argument("--pose-results", type=str, default=None,
                   metavar="PATH",
                   help="Load pose dict from file — skips YOLO + ReID + Pose")
    g.add_argument("--scoreboard-samples", type=str, default=None,
                   metavar="PATH",
                   help="Load scoreboard samples from file — skips OCR calibration + extraction")
    g.add_argument("--manifest", type=str, default=None,
                   metavar="PATH",
                   help="Load rounds from manifest file — skips OCR + segmentation")
    g.add_argument("--rounds", type=str, default=None,
                   metavar="\"s1,e1 s2,e2\"",
                   help="Explicit round boundaries — skips OCR + segmentation")

    # ---- Scoreboard options ----
    g2 = p.add_argument_group("scoreboard overlay options")
    g2.add_argument("--scoreboard-roi", type=str, default=None,
                    metavar="x,y,w,h",
                    help="Manual scoreboard ROI override — skips auto-detection")
    g2.add_argument("--skip-scoreboard", action="store_true",
                    help="Disable scoreboard OCR entirely; use detection signals only")
    g2.add_argument("--recalibrate", action="store_true",
                    help="Delete cached ROI and re-run scoreboard calibration")

    # ---- Debug flags (also cause process_fight to be skipped) ----
    g3 = p.add_argument_group("debug outputs — skips process_fight when used")
    g3.add_argument("--verify-pose", nargs="?", const="all", default=None,
                    metavar="SECONDS or START-END",
                    help=(
                        "Render annotated pose debug video (pose_overlay.mp4). "
                        "Optional value limits output duration: "
                        "'60' → first 60 s, '30-90' → seconds 30–90, "
                        "omit value → full video."
                    ))
    g3.add_argument("--verify-scoreboard", action="store_true",
                    help="Render scoreboard OCR verification video")

    # ---- General ----
    p.add_argument("--debug-level", choices=["none", "normal", "verbose"],
                   default="verbose",
                   help="Debug output verbosity (default: verbose)")

    return p


def main() -> None:
    args = build_parser().parse_args()

    if args.video_input is None:
        run_batch(debug_level=args.debug_level)
    else:
        run_pipeline(
            args.video_input,
            detection_file     = args.detection_file,
            track_file         = args.track_file,
            reid_file          = args.reid_file,
            pose_results       = args.pose_results,
            scoreboard_samples = args.scoreboard_samples,
            manifest_file      = args.manifest,
            scoreboard_roi     = args.scoreboard_roi,
            skip_scoreboard    = args.skip_scoreboard,
            recalibrate        = args.recalibrate,
            rounds_arg         = args.rounds,
            verify_pose        = args.verify_pose,
            verify_scoreboard  = args.verify_scoreboard,
            debug_level        = args.debug_level,
        )


if __name__ == "__main__":
    main()
