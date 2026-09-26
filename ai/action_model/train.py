"""Train the skeleton action model.

    python -m action_model.train [--epochs 60] [--promote] [--no-negatives] [--device cpu]

Training and validation data never share a fight, by construction:

- **train** — every QA-verified hand label on `purpose='training_data'`
  fights (dataset.TRAINING_EVENTS_SQL) plus sampled `none` windows.
- **validation** — `purpose='reference'` fights only
  (dataset.REFERENCE_EVENTS_SQL). No validation data is ever carved out of a
  training fight. Scored after every epoch; the checkpoint kept is the epoch
  with the best validation macro-F1. Because validation picks the epoch, its
  best score is slightly optimistic — a second reference fight left out of
  selection would be the unbiased test number.

Writes runs/action_model/<timestamp>/{model.pt, report.json, report.md}.
"""

import argparse
import json
import shutil
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from torch import nn

from database import SessionLocal

from . import config
from .config import CLASSES, IN_CHANNELS, JITTER_STEPS, N_JOINTS, PERSON_CHANNELS, TARGETS, WINDOW_STEPS
from .dataset import REFERENCE_EVENTS_SQL, TRAINING_EVENTS_SQL, build_dataset
from .windows import centre_crop
from .model import ActionNet

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs" / "action_model"

# x/y channel indices within one sample (both people), for augmentation.
_XY = np.array([p * PERSON_CHANNELS + j * 3 + k
                for p in (0, 1) for j in range(N_JOINTS) for k in (0, 1)])


def _class_weights(y: np.ndarray, n: int) -> torch.Tensor:
    counts = np.bincount(y, minlength=n).astype(np.float64)
    w = np.where(counts > 0, 1.0 / np.sqrt(np.maximum(counts, 1)), 0.0)
    w *= (counts > 0).sum() / w.sum()
    return torch.tensor(w, dtype=torch.float32)


