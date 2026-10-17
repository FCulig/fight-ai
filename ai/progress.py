"""
Live progress for the pipeline's long loops.

On a terminal (deploy/worker.sh, a manual run) each loop gets a tqdm bar with
rate and ETA, and anything printed while the bar is open lands above it. When
stdout is a file (the backend's runs/upload_pipeline.log) it writes one plain
line a minute instead, since a redrawn bar would fill the log with carriage
returns.

Usage:
    with progress("Tracking", total=len(frames)) as bar:
        for frame in frames:
            bar.update()
            ...
"""

import contextlib
import sys
from datetime import datetime

from tqdm import tqdm

_FILE_INTERVAL_SECS = 60


def stamp(message: str) -> None:
    """Print a step line with the wall-clock time in front."""
    print(f"[{datetime.now():%H:%M:%S}] {message}")


@contextlib.contextmanager
def progress(desc: str, total: int | None, unit: str = "frame"):
    out = sys.stdout
    if out.isatty():
        bar = tqdm(total=total, desc=desc, unit=unit, file=out,
                   dynamic_ncols=True, smoothing=0.05)
        try:
            with contextlib.redirect_stdout(_AboveBar(out)):
                yield bar
        finally:
            bar.close()
    else:
        bar = tqdm(total=total, desc=desc, unit=unit, file=_WholeLines(out),
                   mininterval=_FILE_INTERVAL_SECS, ascii=True, ncols=100)
        try:
            yield bar
        finally:
            bar.close()


class _AboveBar:
    """Stdout while a bar is open: each printed line goes above the bar."""

    def __init__(self, out):
        self.out = out

    def write(self, s: str) -> None:
        if s.strip():
            tqdm.write(s.rstrip("\n"), file=self.out)

    def flush(self) -> None:
        self.out.flush()


class _WholeLines:
    """Turns tqdm's in-place redraws into one line per refresh."""

    def __init__(self, out):
        self.out = out

    def write(self, s: str) -> None:
        s = s.replace("\r", "").strip()
        if s:
            self.out.write(s + "\n")
            self.out.flush()

    def flush(self) -> None:
        self.out.flush()
