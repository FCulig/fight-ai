"""Evaluation harness entry point.

Ground truth is labelled in the frontend (Annotate page → label_events /
label_spans in Postgres), not with a standalone tool. `export` is what turns
that into the on-disk ground truth this harness scores against.

Run from the ai/ directory:

    python -m eval.cli export  fight_videos/BATURvsSTAMATOVIC.mp4
    python -m eval.cli sanity  fight_videos/BATURvsSTAMATOVIC.mp4
    python -m eval.cli score   fight_videos/BATURvsSTAMATOVIC.mp4
    python -m eval.cli summary
"""

import argparse
import sys
from pathlib import Path

from .schema import LABELS_DIR, FightLabels
from .score import DEFAULT_TOLERANCE_SECS


def _cmd_export(args) -> int:
    from .labels_db import NotLabeled, build_labels

    try:
        labels = build_labels(args.video)
    except NotLabeled as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.as_pass:
        path = labels.save(LABELS_DIR / f"{Path(args.video).stem}.{args.as_pass}.json")
    else:
        path = labels.save()
    print(labels.summary())
    print(f"\n  wrote {path}")
    return 0


def _cmd_video(args) -> int:
    from .videocheck import check_video, format_video_report

    try:
        rep = check_video(args.video)
    except Exception as e:
        # A file OpenCV can't even open (as opposed to one that opens but
        # decodes only part of itself) never reaches the truncation check
        # below. Without this, --fight-id mode would leave the fight stuck
        # in VALIDATING forever instead of surfacing INVALID.
        print(f"error: {e}", file=sys.stderr)
        if args.fight_id is not None:
            _mark_invalid(args.fight_id)
        return 2

    print(format_video_report(rep))

    if args.fight_id is not None:
        _validate_and_dispatch(args.fight_id, args.video, rep, args.skip_events)

    return 1 if rep.truncated else 0


def _mark_invalid(fight_id: int) -> None:
    from database import set_fight_state
    from models.FightProcessingState import FightProcessingState as S

    set_fight_state(fight_id, S.INVALID)


def _validate_and_dispatch(fight_id: int, video: str, rep, skip_events: bool) -> None:
    """Write the validation result to the fight's DB row and, on a clean
    result, hand off to the real pipeline. This is the entry point
    `run_validation_async` (backend/app/services/pipeline_runner.py) spawns —
    it is the only piece of upload validation that writes to the DB, since
    `eval.cli video` alone only prints a report and returns an exit code.
    See plan 0b.
    """
    import subprocess
    import sys
    from pathlib import Path

    from database import set_fight_state, set_video_check, set_fight_pid
    from models.FightProcessingState import FightProcessingState as S

    set_video_check(fight_id, rep.reported_frames, rep.decoded_frames)

    if rep.truncated:
        set_fight_state(fight_id, S.INVALID)
        return

    # Clear the validator's own pid before spawning the pipeline so there is
    # no window where `pid` names a process that has already exited.
    set_fight_pid(fight_id, None)

    ai_dir = Path(__file__).resolve().parents[1]
    log_dir = ai_dir / "runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "upload_pipeline.log", "ab")
    cmd = [sys.executable, "main.py", video]
    if skip_events:
        cmd.append("--skip-events")
    proc = subprocess.Popen(cmd, cwd=ai_dir, stdout=log, stderr=log)
    set_fight_pid(fight_id, proc.pid)


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


def _resolve_tolerance(override: float | None) -> float:
    if override is not None and override != DEFAULT_TOLERANCE_SECS:
        print(f"  ⚠ --tolerance-override {override}s differs from the "
              f"pinned default {DEFAULT_TOLERANCE_SECS}s — the tolerance is "
              f"a scored quantity (plan 0f), not a free dial. Record why.",
              file=sys.stderr)
    return override if override is not None else DEFAULT_TOLERANCE_SECS


def _cmd_score(args) -> int:
    from .predictions import load_predictions
    from .sanity import check, format_sanity
    from .score import format_report, score

    labels = FightLabels.for_video(args.video)
    preds = load_predictions(args.video)
    tolerance_secs = _resolve_tolerance(args.tolerance_override)

    report = score(labels, preds,
                   tolerance_secs=tolerance_secs,
                   strict_fighter=args.strict_fighter)
    print(format_report(report, show_examples=args.examples))
    _print_agreement_ceiling(args.video, report.strikes.tolerance_frames)

    if not args.no_sanity:
        print(format_sanity(check(preds)))

    if args.json:
        from .report_io import save_report
        path = save_report(report, args.json)
        print(f"\n  wrote {path}")

    return 0


def _print_agreement_ceiling(video: str, tolerance_frames: int) -> None:
    """`labels/<stem>.agreement.json`, if present, caps how good a score can
    honestly be — an F1 above it is fitting label noise, not detecting
    strikes better than a second human would. Only meaningful when it was
    measured at the same tolerance as this run (plan 0f)."""
    path = LABELS_DIR / f"{Path(video).stem}.agreement.json"
    if not path.exists():
        return
    from .report_io import load_report_json
    raw = load_report_json(path)
    agreement_tol = raw.get("tolerance_frames")
    if agreement_tol != tolerance_frames:
        print(f"\n  (human agreement ceiling in {path.name} was measured at "
              f"±{agreement_tol}f, not ±{tolerance_frames}f for this run — "
              f"not comparable, skipping)")
        return
    d = raw["report"]["strikes"]["detection"]
    tp, fp, fn = d["tp"], d["fp"], d["fn"]
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    print(f"\n  human agreement ceiling: F1 {f1:.1%}  (from {path.name})")


