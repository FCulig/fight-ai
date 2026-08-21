[← Back to plan index](../PLAN.md)

**Depends on:** [Prerequisite P1–P3](01-prerequisite.md) for steps 1–5 & 7 (label-free). Steps [6](#st1-6) & [8](#st1-8) additionally depend on [Stage 0](02-stage0-labelling.md) completing (labelled set must exist).
**Blocks:** [P4](01-prerequisite.md#p4) waits on nothing here directly, but its scored comparison is only meaningful once these land.

---

## Stage 1 — Fix the artifacts

Ordered by confidence × impact. Re-run `eval.cli sanity` after each; it needs no
labels, so **steps 1–5 and 7 are verifiable before labelling finishes**.

**Steps 6 and 8 are not.** Step 8 sweeps against the labelled set by definition,
and step 6 is explicitly bound to it ("do both together — the fix alone makes
results worse until the thresholds move"). Both therefore block on
[Stage 0](02-stage0-labelling.md) completing. Sequence the label-free steps first
and treat 6 + 8 as a single unit after labelling, rather than reading this stage
as uniformly label-free.

| Step | What | Needs labels? | Status |
|---|---|---|---|
| [1](#st1-1) | Pose→detection assignment has no mutual exclusion | no | ✅ DONE |
| [2](#st1-2) | Geometry primitives ignore keypoint confidence | no | ✅ DONE |
| [3](#st1-3) | Events are not gated to rounds | no | ✅ DONE |
| [4](#st1-4) | Absolute-pixel thresholds on a zoom-varying 2D projection | no | ✅ DONE |
| [5](#st1-5) | "fps-invariant" constants that are raw frame counts | no | ✅ DONE |
| [6](#st1-6) | Velocity is not velocity | **yes** — after Stage 0 | ⏳ BLOCKED — needs labels |
| [7](#st1-7) | State machine has no real temporal smoothing | no | ✅ DONE |
| [8](#st1-8) | Threshold sweep (`eval/sweep.py`) | **yes** — after Stage 0 | ⏳ BLOCKED — needs labels |

**Verified against a real run (not just unit-level):** re-running the full
pipeline on `JURICvsNOGUEIRA.mp4` after steps 1–5,7 flips `no simultaneous
mutual strikes` and `no duplicate events` from FAIL to PASS. It also
surfaced that most of the baseline's grappling/strike volume was itself an
artifact of the step-1 bug (shared skeletons reading as zero torso
distance) — see the "Stage 1 finding" section in
[ai/eval/README.md](../ai/eval/README.md) and
`ai/eval/baselines/JURICvsNOGUEIRA-stage1-partial.json`. `DISTANCE_GRAPPLING_RATIO`
and friends are placeholder-calibrated (preserving the old absolute-pixel
threshold's apparent behaviour) pending step 8's real sweep — do not
hand-tune further by eyeballing one video.

<a id="st1-1"></a>
### 1. Pose→detection assignment has no mutual exclusion ← start here ✅ DONE
**`video_processing/pose_tracking/pose_tracking.py:93-105`**

Pose runs on **full frames**, then each fighter box greedily takes its argmax-IoU
pose box with a floor of `IOU_MATCH_THRESHOLD = 0.1`. Nothing stops red and blue
being assigned *the same skeleton* — and overlapping boxes is exactly the clinch
case. When `red_kp == blue_kp`: torso distance is 0 (→ grappling state), each
wrist is by definition at the other's head (→ contact gate passes trivially),
velocities are identical (→ both pass). This single bug produces the 64%
mutual-strike signature and much of the state flapping.

**Fix:** reuse the pattern that already exists in this repo —
`models/FighterTracker.py:126-187` builds a cost matrix and solves it with
`scipy.optimize.linear_sum_assignment`. Do the same for fighter-box → pose-box,
and raise the IoU floor to ~0.5. One skeleton per fighter, structurally.

(Moving pose to fighter crops would make this bug impossible and is worth
evaluating after the Hungarian fix is measured; it is the larger change.
`ai/CLAUDE.md` already documents both the full-frame behaviour and the missing
mutual-exclusion constraint, so it needs no correction here — only the removal of
the "currently fails" note once the sanity check passes.)

*Expect:* sanity `no simultaneous mutual strikes` FAIL (64%) → PASS.

<a id="st1-2"></a>
### 2. Geometry primitives ignore keypoint confidence ✅ DONE
**`models/geometry.py`** (all three functions) and
**`fight_processing/fight_processing_util.py:220`** (`is_fighter_grounded`)

`get_torso_rectangle` and `get_fighter_scale` read keypoints 5/6/11/12 with **no
confidence check**, while everything around them gates on
`KEYPOINT_MIN_CONFIDENCE`. `get_fighter_scale` is the denominator of *every*
normalised threshold in the system, so one hallucinated hip silently rescales
the whole strike detector for that frame.

Worse, `is_fighter_grounded` reads nose + ankles (0/15/16) ungated. Ankles are
occluded in most standing-clinch frames → hallucinated near the hips →
`span_ratio` collapses below `GROUND_VERTICAL_SPAN_RATIO` → **reads GROUNDED
while standing.** That is the CLINCH↔GROUND flapping.

**Fix:** gate all three on confidence and return `None` when there is not enough
signal; callers treat `None` as "unusable this frame" instead of computing on
garbage. Drop the vertical-span signal when ankles are unconfident and fall back
to torso tilt alone.

⚠️ **Do not assume the `None` path is already exercised.** `get_torso_rectangle`
*looks* like it can return `None`, but the guard is dead code:
[geometry.py:18](../ai/models/geometry.py) tests `len(valid_points) < 2` where
`valid_points` is a comprehension over four fixed indices and is therefore always
length 4. **No call site has ever actually received `None`.** The nominal
tolerance in `calculate_distance_between_fighters` and `distance_to_rect` is
untested, and every other caller must be checked by hand rather than assumed
safe. Note also that `calculate_distance_between_fighters` returns `inf` for a
missing rect — callers comparing it against a threshold will read "far apart"
where the truth is "unknown", which is the wrong default for a state classifier.

<a id="st1-3"></a>
### 3. Events are not gated to rounds ✅ DONE (round-gating + replay exclusion)
**`fight_processing/fight_processing.py:314`** (frame loop)

`rounds` is already passed in and `round_starts`/`round_ends` are already built
at `:299-311`, but they are only used to emit round-boundary events. The strike
loop runs over the whole video — replays (slow-motion, so velocity is
meaningless), walkouts, post-fight. 80% of output comes from there.

**Fix:** skip strike detection and state updates outside rounds. Keep writing
`fighter_frames` for the whole video (the frontend overlay needs them).
Then add replay exclusion: scoreboard OCR already samples the round timer and
`SCOREBOARD_TIMER_MAX_BACKWARD_JUMP` already exists — a timer that jumps
backward or freezes marks a replay. Wire that into an exclusion mask.

✅ **Both halves landed.** Round-gating skips strike/state detection outside
every detected round. Replay exclusion reuses the existing per-sample check
in `scoreboard_overlay/extraction.py`'s `_smooth_samples()` (which already
tags a backward-jumping timer reading `parse_error = "timer_smoothed_out"`
during smoothing, previously discarded rather than surfaced) via a new
`detect_replay_ranges()` in `fight_segmentation.py`, requiring
`MIN_REPLAY_SAMPLES` (3) consecutive rejections before calling it a replay
rather than one noisy OCR read. Threaded through `segment_fights()` →
`pipeline.py` → `process_fight(..., excluded_ranges=...)`, gated in the frame
loop the same way as the round check (still writes `fighter_frames`).
`detect_replay_ranges()` unit-verified against synthetic samples (genuine
run detected, isolated noisy read correctly ignored, empty/trailing-run
edge cases); a full pipeline re-run confirmed no crash and byte-identical
output. **Not verified against an actual replay** — the one test video's
scoreboard OCR doesn't calibrate at all (falls back to detection-only
segmentation), so `excluded_ranges` is empty on every run so far. Re-verify
once a video with working OCR and a real replay is available.

*Expect:* sanity `events inside rounds` FAIL (80%) → PASS.

<a id="st1-4"></a>
### 4. Absolute-pixel thresholds on a zoom-varying 2D projection ✅ DONE (all, including tape-patch)
**`models/constants.py`**

Every threshold was made scale-invariant except the most important one:
`DISTANCE_GRAPPLING_THRESHOLD = 20` px is the *primary axis* of the state
classifier. Same for `MIN_HIP_DROP_THRESHOLD = 30` and
`ROUND_ENGAGEMENT_DISTANCE = 800`.

**Fix:** express all three as ratios of fighter scale (or frame width for the
segmentation one). Call sites: `determine_fight_state`
(`fight_processing_util.py:652`), `determine_takedown_initiator` (`:271`),
`fight_segmentation.py`.

**A fourth one is not in `constants.py` at all.**
[geometry.py:53](../ai/models/geometry.py) hardcodes `if torso_len < 20:` as the
trigger for the shoulder-width fallback inside `get_fighter_scale` — an absolute
pixel threshold sitting *inside the denominator of every normalised threshold in
the system*, and one that fires more often the further the camera is from the
cage. It also violates `ai/CLAUDE.md`'s own rule that `constants.py` is the single
source of truth and processing modules never hardcode a threshold. Move it out
and express it as a fraction of frame height, or of the fighter's bbox diagonal.

Lower priority, same class: `TAPE_PATCH_HALF = 40` and `WRIST_EDGE_MARGIN = 10`
are absolute pixels in corner assignment — a component this plan already calls
unreliable, and one whose failures corrupt training data ([0a](02a-upload-tracks.md#0a)).
✅ **DONE.** Replaced with `TAPE_PATCH_RATIO` (fraction of fighter scale,
computed once per `_sample_tape()` call via `get_fighter_scale`, returning no
tape sample for a frame where scale is unusable rather than falling back to
an absolute crop size) and `WRIST_EDGE_MARGIN_RATIO` (fraction of frame
width). Both calibrated against the same reference measurement as the other
three ratios in this step; verified with a full pipeline re-run producing
sane corner-assignment output (tape pixel counts, confirmed swaps) with no
crash or regression.

<a id="st1-5"></a>
### 5. "fps-invariant" constants that are raw frame counts ✅ DONE
**`models/constants.py`** + call sites

`STRIKE_COOLDOWN_FRAMES=15`, `RECOIL_LOOKAHEAD_FRAMES=4`,
`TAKEDOWN_LOOKBACK_FRAMES=15`, `STRIKE_EXTENSION_FRAMES=2`,
`MIN_GRAPPLING_THRESHOLD=3`, `MIN_GROUND_THRESHOLD=5`,
`TRACK_MAX_FRAMES_MISSING=30`, `CORNER_SWAP_CONFIRM_FRAMES=4`.

At 50fps the recoil window is **0.08s** — far too short to measure head
displacement from impact, which is why landed/missed is noise.

**Fix:** convert to `*_SECS` and multiply by fps at the use site. The pattern
already exists for the segmentation constants (`MIN_FIGHT_END_GAP_SECS` etc.,
converted at runtime) — follow it.

<a id="st1-6"></a>
### 6. Velocity is not velocity ⏳ BLOCKED — needs labels (Stage 0)
**`fight_processing/fight_processing_util.py:481-486`**

Speed is computed as `|displacement since last confident frame| × fps` and
**never divided by the gap**, so its magnitude scales with how long the limb was
occluded (up to `max_base_gap` ≈ 0.3s). Inflated velocities forced
`PUNCH_VELOCITY_RATIO` up to 4.5, where only the top ~5% of arm extensions pass
(measured p95 = 5.42). Real punches lose; occlusion artifacts win.

**Fix:** divide by the actual frame gap to get true px/sec, then re-sweep the
ratios ([step 8](#st1-8)). Do both together — the fix alone makes results worse until the
thresholds move.

⚠️ **`ai/CLAUDE.md` currently documents the broken behaviour as intentional and
warns against fixing it** (the "Velocity uses raw `fps` (not gap-normalized)"
paragraph). That note is rationalising a compensating error and must be rewritten
as part of this change.

**The same section is defeated by a guard at the call site.** `detect_strikes` is
only invoked when the *immediately preceding* frame had both fighters' keypoints
([fight_processing.py:481](../ai/fight_processing/fight_processing.py)):

```python
if prev_red_kp is not None and prev_blue_kp is not None:
```

That directly contradicts the per-limb `vel_base` design, whose entire purpose is
to span the frames where the punching wrist blurs out — the impact frames. The
baseline is confidence-gated and carries its own staleness check
(`max_base_gap`), so this outer guard adds nothing except discarding exactly the
frames the mechanism exists to recover. Drop it and let `vel_base` do the
gating. Do this **with** the gap-division fix and the re-sweep, not separately:
all three move the same distribution.

(`prev_red_kp` / `prev_blue_kp` are also unused *inside* `detect_strikes`, which
reads `state["vel_base"]` instead — remove the parameters once the guard is gone.)

<a id="st1-7"></a>
### 7. State machine has no real temporal smoothing ✅ DONE
**`fight_processing/fight_processing_util.py:613`** (`determine_fight_state`)

3- and 5-frame consecutive counters are 0.06–0.1s at 50fps — no hysteresis at
all in practice.

**Fix:** median filter over ~0.5s of per-frame candidates plus a minimum-dwell
constraint (~0.75s) before emitting a transition.

*Expect:* sanity `state does not flap` and `state dwell is physical` → PASS.

<a id="st1-8"></a>
### 8. Threshold sweep — new `ai/eval/sweep.py` ⏳ BLOCKED — needs labels (Stage 0); not yet built
Coordinate/grid sweep over the velocity and contact ratios, reporting F1 per
setting against the labelled set. This is the payoff of the harness: tuning
becomes optimisation instead of eyeballing. Report the human ceiling
([0e](02d-label-quality.md#0e)) beside every swept F1. A setting that scores above
the ceiling is fitting label noise, not detecting strikes.

---

## Verification — Pipeline fixes

Run from `ai/`:

```bash
python main.py <video>
python -m eval.cli sanity <video>       # gate: target 6/6 pass
python -m eval.cli score  <video>       # once labels exist
```

Gate on the sanity checks first — they need no labels and catch output that is
*internally impossible* rather than merely inaccurate:

| Check | Baseline | Target | Fixed by |
|---|---|---|---|
| events inside rounds | FAIL 80% outside | PASS 0% | [Step 3](#st1-3) |
| no simultaneous mutual strikes | FAIL 64% | PASS ≤2% | [Step 1](#st1-1) |
| state does not flap | FAIL 50/min | PASS ≤15/min | [Steps 2](#st1-2), [7](#st1-7) |
| state dwell is physical | FAIL 0.62s | PASS ≥1.0s | [Steps 2](#st1-2), [7](#st1-7) |
| no duplicate events | PASS | PASS | — |
| strike rate plausible | PASS 17.3/min | PASS | — |

Then on the scored report: strike **F1** as the headline, with fighter
attribution, family, target, and landed accuracy tracked separately. For fight
state watch `transitions/min` and `median dwell` rather than per-frame accuracy,
which stays high even while the state machine visibly flaps.

**Record before/after `score` output in every commit message that touches
`constants.py`.** Add this rule to `ai/CLAUDE.md`.

---

Next: [Stage 2 — Skeleton action model](04-stage2-model.md)
