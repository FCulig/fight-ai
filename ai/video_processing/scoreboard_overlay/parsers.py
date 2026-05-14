"""
Org-agnostic regexes for parsing round number and timer from OCR text.

To add support for a new organisation, append one entry to ROUND_PATTERNS.
Patterns are tried in order; the first match wins.
"""

import re
from typing import Optional

# Tried in order — first match wins. All matched against upper-cased text.
ROUND_PATTERNS: list[str] = [
    r"R\s*([1-5])\b",
    r"ROUND\s*([1-5])\b",
    r"RD\s*([1-5])\b",
    r"RUNDA\s*([1-5])\b",  # Polish (KSW)
    r"R-([1-5])\b",
]

# Universal MM:SS or M:SS timer
TIMER_PATTERN: str = r"\b(\d{1,2}):(\d{2})\b"


def parse_round(text: str) -> Optional[int]:
    """
    Return the round number (1–5) found in *text*, or None.

    >>> parse_round("R1 4:32 BLUE 0 RED 0")
    1
    >>> parse_round("ROUND 3")
    3
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

    Accepts MM:SS or M:SS (e.g. "4:32" → 272, "0:07" → 7).
    Rejects obviously invalid values (seconds > 59, minutes > 59).

    >>> parse_timer("R1 4:32")
    272
    >>> parse_timer("0:07")
    7
    >>> parse_timer("no clock here")
    """
    m = re.search(TIMER_PATTERN, text)
    if not m:
        return None
    minutes, seconds = int(m.group(1)), int(m.group(2))
    if seconds > 59 or minutes > 59:
        return None
    return minutes * 60 + seconds
