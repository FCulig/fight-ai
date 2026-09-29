---
paths:
  - "ai/video_processing/corner_assignment/**"
  - "ai/eval/corner_accuracy.py"
---

# Corner assignment (`assign_corners`)

Per-frame, appearance-anchored re-ID that maps tracker slots to red=0 and blue=1.
- **Pass 1** reads the video once. It builds a descriptor for each detection (glove tape `net_red`/`tape_total` plus a torso HSV hue histogram), finds *clean frames*, and bootstraps a template for each corner from those frames.
- **Pass 2** reuses the cached descriptors, with no second video read. It assigns each detection by normalised tape plus Bhattacharyya histogram distance, through a hysteresis gate (`CORNER_SWAP_CONFIRM_SECS`, converted to frames with the video's fps).
- **Fallback:** when template separation is below `CORNER_TEMPLATE_MIN_SEPARATION`, it uses a whole-fight paired tape vote. If even that lacks evidence, the mapping stays identity and is logged as **unverified**. The two corners stay distinct and consistent, but may be the wrong way round.

## Verify with `python -m eval.corner_accuracy <fight_id>`
A whole-fight inversion is fully self-consistent, so nothing else catches it: `sanity` checks structure, `score` needs labels, and hand labels inherit the error. Run it on the fights you care about before and after a change. The `check-processed-fight` skill explains how to read its output.

## Invariants (don't relax any without re-measuring)
- **Colour is only ever read relatively**, because the red HSV band overlaps skin:
  - Size the wrist crop to the glove (`TAPE_PATCH_RATIO`) and gate it at `TAPE_MIN_SATURATION`, above the skin band.
  - Convert counts to coverage fractions of each crop. Never sum raw pixels across the fight: a sum ranks fighters by close-up time, which inverted `MILIDRAGOVICvsMOOSMAN` for its whole length.
  - Compare the two fighters **within one frame**, since they share lighting and skin tone. Each frame gets one vote.
- **`_is_clean_frame` uses `STRIKING_CORE_KEYPOINT_INDICES`**, not all 15 joints. Broadcast cameras hide knees and ankles, and the strict set found zero clean frames in 18,518 frames of `NAZHANDvsSTAROPOLI`, so no swap was ever corrected.
- **The slot→corner mapping is a bijection.** Hysteresis must commit both slots' flips together, and Pass 2 must also relabel detections that had no descriptor. Either bug produces duplicate corner ids (fight 31 has 755 such frames). The step ends with `Invariant OK: no duplicate corner ids`. A `WARNING` there blocks a release.
