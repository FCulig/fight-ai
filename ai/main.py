"""
Entry point — argument parsing and dispatch only.
All business logic lives in pipeline.py.
"""

import argparse

from pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fight AI video processing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline — run everything from scratch
  python main.py fight.mp4

  # Skip YOLO (reuse existing detection)
  python main.py fight.mp4 --detection-file runs/detection_results.json

  # Skip YOLO + ReID (reuse existing reid output)
  python main.py fight.mp4 --reid-file runs/output_reidentification.json

  # Skip YOLO + ReID + Pose (reuse existing pose results)
  python main.py fight.mp4 --pose-results runs/pose_results.json

  # Skip OCR + segmentation (supply existing manifest)
  python main.py fight.mp4 --manifest runs/manifest.json

  # Render pose debug video (also skips process_fight)
  python main.py fight.mp4 --verify-pose

  # Render pose debug video, reuse all heavy steps
  python main.py fight.mp4 --pose-results runs/pose_results.json --manifest runs/manifest.json --verify-pose
        """,
    )

    p.add_argument("video_input", type=str,
                   help="Path to the .mp4 fight video")

    # ---- File overrides (supplying a file skips that step + all earlier steps) ----
    g = p.add_argument_group("file overrides — supply to skip steps")
    g.add_argument("--detection-file", type=str, default=None,
                   metavar="PATH",
                   help="Reuse detection_results.json — skips YOLO")
    g.add_argument("--reid-file", type=str, default=None,
                   metavar="PATH",
                   help="Reuse output_reidentification.json — skips YOLO + ReID")
    g.add_argument("--pose-results", type=str, default=None,
                   metavar="PATH",
                   help="Reuse pose_results.json — skips YOLO + ReID + Pose")
    g.add_argument("--scoreboard-samples", type=str, default=None,
                   metavar="PATH",
                   help="Reuse scoreboard samples JSON — skips OCR calibration + extraction")
    g.add_argument("--manifest", type=str, default=None,
                   metavar="PATH",
                   help="Reuse manifest.json — skips OCR + segmentation")
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
    p.add_argument("--no-db", action="store_true",
                   help="Skip database writes")
    p.add_argument("--debug-level", choices=["none", "normal", "verbose"],
                   default="verbose",
                   help="Debug output verbosity (default: verbose)")

    return p


def main() -> None:
    args = build_parser().parse_args()

    run_pipeline(
        args.video_input,
        detection_file     = args.detection_file,
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
        no_db              = args.no_db,
        debug_level        = args.debug_level,
    )


if __name__ == "__main__":
    main()
