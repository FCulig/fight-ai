"""
Org-agnostic parsing of round number and timer from OCR output.

Two independent routes to the round number, tried in order:

1. **Text prefix** (`parse_round`) — an explicit "R1" / "ROUND 1" / "RUNDA 1"
   token. Unambiguous when present, but many broadcasts don't render one.
2. **Box geometry** (`parse_round_from_boxes`) — the round is a bare digit in
   its own box beside the timer, e.g. "NAZHAND | 1 | 03:50 | STAROPOLI". Found
   by position relative to the timer box rather than by any text pattern, so it
   needs no per-organisation configuration.

Route 2 exists because route 1 cannot read a bare digit, and a bare digit is
what a large share of regional MMA overlays actually show. Route 2 is also
strictly safer than "accept any digit in the ROI": mat logos, sponsor banners
and fighter records routinely put stray numerals inside the crop, and only the
positional constraint rejects them.

To add support for a new organisation's *prefixed* format, append one entry to
ROUND_PATTERNS. Patterns are tried in order; the first match wins.
"""

import re
from typing import Optional, Sequence

from models.constants import (
    ROUND_BOX_MAX_HORIZONTAL_GAP_RATIO,
    ROUND_BOX_MAX_VERTICAL_OFFSET_RATIO,
)

# Tried in order — first match wins. All matched against upper-cased text.
#
# The leading \b matters: without it "R\s*([1-5])" matches the tail of any word
# ending in R followed by a numeral — "SUPER 5", "FIGHTER 2 GYM" — and the ROI
# routinely contains exactly that kind of sponsor/gym text.
ROUND_PATTERNS: list[str] = [
    r"\bR\s*([1-5])\b",
    r"\bROUND\s*([1-5])\b",
    r"\bRD\s*([1-5])\b",
    r"\bRUNDA\s*([1-5])\b",  # Polish (KSW)
    r"\bR-([1-5])\b",
]

# Universal MM:SS or M:SS timer.
#
# The separator class is deliberately wider than ":". At the small glyph sizes a
# broadcast timer occupies in a scoreboard crop, OCR routinely returns the colon
# as "." or ";" — on some overlays more often than not, and on clean, unambiguous
# digits at 0.9+ confidence. Matching only ":" throws those readings away, and
# because the timer is the authoritative round signal, losing them silently
# demotes the whole video to detection-only segmentation.
#
# Widening here is safe: the seconds/minutes range check below rejects the
# decimals this also lets through ("3.85", "12.99" — seconds > 59), and callers
# only ever apply it to a tight scoreboard ROI, not to arbitrary frame text.
TIMER_PATTERN: str = r"\b(\d{1,2})[:.;](\d{2})\b"

# A box holding nothing but a round digit, allowing for OCR noise around it
# ("1", "|1|", "[1]").
_BARE_ROUND_DIGIT = re.compile(r"^[^0-9A-Za-z]*([1-5])[^0-9A-Za-z]*$")


def parse_round(text: str) -> Optional[int]:
    """
    Return the round number (1–5) found in *text* via an explicit prefix, or None.

    >>> parse_round("R1 4:32 BLUE 0 RED 0")
    1
    >>> parse_round("ROUND 3")
    3
    >>> parse_round("SUPER 5 ENERGY")
    >>> parse_round("no match here")
    """
    upper = text.upper()
    for pattern in ROUND_PATTERNS:
        m = re.search(pattern, upper)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 5:
                return val
    return None


def parse_timer(text: str) -> Optional[int]:
    """
    Return the clock reading as total seconds, or None if not found.

    Accepts MM:SS or M:SS (e.g. "4:32" → 272, "0:07" → 7), including the "."
    and ";" separators OCR substitutes for the colon.
    Rejects obviously invalid values (seconds > 59, minutes > 59).

    >>> parse_timer("R1 4:32")
    272
    >>> parse_timer("0:07")
    7
    >>> parse_timer("1 01.23")
    83
    >>> parse_timer("PURSE 3.85M")
    >>> parse_timer("no clock here")
    """
    m = re.search(TIMER_PATTERN, text)
    if not m:
        return None
    minutes, seconds = int(m.group(1)), int(m.group(2))
    if seconds > 59 or minutes > 59:
        return None
    return minutes * 60 + seconds


