"""Evaluation harness entry point.

Run from the ai/ directory:

    python -m eval.cli label   fight_videos/BATURvsSTAMATOVIC.mp4
    python -m eval.cli sanity  fight_videos/BATURvsSTAMATOVIC.mp4
    python -m eval.cli score   fight_videos/BATURvsSTAMATOVIC.mp4
    python -m eval.cli summary
"""

import argparse
import sys
from pathlib import Path

from .schema import LABELS_DIR, FightLabels


def _cmd_label(args) -> int:
    from .label import run_labeler
    run_labeler(args.video, args.labeler)
    return 0


def _cmd_video(args) -> int:
    from .videocheck import check_video, format_video_report

    rep = check_video(args.video)
    print(format_video_report(rep))
    return 1 if rep.truncated else 0


def _cmd_sanity(args) -> int:
    from .predictions import load_predictions
    from .sanity import check, format_sanity

    ok = True
    if not args.skip_decode and Path(args.video).exists():
        from .videocheck import check_video, format_video_report
        vrep = check_video(args.video)
        print(format_video_report(vrep))
        ok = not vrep.truncated

    rep = check(load_predictions(args.video))
    print(format_sanity(rep))

    if args.json:
        from .report_io import save_sanity_report
        path = save_sanity_report(rep, args.json)
        print(f"\n  wrote {path}")

    return 0 if (rep.passed and ok) else 1


def _cmd_score(args) -> int:
    from .predictions import load_predictions
    from .sanity import check, format_sanity
    from .score import format_report, score

    labels = FightLabels.for_video(args.video)
    preds = load_predictions(args.video)

    report = score(labels, preds,
                   tolerance_secs=args.tolerance,
                   strict_fighter=args.strict_fighter)
    print(format_report(report, show_examples=args.examples))

    if not args.no_sanity:
        print(format_sanity(check(preds)))

    if args.json:
        from .report_io import save_report
        path = save_report(report, args.json)
        print(f"\n  wrote {path}")

    return 0


def _cmd_summary(args) -> int:
    paths = ([LABELS_DIR / f"{Path(args.video).stem}.json"] if args.video
             else sorted(LABELS_DIR.glob("*.json")))
    if not paths or not any(p.exists() for p in paths):
        print(f"No label files in {LABELS_DIR}. Create one with:\n"
              f"  python -m eval.cli label <video>")
        return 1

    total_strikes = 0
    total_minutes = 0.0
    for p in paths:
        if not p.exists():
            continue
        labels = FightLabels.load(p)
        print(f"\n{labels.summary()}")
        total_strikes += len(labels.strikes)
        total_minutes += len(labels.scored_frames()) / labels.fps / 60

    print(f"\n{'-' * 60}")
    print(f"TOTAL  {total_strikes} strikes over {total_minutes:.1f} min "
          f"across {len(paths)} video(s)")
    # The Stage-2 skeleton action model needs a few hundred examples per class
    # before it can beat hand-tuned rules; surface progress toward that.
    target = 300
    if total_strikes < target:
        print(f"       {target - total_strikes} more strikes to reach the "
              f"{target}-strike training-set target")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m eval.cli",
        description="Ground-truth labelling and pipeline evaluation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command", required=True)

    lab = sub.add_parser("label", help="open the labelling tool on a video")
    lab.add_argument("video")
    lab.add_argument("--labeler", default="", help="name recorded in the label file")
    lab.set_defaults(func=_cmd_label)

    vid = sub.add_parser("video", help="check a source video decodes fully")
    vid.add_argument("video")
    vid.set_defaults(func=_cmd_video)

    san = sub.add_parser("sanity", help="label-free artifact checks on pipeline output")
    san.add_argument("video")
    san.add_argument("--skip-decode", action="store_true",
                     help="skip the full-decode video integrity check (it is slow "
                          "on long videos)")
    san.add_argument("--json", metavar="PATH",
                     help="write the report as JSON to PATH, alongside git_sha "
                          "and constants_sha256")
    san.set_defaults(func=_cmd_sanity)

    sc = sub.add_parser("score", help="score pipeline output against ground truth")
    sc.add_argument("video")
    sc.add_argument("--tolerance", type=float, default=0.25,
                    metavar="SECS",
                    help="temporal match window for strikes (default: 0.25)")
    sc.add_argument("--strict-fighter", action="store_true",
                    help="require the corner to match for a strike to count as a TP")
    sc.add_argument("--examples", type=int, default=8, metavar="N",
                    help="how many example FN/FP to list (default: 8)")
    sc.add_argument("--no-sanity", action="store_true",
                    help="skip the artifact checks appended to the report")
    sc.add_argument("--json", metavar="PATH",
                    help="write the report as JSON to PATH, alongside git_sha "
                         "and constants_sha256")
    sc.set_defaults(func=_cmd_score)

    smy = sub.add_parser("summary", help="show labelling progress")
    smy.add_argument("video", nargs="?", default=None)
    smy.set_defaults(func=_cmd_summary)

    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (FileNotFoundError, LookupError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
