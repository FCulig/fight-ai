from .calibration import calibrate_scoreboard_overlay, load_roi, save_roi
from .extraction import extract_scoreboard_samples, load_samples
from .scoreboard_verification import build_verification_video


def parse_roi_override(roi_str: str) -> tuple[int, int, int, int]:
    """
    Parse a CLI '--scoreboard-roi x,y,w,h' string into a 4-int tuple.
    Raises ValueError with a human-readable message on bad input.
    """
    parts = roi_str.split(",")
    if len(parts) != 4:
        raise ValueError(
            f"--scoreboard-roi must be four comma-separated integers (x,y,w,h), got: {roi_str!r}"
        )
    try:
        return tuple(int(p.strip()) for p in parts)  # type: ignore[return-value]
    except ValueError:
        raise ValueError(
            f"--scoreboard-roi values must all be integers, got: {roi_str!r}"
        )


__all__ = [
    "calibrate_scoreboard_overlay",
    "load_roi",
    "save_roi",
    "extract_scoreboard_samples",
    "load_samples",
    "build_verification_video",
    "parse_roi_override",
]
