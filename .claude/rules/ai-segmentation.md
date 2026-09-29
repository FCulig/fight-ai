---
paths:
  - "ai/video_processing/fight_segmentation.py"
  - "ai/video_processing/round_clock.py"
  - "ai/eval/sanity.py"
---

# Round segmentation (`segment_fights`)

## The signals rank by authority; they are not peers
Inverting this order is what made round counts unreliable.
1. **Scoreboard clock** (`round_clock.derive_rounds_from_clock`) decides the round **count** and **identity**. The slope is known in advance (`-1/fps`), so only the intercept is fitted, by median. That makes it robust from about 3 readings anywhere in a round, which matters because overlays disappear during replays and close-ups.
2. **Round number** corroborates the clock and pins boundaries. Nothing may *depend* on it, since many overlays show a bare digit or none at all.
3. **Fighter presence and engagement** refine the edges the clock couldn't pin, and are the only signal when OCR fails.

## Rules
- **Detection alone can't decide a round count.** It splits at every ground scramble or camera cutaway. When it is the only signal, `enforce_round_plausibility()` applies these rules:
  - Only the **last** round may be short. A short non-final segment is *dropped*, not merged, because merging drags the real start back across the walkout.
  - A gap below `MIN_ROUND_BREAK_SECS` is a dropout, so the halves are rejoined.
  - The video must be long enough to hold the rounds claimed.
- **Trust edges only where they were observed.** `ClockRound.start_anchored`/`end_anchored` record whether a reading was actually seen near the round's start or near 0:00. A knockout never reaches 0:00. `_reconcile_with_clock` takes unanchored edges from detection.
- **The result carries its own verdict.** `quality.needs_review`/`review_reason` are keyed on how many mutually consistent readings back each round (`ROUND_CLOCK_HEALTHY_SUPPORT`), not on raw OCR coverage. `pipeline.py` persists them through `database.set_segmentation_review`, and Annotate shows a banner. A detection-only guess must never reach the DB looking verified.
- **Mid-round replays:** `detect_replay_ranges()` treats `MIN_REPLAY_SAMPLES` consecutive `timer_smoothed_out` readings as a replay and returns them as `excluded_ranges`, which `process_fight` skips. It returns `[]` when OCR doesn't calibrate.
- `eval/sanity.py` re-checks the same physical rules label-free, so a regression shows up in `sanity`.
- To validate a change, see "Measure before you change a threshold" in `ai/CLAUDE.md`. Round IoU is circular until a person has moved the labels.
