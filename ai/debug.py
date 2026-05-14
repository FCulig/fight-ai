"""
Centralised debug context for the fight-ai pipeline.

Every pipeline step that produces diagnostic output accepts an optional
DebugContext. All writes are routed through it, so disabling debug is a
single flag change rather than scattered conditionals.

Usage:
    ctx = DebugContext("runs/my_run", verbose=True)
    sub = ctx.subdir("calibration")   # runs/my_run/calibration/
    sub.save_image("heatmap.png", arr)
    sub.save_json("data.json", obj)
    sub.log("step", "found 3 candidates")
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class DebugContext:
    def __init__(self, root: str | Path, verbose: bool = True):
        self.root = Path(root)
        self.verbose = verbose
        self._timings: dict[str, float] = {}
        if verbose:
            self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def disabled(cls) -> "DebugContext":
        return cls("_disabled", verbose=False)

    def subdir(self, name: str) -> "DebugContext":
        """Return a DebugContext rooted at <root>/<name>/."""
        child = DebugContext(self.root / name, self.verbose)
        return child

    # ------------------------------------------------------------------
    # Path helper
    # ------------------------------------------------------------------

    def path(self, filename: str) -> Path:
        return self.root / filename

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def save_image(
        self,
        filename: str,
        image: np.ndarray,
        label: Optional[str] = None,
    ) -> Optional[Path]:
        """Write an OpenCV image (grayscale or BGR). Returns path or None."""
        if not self.verbose:
            return None
        out = self.root / filename
        img = image.copy()
        if img.ndim == 2:                          # grayscale → BGR so putText works
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if label is not None:
            cv2.putText(img, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.9, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.imwrite(str(out), img)
        return out

    def save_json(self, filename: str, data, indent: int = 2) -> Optional[Path]:
        if not self.verbose:
            return None
        out = self.root / filename
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)
        return out

    def log(self, step: str, message: str) -> None:
        line = f"[{datetime.now().strftime('%H:%M:%S')}] [{step}] {message}"
        print(line)
        if self.verbose:
            with open(self.root / "debug.log", "a", encoding="utf-8") as f:
                f.write(line + "\n")

    # ------------------------------------------------------------------
    # Timing helpers
    # ------------------------------------------------------------------

    def start_timer(self, key: str) -> None:
        self._timings[key] = time.perf_counter()

    def stop_timer(self, key: str) -> float:
        elapsed = time.perf_counter() - self._timings.pop(key, time.perf_counter())
        self.log("timer", f"{key} took {elapsed:.2f}s")
        return elapsed