def _cmd_agreement(args) -> int:
    from .score import format_report, score

    passes = FightLabels.passes_for_video(args.video)
    if len(passes) != 2:
        print(f"error: agreement needs exactly 2 label passes for "
              f"{args.video}, found {len(passes)}. Label a second, "
              f"independent pass (leave a week between passes if it's the "
              f"same labeller) and export it with:\n"
              f"  python -m eval.cli export {args.video} --as <name>",
              file=sys.stderr)
        return 1

    a, b = passes
    tolerance_secs = _resolve_tolerance(args.tolerance_override)

    # score() is asymmetric (labels=truth, preds=on trial); between two human
    # passes there is no truth, so F1 is the only symmetric, honest headline
    # — swapping a/b trades precision for recall but leaves F1 unchanged.
    # Verifying that is the regression test for "is this report silently
    # asymmetric." Plan 0e/0f.
    report = score(a, b, tolerance_secs=tolerance_secs)
    print(format_report(report, show_examples=args.examples))

    s = report.strikes
    print(f"\nAGREEMENT CEILINGS  ({a.labeler or 'pass A'} vs {b.labeler or 'pass B'})")
    print(f"  detection F1        {s.detection.f1:6.1%}")
    if s.family_accuracy is not None:
        print(f"  family agreement    {s.family_accuracy:6.1%}  ({s.family_total} specific matches)")
    if s.fighter_accuracy is not None:
        print(f"  corner agreement    {s.fighter_accuracy:6.1%}  ({s.fighter_total} matches) "
              f"— expect ~100%; anything less is a labelling-UI defect, not a labeller one")
    if s.family_confusion:
        print("  (see 'family confusion' above — names which distinctions are unreliable)")

    from .report_io import save_report
    path = save_report(report, LABELS_DIR / f"{Path(args.video).stem}.agreement.json")
    print(f"\n  wrote {path}")
    return 0


def _cmd_inject_swap(args) -> int:
    from .corner_swap_check import inject_swap

    n = inject_swap(args.video, args.start, args.end)
    print(f"flipped corner on {n} fighter_frames rows in "
          f"[{args.start}, {args.end}] for {args.video}")
    print("running this again with the same --start/--end restores the original assignment")
    return 0


def _cmd_corner_swap_recall(args) -> int:
    from .corner_swap_check import format_recall, measure_recall

    result = measure_recall(args.video, args.start, args.end)
    print(format_recall(result, args.start, args.end))
    return 0 if result.detected else 1


def _cmd_summary(args) -> int:
    paths = ([LABELS_DIR / f"{Path(args.video).stem}.json"] if args.video
             else sorted(LABELS_DIR.glob("*.json")))
    if not paths or not any(p.exists() for p in paths):
        print(f"No label files in {LABELS_DIR}. Label the fight in the "
              f"Annotate page, finish labeling, then create one with:\n"
              f"  python -m eval.cli export <video>")
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

    exp = sub.add_parser("export", help="build ground truth from label_events/"
                                          "label_spans and write eval/labels/*.json")
    exp.add_argument("video")
    exp.add_argument("--as", dest="as_pass", metavar="NAME", default=None,
                     help="write as a second labelled pass — "
                          "labels/<stem>.<NAME>.json — instead of overwriting "
                          "the primary file (for the double-labelling "
                          "agreement ceiling, see `agreement`)")
    exp.set_defaults(func=_cmd_export)

    vid = sub.add_parser("video", help="check a source video decodes fully")
    vid.add_argument("video")
    vid.add_argument("--fight-id", type=int, default=None,
                     help="upload-validation mode: write the result to this "
                          "fight's DB row and, if clean, spawn the pipeline "
                          "(used by the backend upload handler, not for "
                          "interactive use)")
    vid.add_argument("--skip-events", action="store_true",
                     help="with --fight-id: forward --skip-events to the "
                          "spawned pipeline (manual-labeling track)")
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
    sc.add_argument("--tolerance-override", type=float, default=None,
                    metavar="SECS",
                    help=f"override the pinned matching tolerance "
                         f"(default: {DEFAULT_TOLERANCE_SECS}s, see score.py "
                         f"DEFAULT_TOLERANCE_SECS) — the tolerance is a "
                         f"scored quantity, not a free dial; using this warns loudly")
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

    agr = sub.add_parser("agreement", help="double-labelling agreement ceiling "
                                             "between two label passes")
    agr.add_argument("video")
    agr.add_argument("--tolerance-override", type=float, default=None,
                     metavar="SECS", help="see `score --tolerance-override`; "
                     "must match to compare against a score run's ceiling")
    agr.add_argument("--examples", type=int, default=8, metavar="N",
                     help="how many example disagreements to list (default: 8)")
    agr.set_defaults(func=_cmd_agreement)

    inj = sub.add_parser("inject-swap", help="flip fighter_frames.corner over "
                                                "a frame range — its own inverse "
                                                "(plan 0g corner-swap recall test)")
    inj.add_argument("video")
    inj.add_argument("--start", type=int, required=True, metavar="FRAME")
    inj.add_argument("--end", type=int, required=True, metavar="FRAME")
    inj.set_defaults(func=_cmd_inject_swap)

    rec = sub.add_parser("corner-swap-recall", help="compare a labeller's "
                                                       "corner_swap spans against "
                                                       "an injected window")
    rec.add_argument("video")
    rec.add_argument("--start", type=int, required=True, metavar="FRAME")
    rec.add_argument("--end", type=int, required=True, metavar="FRAME")
    rec.set_defaults(func=_cmd_corner_swap_recall)

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