def box_aabb(bbox: Sequence) -> tuple[float, float, float, float]:
    """Axis-aligned bounds (x1, y1, x2, y2) of an EasyOCR 4-point polygon."""
    xs = [float(p[0]) for p in bbox]
    ys = [float(p[1]) for p in bbox]
    return min(xs), min(ys), max(xs), max(ys)


def find_round_digit_box(
    boxes: Sequence[tuple],
    min_confidence: float = 0.0,
) -> Optional[tuple[tuple[float, float, float, float], int]]:
    """
    Locate the bare round digit by its position relative to the timer box.

    Returns ((x1, y1, x2, y2), round_number) or None.

    Accepts a single-digit box that sits on the same horizontal band as the
    timer and within a short reach of it. Both tolerances are expressed relative
    to the timer box's own dimensions, so they hold at any resolution and under
    any crop upscale without retuning.

    The box is returned, not just the value, because ROI calibration has to
    *widen* the crop to include the digit — on a typical overlay it sits outside
    a timer-only ROI, and a crop that clips it makes the round number
    permanently unreadable downstream.
    """
    usable = [
        (box_aabb(bbox), str(text), float(conf))
        for (bbox, text, conf) in boxes
        if float(conf) >= min_confidence
    ]
    timers = [(aabb, conf) for aabb, text, conf in usable if parse_timer(text) is not None]
    if not timers:
        return None

    (tx1, ty1, tx2, ty2), _ = max(timers, key=lambda item: item[1])
    timer_w = tx2 - tx1
    timer_h = ty2 - ty1
    if timer_w <= 0 or timer_h <= 0:
        return None

    timer_cy = (ty1 + ty2) / 2
    max_dy   = ROUND_BOX_MAX_VERTICAL_OFFSET_RATIO * timer_h
    max_gap  = ROUND_BOX_MAX_HORIZONTAL_GAP_RATIO * timer_w

    best: Optional[tuple[float, tuple[float, float, float, float], int]] = None
    for aabb, text, _conf in usable:
        m = _BARE_ROUND_DIGIT.match(text.strip())
        if not m:
            continue
        x1, y1, x2, y2 = aabb
        if abs((y1 + y2) / 2 - timer_cy) > max_dy:
            continue
        # Horizontal gap between the two boxes' facing edges (0 when they overlap).
        gap = max(0.0, max(tx1 - x2, x1 - tx2))
        if gap > max_gap:
            continue
        if best is None or gap < best[0]:
            best = (gap, aabb, int(m.group(1)))

    return (best[1], best[2]) if best else None


def parse_round_from_boxes(
    boxes: Sequence[tuple],
    min_confidence: float = 0.0,
) -> Optional[int]:
    """
    Return the round number read from OCR output, or None.

    Args:
        boxes:          EasyOCR readtext() output — a sequence of
                        (bbox, text, confidence) triples, in ROI coordinates.
        min_confidence: Confidence floor applied to every box considered.

    Tries the explicit-prefix parse on each box's own text first, since an "R1"
    token is unambiguous where present, then falls back to box geometry. The
    prefix parse runs per box rather than on joined text, which would otherwise
    manufacture adjacencies that were never on screen.
    """
    usable = [
        (str(text), float(conf))
        for (_bbox, text, conf) in boxes
        if float(conf) >= min_confidence
    ]
    for text, _conf in usable:
        found = parse_round(text)
        if found is not None:
            return found

    hit = find_round_digit_box(boxes, min_confidence)
    return hit[1] if hit else None
