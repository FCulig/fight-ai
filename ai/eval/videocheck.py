"""Source-video integrity checks.

Every metric in this harness — and every threshold in `models/constants.py` —
is only as trustworthy as the footage it was derived from. A truncated or
partially-corrupt download still opens fine in OpenCV and still reports a full
duration from its container header; it simply stops decoding partway through and
emits garbage frames around the break. Nothing downstream notices.

`BATURvsSTAMATOVIC.mp4` is exactly this case: the container advertises 24712
frames (8.2 min) and the decoder yields 8147 (2.7 min) before the H.264 stream
fails. The pipeline processed the first third of a fight and reported success.

Run this before trusting any number computed from a video.
"""

from dataclasses import dataclass
from pathlib import Path

import cv2

# Container-vs-decoder frame-count disagreement above this fraction is treated
# as truncation rather than the usual off-by-a-few from index rounding.
FRAME_COUNT_TOLERANCE = 0.01


@dataclass
class VideoReport:
    path: str
    fps: float
    width: int
    height: int
    reported_frames: int
    decoded_frames: int

    @property
    def missing_frames(self) -> int:
        return max(0, self.reported_frames - self.decoded_frames)

    @property
    def missing_ratio(self) -> float:
        return self.missing_frames / self.reported_frames if self.reported_frames else 0.0

    @property
    def truncated(self) -> bool:
        return self.missing_ratio > FRAME_COUNT_TOLERANCE

    @property
    def reported_secs(self) -> float:
        return self.reported_frames / self.fps if self.fps else 0.0

    @property
    def decoded_secs(self) -> float:
        return self.decoded_frames / self.fps if self.fps else 0.0


def check_video(path: str | Path) -> VideoReport:
    """Decode the whole file and compare against the container's frame count.

    Full decode is the only reliable test — the container header is exactly the
    thing that lies about a truncated file. Costs roughly real-time/10.
    """
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {path}")

    rep = VideoReport(
        path=str(path),
        fps=cap.get(cv2.CAP_PROP_FPS),
        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        reported_frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        decoded_frames=0,
    )

    while True:
        ok, _ = cap.read()
        if not ok:
            break
        rep.decoded_frames += 1
    cap.release()

    return rep


def format_video_report(r: VideoReport) -> str:
    L: list[str] = []
    add = L.append

    add(f"\n{'=' * 70}")
    add(f"VIDEO INTEGRITY  {Path(r.path).name}")
    add("=" * 70)
    add(f"  {r.width}x{r.height} @ {r.fps:.2f} fps")
    add(f"  container reports {r.reported_frames:>7d} frames  "
        f"({r.reported_secs / 60:.1f} min)")
    add(f"  decoder yields    {r.decoded_frames:>7d} frames  "
        f"({r.decoded_secs / 60:.1f} min)")

    if r.truncated:
        add("")
        add(f"  [FAIL] TRUNCATED — {r.missing_frames} frames "
            f"({r.missing_ratio:.0%}) never decode.")
        add("         The file is an incomplete download. The pipeline will")
        add("         silently process only the decodable prefix and report")
        add("         success, and frames near the break are visually corrupt")
        add("         (the pose model hallucinates keypoints on them).")
        add("         Re-download before trusting any metric from this video.")
    else:
        add("")
        add("  [PASS] decodes fully")

    add("")
    return "\n".join(L)
