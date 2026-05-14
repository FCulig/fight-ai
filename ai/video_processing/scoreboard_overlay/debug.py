"""
Visualisation helpers for the scoreboard overlay pipeline.

All public functions are no-ops when the path argument is None, so callers
can simply pass `ctx.path("x.png") if ctx.verbose else None` without extra
conditionals.
"""

from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")          # headless — no display required
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Heatmap / mask helpers
# ---------------------------------------------------------------------------

def save_heatmap(array: np.ndarray, path: Optional[Path], title: str = "") -> None:
    """Normalise *array* and write it as a JET-colourmap PNG."""
    if path is None:
        return
    norm = cv2.normalize(
        array.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX
    ).astype(np.uint8)
    colored = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
    if title:
        cv2.putText(colored, title, (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.imwrite(str(path), colored)


# ---------------------------------------------------------------------------
# ROI drawing helpers
# ---------------------------------------------------------------------------

def draw_roi(
    frame: np.ndarray,
    roi: dict,
    color: tuple = (0, 0, 255),
    label: str = "",
) -> np.ndarray:
    """Return a copy of *frame* with the ROI rectangle drawn on it."""
    out = frame.copy()
    x, y, w, h = roi["x"], roi["y"], roi["w"], roi["h"]
    cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
    if label:
        cv2.putText(
            out, label, (x, max(0, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA,
        )
    return out


def save_annotated_roi(
    frame: np.ndarray,
    candidates: list[dict],
    selected_idx: Optional[int],
    path: Optional[Path],
) -> None:
    """
    Draw every candidate ROI on *frame*, highlighting the selected one.
    Rejected candidates are drawn in orange; the winner in green.
    """
    if path is None:
        return
    out = frame.copy()
    for i, cand in enumerate(candidates):
        if i == selected_idx:
            color = (0, 255, 0)
            lbl   = f"SELECTED #{i} score={cand.get('score', 0):.2f}"
        else:
            color = (0, 165, 255)
            lbl   = f"#{i} score={cand.get('score', 0):.2f}"
        out = draw_roi(out, cand["roi"], color=color, label=lbl)
    cv2.imwrite(str(path), out)


# ---------------------------------------------------------------------------
# OCR crop debug
# ---------------------------------------------------------------------------

def save_crop_pair(
    raw_crop: np.ndarray,
    preprocessed_crop: np.ndarray,
    path_prefix: Optional[Path],
) -> None:
    """Write <prefix>_raw.jpg and <prefix>_preprocessed.jpg."""
    if path_prefix is None:
        return
    cv2.imwrite(str(path_prefix) + "_raw.jpg", raw_crop)
    pre = preprocessed_crop
    if pre.ndim == 2:
        pre = cv2.cvtColor(pre, cv2.COLOR_GRAY2BGR)
    cv2.imwrite(str(path_prefix) + "_preprocessed.jpg", pre)


# ---------------------------------------------------------------------------
# Timer series plot
# ---------------------------------------------------------------------------

def plot_timer_series(samples: list[dict], path: Optional[Path]) -> None:
    """
    Three-panel matplotlib chart:
      - Parsed timer (seconds remaining) coloured by round
      - Parsed round number over time
      - OCR confidence with 0.7 threshold line
    """
    if path is None or not samples:
        return

    frames  = [s["frame"]                  for s in samples]
    timers  = [s.get("seconds_remaining")  for s in samples]
    rounds  = [s.get("round_num")          for s in samples]
    confs   = [s.get("conf", 0.0)          for s in samples]

    round_nums = sorted({r for r in rounds if r is not None})
    palette    = plt.cm.tab10(np.linspace(0, 1, max(len(round_nums), 1)))
    color_map  = {r: palette[i] for i, r in enumerate(round_nums)}

    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    fig.suptitle("Scoreboard overlay — OCR signal series", fontsize=13)

    # Panel 1 — timer
    ax = axes[0]
    ax.set_ylabel("Seconds remaining")
    ax.set_ylim(-5, 320)
    for i in range(len(frames) - 1):
        t0, t1 = timers[i], timers[i + 1]
        r0, r1 = rounds[i], rounds[i + 1]
        if t0 is not None and t1 is not None and r0 == r1:
            ax.plot([frames[i], frames[i + 1]], [t0, t1],
                    color=color_map.get(r0, "grey"), linewidth=1.5)
        elif t0 is not None:
            ax.scatter([frames[i]], [t0],
                       color=color_map.get(r0, "grey"), s=12, zorder=5)
    # Legend
    for r in round_nums:
        ax.plot([], [], color=color_map[r], label=f"Round {r}", linewidth=2)
    ax.legend(fontsize=8, loc="upper right")

    # Panel 2 — round number
    ax2 = axes[1]
    ax2.set_ylabel("Round")
    ax2.set_yticks([1, 2, 3, 4, 5])
    ax2.set_ylim(0.5, 5.5)
    valid_r = [(f, r) for f, r in zip(frames, rounds) if r is not None]
    if valid_r:
        fs, rs = zip(*valid_r)
        ax2.scatter(fs, rs,
                    c=[color_map.get(r, "grey") for r in rs],
                    s=12, zorder=5)

    # Panel 3 — confidence
    ax3 = axes[2]
    ax3.set_ylabel("OCR confidence")
    ax3.set_xlabel("Frame number")
    ax3.set_ylim(-0.05, 1.05)
    ax3.axhline(0.7, color="red", linestyle="--", linewidth=0.8,
                label="min threshold (0.7)")
    for f, c, r in zip(frames, confs, rounds):
        col = color_map.get(r, "lightgrey") if r is not None else "lightgrey"
        ax3.scatter([f], [c], color=col, s=10, zorder=5)
    ax3.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig(str(path), dpi=150)
    plt.close(fig)
