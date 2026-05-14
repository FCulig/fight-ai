"""
Entry point — argument parsing and pipeline dispatch only.
All business logic lives in pipeline.py.
"""

import argparse
import sys

from pipeline import run_segmentation_pipeline, run_full_pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fight AI video processing.")

    p.add_argument("video_input", type=str,
                   help="Path to the .mp4 fight video")

    p.add_argument("--segment", action="store_true",
                   help="Segment a full fight video into rounds")

    # --- Detection ---
    p.add_argument("--detection-file", type=str, default=None,
                   help="Reuse existing detection_results.json (skips YOLO)")

    # --- Scoreboard overlay ---
    p.add_argument("--scoreboard-samples", type=str, default=None,
                   help="Reuse existing scoreboard samples JSON (skips OCR)")
    p.add_argument("--scoreboard-roi", type=str, default=None,
                   help="Manual ROI override: 'x,y,w,h'")
    p.add_argument("--skip-scoreboard", action="store_true",
                   help="Disable scoreboard OCR; use detection signals only")
    p.add_argument("--recalibrate", action="store_true",
                   help="Delete cached ROI and re-run calibration")
    p.add_argument("--verify-scoreboard", action="store_true",
                   help="Render a scoreboard verification video after OCR")

    # --- General ---
    p.add_argument("--no-db", action="store_true",
                   help="Skip database writes (full pipeline only)")
    p.add_argument("--debug-level", choices=["none", "normal", "verbose"],
                   default="verbose",
                   help="Debug output verbosity (default: verbose)")

    return p


def main() -> None:
    args = build_parser().parse_args()

    if args.segment:
        run_segmentation_pipeline(
            args.video_input,
            detection_file    = args.detection_file,
            scoreboard_samples= args.scoreboard_samples,
            scoreboard_roi    = args.scoreboard_roi,
            skip_scoreboard   = args.skip_scoreboard,
            recalibrate       = args.recalibrate,
            verify_scoreboard = args.verify_scoreboard,
            debug_level       = args.debug_level,
        )
    else:
        run_full_pipeline(args.video_input, no_db=args.no_db)


if __name__ == "__main__":
    main()