def _augment(x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    b = x.shape[0]
    shifts = rng.integers(0, 2 * JITTER_STEPS + 1, size=b)
    out = np.stack([x[i, :, s:s + WINDOW_STEPS] for i, s in enumerate(shifts)])
    xy = out[:, _XY, :]
    nonzero = xy != 0
    xy = xy * rng.uniform(0.9, 1.1, size=(b, 1, 1)) + rng.normal(0, 0.02, size=xy.shape) * nonzero
    out[:, _XY, :] = xy
    return out.astype(np.float32)


def train_model(data: dict, val: dict | None, epochs: int, device: str, seed: int):
    """Returns (model restored to its best-validation epoch, per-epoch history).
    With no validation data the last epoch is kept."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = ActionNet().to(device)
    x_all, fam, tgt = data["x"], data["family"], data["target"]
    n_train = len(fam)
    fam_loss = nn.CrossEntropyLoss(weight=_class_weights(fam, len(CLASSES)).to(device))
    tgt_loss = nn.CrossEntropyLoss(ignore_index=-1)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-2)
    batch = 64
    steps = epochs * int(np.ceil(n_train / batch))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=2e-3, total_steps=steps)

    history, best = [], None
    for epoch in range(1, epochs + 1):
        model.train()
        order = rng.permutation(n_train)
        for s in range(0, len(order), batch):
            b = order[s:s + batch]
            if len(b) < 2:
                continue  # BatchNorm needs >1 sample
            xb = torch.from_numpy(_augment(x_all[b], rng)).to(device)
            fb = torch.from_numpy(fam[b]).to(device)
            tb = torch.from_numpy(tgt[b]).to(device)
            lf, lt = model(xb)
            loss = fam_loss(lf, fb)
            if (tb >= 0).any():
                loss = loss + 0.5 * tgt_loss(lt, tb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()

        if val is not None and len(val["family"]):
            p, tp = predict(model, val["x"], device)
            m = metrics(val["family"], p, val["target"], tp)
            history.append({"epoch": epoch, "accuracy": m["accuracy"], "macro_f1": m["macro_f1"],
                            **{f"strike_{k}": v for k, v in m["strike_detection"].items()}})
            if best is None or m["macro_f1"] > best[0]:
                best = (m["macro_f1"], epoch, {k: v.detach().clone() for k, v in model.state_dict().items()})
    if best is not None:
        model.load_state_dict(best[2])
    return model, history


@torch.no_grad()
def predict(model: ActionNet, x: np.ndarray, device: str):
    model.eval()
    fams, tgts = [], []
    for s in range(0, len(x), 256):
        xb = torch.from_numpy(centre_crop(x[s:s + 256]).copy()).to(device)
        lf, lt = model(xb)
        fams.append(lf.argmax(1).cpu().numpy())
        tgts.append(lt.argmax(1).cpu().numpy())
    empty = np.zeros(0, np.int64)
    return (np.concatenate(fams) if fams else empty), (np.concatenate(tgts) if tgts else empty)


def metrics(y: np.ndarray, p: np.ndarray, ty: np.ndarray, tp: np.ndarray) -> dict:
    n = len(CLASSES)
    cm = np.zeros((n, n), np.int64)
    np.add.at(cm, (y, p), 1)
    per_class = {}
    f1s = []
    for c, name in enumerate(CLASSES):
        support = int(cm[c].sum())
        pred = int(cm[:, c].sum())
        tp_c = int(cm[c, c])
        prec = tp_c / pred if pred else 0.0
        rec = tp_c / support if support else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[name] = {"support": support, "precision": prec, "recall": rec, "f1": f1}
        if support:
            f1s.append(f1)

    # Strike-vs-none: the detection question the pipeline actually asks.
    is_strike, pred_strike = y > 0, p > 0
    det_tp = int((is_strike & pred_strike).sum())
    det_p = det_tp / pred_strike.sum() if pred_strike.sum() else 0.0
    det_r = det_tp / is_strike.sum() if is_strike.sum() else 0.0
    # Family accuracy among true strikes the model also called a strike.
    both = is_strike & pred_strike
    fam_acc = float((y[both] == p[both]).mean()) if both.any() else None
    has_t = (ty >= 0) & is_strike
    tgt_acc = float((ty[has_t] == tp[has_t]).mean()) if has_t.any() else None
    majority = float(np.bincount(y, minlength=n).max() / len(y)) if len(y) else 0.0
    return {
        "n": int(len(y)),
        "accuracy": float((y == p).mean()) if len(y) else 0.0,
        "majority_baseline": majority,
        "macro_f1": float(np.mean(f1s)) if f1s else 0.0,
        "strike_detection": {"precision": float(det_p), "recall": float(det_r)},
        "family_accuracy_on_detected": fam_acc,
        "target_accuracy": tgt_acc,
        "per_class": per_class,
        "confusion": cm.tolist(),
    }


def _fmt_metrics(title: str, m: dict) -> list[str]:
    lines = [f"### {title}", "",
             f"- samples: {m['n']}  ·  accuracy **{m['accuracy']:.3f}** "
             f"(majority-class baseline {m['majority_baseline']:.3f})  ·  macro-F1 **{m['macro_f1']:.3f}**",
             f"- strike vs none: precision {m['strike_detection']['precision']:.3f}, "
             f"recall {m['strike_detection']['recall']:.3f}"]
    if m["family_accuracy_on_detected"] is not None:
        lines.append(f"- family accuracy on detected strikes: {m['family_accuracy_on_detected']:.3f}")
    if m["target_accuracy"] is not None:
        lines.append(f"- target (head/body/leg) accuracy: {m['target_accuracy']:.3f}")
    lines += ["", "| class | support | precision | recall | F1 |", "|---|---:|---:|---:|---:|"]
    for name, c in m["per_class"].items():
        if c["support"] or c["precision"]:
            lines.append(f"| {name} | {c['support']} | {c['precision']:.2f} | {c['recall']:.2f} | {c['f1']:.2f} |")
    lines += ["", "Confusion (rows = truth, cols = predicted): " + " ".join(CLASSES), "```"]
    lines += [f"{name:>9} " + " ".join(f"{v:5d}" for v in row) for name, row in zip(CLASSES, m["confusion"])]
    lines += ["```", ""]
    return lines


def _dataset_table(data: dict, stats: dict) -> list[str]:
    lines = ["| fight | fps | " + " | ".join(CLASSES) + " | skipped (no skeleton / class) |",
             "|---|---:|" + "---:|" * len(CLASSES) + "---|"]
    for fid, st in stats.items():
        m = data["fight_id"] == fid
        counts = np.bincount(data["family"][m], minlength=len(CLASSES))
        lines.append(f"| {fid} | {st['fps']} | " + " | ".join(str(c) for c in counts)
                     + f" | {st['skipped_no_skeleton']} / {st['skipped_class']} |")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cpu", help="cpu | mps | cuda (the model is tiny; cpu is fine)")
    ap.add_argument("--promote", action="store_true",
                    help="copy the checkpoint to action_model/weights/strike_model.pt, the one the pipeline loads")
    ap.add_argument("--no-negatives", action="store_true",
                    help="positives only: a pure strike-type classifier with no `none` class examples")
    args = ap.parse_args()

    t0 = time.time()
    db = SessionLocal()
    try:
        data, stats = build_dataset(db, TRAINING_EVENTS_SQL, seed=args.seed, negatives=not args.no_negatives)
        ref_data, ref_stats = build_dataset(db, REFERENCE_EVENTS_SQL, seed=args.seed + 1,
                                            negatives=not args.no_negatives)
    finally:
        db.close()
    print(f"dataset built in {time.time() - t0:.0f}s: {len(data['family'])} training windows, "
          f"{len(ref_data['family'])} validation windows (reference fights)")
    for fid, st in stats.items():
        print(f"  fight {fid}: {st}")

    fights = sorted(stats)
    val_fights = sorted(ref_stats)
    overlap = set(fights) & set(val_fights)
    assert not overlap, f"fights {overlap} are in both training and validation"
    if not val_fights:
        raise SystemExit("no labelled `reference` fight to validate on — upload one with purpose=reference")

    out_dir = RUNS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    model, history = train_model(data, ref_data, args.epochs, args.device, args.seed)
    best_epoch = max(history, key=lambda h: h["macro_f1"])["epoch"]
    p, tp = predict(model, ref_data["x"], args.device)
    val = metrics(ref_data["family"], p, ref_data["target"], tp)
    print(f"  best epoch {best_epoch}/{args.epochs}: validation acc={val['accuracy']:.3f} "
          f"macroF1={val['macro_f1']:.3f} strike P/R={val['strike_detection']['precision']:.2f}/"
          f"{val['strike_detection']['recall']:.2f}")

    torch.save({
        "state_dict": model.state_dict(),
        "classes": CLASSES, "targets": TARGETS,
        "config": {k: getattr(config, k) for k in dir(config) if k.isupper()},
        "in_channels": IN_CHANNELS,
        "training_fights": fights,
        "validation_fights": val_fights,
        "best_epoch": best_epoch,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
    }, out_dir / "model.pt")

    report = {"args": vars(args), "training_fights": fights, "validation_fights": val_fights,
              "best_epoch": best_epoch, "validation": val, "history": history,
              "dataset": {str(k): v for k, v in stats.items()},
              "validation_dataset": {str(k): v for k, v in ref_stats.items()}}
    md = ["# Skeleton action model — training report", "",
          f"Run `{out_dir.name}`.", "",
          "- **Train:** `purpose='training_data'` fights, `source='label'`, `kind='point'`, "
          f"`is_verified IS TRUE` — fights {fights}.",
          f"- **Validation:** `purpose='reference'` fights only — fights {val_fights}. "
          "Every hand label there is used; reference fights are ground truth and are never QA'd.",
          f"- `none` windows are sampled, not labelled (no hand label for that corner within "
          f"{config.NEG_EXCLUSION_SECS}s).",
          f"- Checkpoint = best validation macro-F1: epoch **{best_epoch}** of {args.epochs}. "
          "Selection on validation makes this score slightly optimistic.", "",
          "## Training windows", ""] + _dataset_table(data, stats) + [
          "", "## Validation windows", ""] + _dataset_table(ref_data, ref_stats) + [""]
    md += _fmt_metrics(f"Validation (epoch {best_epoch})", val)
    md += ["## Validation curve", "", "| epoch | accuracy | macro-F1 | strike P | strike R |",
           "|---:|---:|---:|---:|---:|"]
    md += [f"| {h['epoch']} | {h['accuracy']:.3f} | {h['macro_f1']:.3f} | "
           f"{h['strike_precision']:.2f} | {h['strike_recall']:.2f} |"
           for h in history if h["epoch"] % 5 == 0 or h["epoch"] == best_epoch]

    (out_dir / "report.json").write_text(json.dumps(report, indent=2))
    (out_dir / "report.md").write_text("\n".join(md))
    print(f"\nwrote {out_dir}/model.pt, report.md, report.json  ({time.time() - t0:.0f}s total)")
    if args.promote:
        from .inference import WEIGHTS_PATH
        WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out_dir / "model.pt", WEIGHTS_PATH)
        print(f"promoted to {WEIGHTS_PATH} — re-sweep STRIKE_PROB_THRESHOLD/STRIKE_NMS_SECS "
              "and re-score before committing it")


if __name__ == "__main__":
    main()
