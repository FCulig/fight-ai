"""Label-free check that `fighter_frames.corner` matches the visible kit colour.

Corner assignment is the one pipeline output with a 50% failure mode: get the
red/blue mapping backwards and every downstream event is attributed to the wrong
fighter, while everything stays perfectly self-consistent and therefore invisible.
Nothing else in eval/ catches that — `sanity.py` checks structure, `score.py`
needs labels, and labels themselves inherit the error.

This needs no labels. It samples frames, reads each fighter's shorts band, and
asks whether the fighter stored as `corner = 0` is the one wearing red. Only
frames where one fighter reads decisively red and the other decisively blue are
scored, so a marginal colour call never counts as evidence either way.

Measured with this module (`corner` as stored, before → after the corner
assignment fixes):

    fight 31  JURICvsNOGUEIRA        100% →  100%   (17 decisive frames)
    fight 42  MILIDRAGOVICvsMOOSMAN    1% →   93%   (86 decisive frames)
    fight 44  NAZHANDvsSTAROPOLI      65% →   95%  (219 decisive frames)

Usage:
    python -m eval.corner_accuracy <fight_id> [--stride N]
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import cv2
from sqlalchemy import text

from database import SessionLocal

# Shorts band as a fraction of bbox height. Below the torso (which is bare skin
# or a rash guard) and above the knees, so it lands on the trunks — the largest
# reliably corner-coloured surface on a fighter.
_BAND_TOP    = 0.42
_BAND_BOTTOM = 0.72

# Deliberately stricter than the pipeline's own sampler: this is the referee,
# so it must only speak when the colour is unambiguous.
_MIN_SATURATION   = 140
_MIN_VALUE        = 70
_RED_HUE_HIGH     = 8
_RED_HUE_LOW2     = 172
_BLUE_HUE_LOW     = 100
_BLUE_HUE_HIGH    = 132
_MIN_COLOUR_PX    = 400   # below this the band is too small/occluded to read
_MIN_DECISIVENESS = 0.6   # |red-blue| / (red+blue) needed to call a colour


@dataclass
class CornerAccuracy:
    fight_id: int
    decisive_frames: int
    correct: int
    runs: list = field(default_factory=list)  # (start_frame, end_frame, ok, n)

    @property
    def accuracy(self) -> Optional[float]:
        if not self.decisive_frames:
            return None
        return self.correct / self.decisive_frames


def _colour_vote(img, box) -> Optional[int]:
    """+1 decisively red, -1 decisively blue, None not decisive."""
    x1, y1, x2, y2 = box
    h = y2 - y1
    a = max(0, int(y1 + _BAND_TOP * h))
    b = min(img.shape[0], int(y1 + _BAND_BOTTOM * h))
    X1, X2 = max(0, int(x1)), min(img.shape[1], int(x2))
    if b <= a or X2 <= X1:
        return None
    patch = img[a:b, X1:X2]
    if patch.size == 0:
        return None

    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    quality = (sat >= _MIN_SATURATION) & (val >= _MIN_VALUE)
    red = int((((hue <= _RED_HUE_HIGH) | (hue >= _RED_HUE_LOW2)) & quality).sum())
    blue = int((((hue >= _BLUE_HUE_LOW) & (hue <= _BLUE_HUE_HIGH)) & quality).sum())

    if red + blue < _MIN_COLOUR_PX:
        return None
    if abs(red - blue) / (red + blue) < _MIN_DECISIVENESS:
        return None
    return 1 if red > blue else -1


def measure(fight_id: int, stride: int = 15) -> CornerAccuracy:
    db = SessionLocal()
    try:
        video_path = db.execute(
            text("SELECT video_path FROM fights WHERE id = :f"), {"f": fight_id}
        ).scalar()
        if video_path is None:
            raise ValueError(f"no fight with id {fight_id}")
        rows = db.execute(
            text("SELECT frame, corner, x1, y1, x2, y2 FROM fighter_frames "
                 "WHERE fight_id = :f AND mod(frame, :s) = 0 ORDER BY frame"),
            {"f": fight_id, "s": stride},
        ).fetchall()
    finally:
        db.close()

    by_frame = defaultdict(list)
    for frame, corner, x1, y1, x2, y2 in rows:
        by_frame[frame].append((corner, (x1, y1, x2, y2)))

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    seq: list[tuple[int, bool]] = []
    for frame in sorted(by_frame):
        dets = by_frame[frame]
        # Need exactly one red-labelled and one blue-labelled box to compare.
        if len(dets) != 2 or {dets[0][0], dets[1][0]} != {0, 1}:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame - 1)   # frames are 1-based
        ok, img = cap.read()
        if not ok:
            continue
        votes = {corner: _colour_vote(img, box) for corner, box in dets}
        if votes[0] is None or votes[1] is None or votes[0] == votes[1]:
            continue
        seq.append((frame, votes[0] == 1))   # corner 0 should be the red fighter
    cap.release()

    runs: list = []
    for frame, ok in seq:
        if runs and runs[-1][2] == ok:
            runs[-1][1] = frame
            runs[-1][3] += 1
        else:
            runs.append([frame, frame, ok, 1])

    return CornerAccuracy(
        fight_id=fight_id,
        decisive_frames=len(seq),
        correct=sum(1 for _, ok in seq if ok),
        runs=runs,
    )


def format_accuracy(r: CornerAccuracy, min_run: int = 3) -> str:
    L = [f"\n{'=' * 70}", f"CORNER ACCURACY   fight {r.fight_id}", "=" * 70]
    if r.accuracy is None:
        L.append("  no decisive frames — kit colours never read unambiguously.")
        L.append("  This is NOT a pass: corner assignment is unverified here.")
        L.append("")
        return "\n".join(L)

    L.append(f"  {r.decisive_frames} decisive frames, {r.accuracy:.0%} correct")
    for start, end, ok, n in r.runs:
        if n >= min_run:
            L.append(f"      {start:6d}-{end:6d} ({n:3d})  "
                     f"{'OK' if ok else 'FLIPPED'}")
    if r.accuracy < 0.5:
        L.append("  [FAIL] mostly inverted — the whole-fight mapping is backwards.")
    elif r.accuracy < 0.9:
        L.append("  [WARN] intermittent — tracker identity swaps the appearance")
        L.append("         path did not correct. Check the FLIPPED runs above.")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fight_id", type=int)
    ap.add_argument("--stride", type=int, default=15,
                    help="sample every Nth frame (default 15)")
    args = ap.parse_args()
    print(format_accuracy(measure(args.fight_id, stride=args.stride)))
