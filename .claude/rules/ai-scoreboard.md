---
paths:
  - "ai/video_processing/scoreboard_overlay/**"
---

# Scoreboard overlay OCR

- **Round parsing doesn't depend on the organisation.** It takes an explicit prefix ("R1", "ROUND 1") or, when the overlay shows a bare digit, uses box geometry: `find_round_digit_box()` finds the one-character box beside the timer. Calibration must union that box into the ROI, or the crop clips the digit and it can never be read.
- **The timer's colon is unreliable; its digits aren't.** `parse_timer()` falls back to a zero-padded `0M?SS` token (`0344`, `04x08`, `04408`) because on some overlays (KSW's red pill) EasyOCR never returns a usable colon. Keep the leading zero and the token boundaries: they are what stop calibration's whole-strip OCR matching years and sponsor numerals.
- **Validate an OCR change with timer coverage plus an intercept check. No labels are needed.** The clock is linear, so `k = frame/fps + seconds_remaining` is constant within a round and a misread falls off that intercept. Take the intercepts from readings the current settings already accept, then confirm newly admitted readings agree. That tests for false positives on data the change didn't tune on.
- **Never tune on EasyOCR confidence.** A ≤1px change to the calibrated ROI moves it by a median of 0.117 (max 0.433). The confidence floor also feeds back into the ROI, because calibration only unions boxes that clear it.
- `_smooth_samples()` in `extraction.py` tags backward timer jumps `parse_error="timer_smoothed_out"`. Segmentation reads runs of that tag as replays, so don't repurpose it.
- No `eval score` section covers OCR, so don't ask for a `score` delta here.
