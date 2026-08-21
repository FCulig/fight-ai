# Evaluation harness

Measurement layer for the processing pipeline. Nothing here is imported by the
pipeline — it only reads what the pipeline persisted to PostgreSQL and compares
it against hand-labelled ground truth.

It exists because the pipeline currently has ~40 hand-tuned constants in
`models/constants.py` and no way to tell whether changing one helps. Every
tuning decision so far was made by eyeballing a single video. That does not
converge: a threshold that fixes one clip silently breaks another, and there is
no signal to say so.

## Quick start

Labelling itself happens in the frontend, not here — upload a video in
**manual** mode, open it in the Annotate page, and use the on-screen palette
(see its own keyboard legend). This harness is where a finished labelling
session becomes ground truth on disk and gets scored against.

```bash
cd ai

# 0. Check the source video decodes fully — do this FIRST, see below
python -m eval.cli video fight_videos/BATURvsSTAMATOVIC.mp4

# 1. Once the fight is fully labelled and "Finish Labeling" was clicked,
#    build eval/labels/<video>.json from label_events/label_spans in Postgres
python -m eval.cli export fight_videos/BATURvsSTAMATOVIC.mp4

# 2. Check pipeline output for impossible artifacts — needs no labels
python -m eval.cli sanity fight_videos/BATURvsSTAMATOVIC.mp4

# 3. Score the pipeline against ground truth
python -m eval.cli score fight_videos/BATURvsSTAMATOVIC.mp4

# 4. Track labelling progress
python -m eval.cli summary
```

Labels live in `eval/labels/<video_stem>.json` and **are committed to git** —
they are expensive hand work and the single most valuable artifact in the repo.
`export` refuses to run against a fight that hasn't been through "Finish
Labeling" (`labeled_at IS NULL`) — that's the only durable marker that a
fight's ground truth is actually finished, since `state` gets reset the
moment a labelled fight is re-run through the AI pipeline to become an
evaluation fixture.

## Check the video first

`python -m eval.cli video <path>` decodes the whole file and compares the result
against the container's advertised frame count. A truncated download opens
fine, reports a full duration, and simply stops decoding partway through — the
pipeline processes the decodable prefix and reports success.

The only video currently in `fight_videos/` is in exactly this state:

```
container reports   24712 frames  (8.2 min)
decoder yields       8147 frames  (2.7 min)
[FAIL] TRUNCATED — 16565 frames (67%) never decode.
```

**Every threshold in `models/constants.py` was tuned against the first third of
one broken fight**, with corrupt frames around the break feeding the pose model.
Re-download before drawing conclusions from any metric.

## Start with `sanity`

The sanity checks need no labels and catch output that is *internally
impossible* rather than merely inaccurate. They will tell you more, faster,
than an F1 score will. On the current pipeline, four of six fail:

```
[FAIL] events inside rounds        75/94 strikes fall outside every detected round
[FAIL] no simultaneous mutual strikes   30 frames have BOTH fighters striking
[FAIL] state does not flap         55 transitions over 1.1 min = 50.0/min
[FAIL] state dwell is physical     median 0.62s between state changes
```

Two fighters do not throw punches on the same frame 30 times in a fight, and
fight state does not alternate every 0.6 seconds. These are bugs with specific
causes, not thresholds that need nudging.

## Then run `corner_accuracy` — before you label anything

```
python -m eval.corner_accuracy <fight_id>
```

Also label-free. It reads `fighter_frames.corner` back and checks it against
each fighter's kit colour, because a red/blue inversion is the one error that
leaves every artifact perfectly self-consistent: `sanity` sees valid structure,
`score` needs labels, and the labels themselves inherit the error the moment a
human starts tagging against a wrong overlay. Two of three fights were wrong
when this check was written:

```
fight 31  JURICvsNOGUEIRA        100%  OK
fight 42  MILIDRAGOVICvsMOOSMAN    1%  [FAIL]  whole fight inverted
fight 44  NAZHANDvsSTAROPOLI      66%  [WARN]  intermittent tracker swaps
```

`[FAIL]` means the whole-fight mapping is backwards. `[WARN]` means the
appearance path failed to correct tracker identity swaps — the FLIPPED frame
ranges it prints are where `corner_swap` spans belong. **"No decisive frames"
is not a pass**; it means the kit colours never read unambiguously and corner
assignment is simply unverified for that fight.

Run this before labelling. Labels recorded against an inverted overlay are
attributed to the wrong fighter and are silently useless as training data.

## Labelling guide

Labelling happens in the Annotate page (upload in **manual** mode, wait for
`LABELING_IN_PROGRESS`, open the fight). The palette and its keyboard
shortcuts are self-documenting via the on-page keyboard legend; the
conventions below are the ones that aren't obvious from the UI alone. The
labels are also the training set for the skeleton action model, so
consistency matters more than volume.

**Which frame to mark.** The frame of impact, or of peak extension for a
strike that misses. The scorer uses a ±0.25s window by default, so being a
frame or two off is harmless — being systematically early or late is not.

**Log every strike thrown, outcome unknown.** Landed-vs-missed is deferred —
every strike is recorded with `success = null`. The model needs negatives too,
so a punch that visibly misses still gets logged, not skipped.

**Red vs. blue** is the fighter's corner as shown by glove tape / shorts, fixed
for the whole video. Do *not* copy whatever the pipeline decided — corner
assignment is one of the things being measured. If the overlay shows a
swapped corner (most likely mid-clinch), mark it with a `corner_swap` span
(`O` to open, `O` again to close) rather than trusting the overlay or
excluding the stretch — those are exactly the frames the model most needs.

**Exclude mid-round replays and camera cuts** with an `excluded` span (`P` to
open, `P` again to close). Excluded spans are dropped from every metric, so a
predicted event inside one is neither a hit nor a false positive. Slow-motion
replays especially must be excluded: velocity thresholds are meaningless
there. Between-round rest and pre/post-fight footage don't need this — they're
already outside every `round` span.

**Round bounds** are seeded from AI segmentation and shown as a draggable span
in the ROUNDS lane — confirm or nudge the edges rather than re-marking from
scratch. Everything outside a round is not training data and not scored.
"Finish Labeling" requires every detected round to have a confirmed span.

**State marks** (`W`/`F`/`G` for STRIKING/CLINCH/GROUND) are change points, not
spans — mark the frame where the state genuinely changes and the span is
derived automatically, running to the next mark (or the end of the round for
the last one).

**Elbows** have no pipeline equivalent yet. Label them anyway — they will score
as false negatives, which is the honest reading, and the action model will
need them.

## Reading the score report

**Strike detection** is matched with optimal (Hungarian) assignment on temporal
distance, not greedy nearest-match, so the score does not depend on which end of
the video you start from.

Matching **ignores the fighter** by default, and attribution accuracy is
reported separately. This is deliberate: "we missed the strike" and "we saw the
strike but credited the wrong corner" are different bugs with different fixes,
and a joint match key would hide detection progress behind corner-assignment
noise. Pass `--strict-fighter` to fold it back in.

**Non-specific predictions are excluded from the family/target denominators.**
The pipeline emits `clinch_punch` / `ground_punch` with no punch family and no
target zone, so grading those against a labelled `hook`/`head` would penalise it
for a distinction it never attempts. They still count for detection.

**Only scored frames count** — inside a labelled round and outside every
excluded span. Events on either side are dropped rather than counted as false
positives.

For fight state, watch `transitions/min` and `median dwell` more than per-frame
accuracy. Per-frame accuracy is dominated by whichever state is most common and
stays high even when the state machine is visibly flapping.

## How many labels?

~300 strikes is the working target before the skeleton action model can be
expected to beat hand-tuned rules — roughly 10–15 minutes of round time. Two or
three fights. `python -m eval.cli summary` tracks progress toward it.

For evaluation alone, far fewer are useful: even 50 labelled strikes on one
round will tell you whether a change to `constants.py` helped or hurt, which is
strictly more than is knowable today.

## Before labelling at volume: measure the labels themselves

Every number above is measured against hand labels treated as ground truth.
Nothing measures the labels themselves unless you run these — do it on the
*first* labelled fight, not the last, since the disagreement list doubles as a
review queue that catches an underspecified taxonomy before 300 strikes are
committed to it.

**Double-labelling ceiling.** Label one round twice — ideally a second
person, or the same labeller with a week's gap so they don't just remember and
agree with themselves — and measure how much the two passes agree:

```bash
python -m eval.cli export fight_videos/x.mp4                # primary pass
python -m eval.cli export fight_videos/x.mp4 --as alex       # second pass → x.alex.json
python -m eval.cli agreement fight_videos/x.mp4              # writes x.agreement.json
```

Reports **F1 only** — `score()` is asymmetric (truth vs. on-trial) and between
two humans there is no truth, so precision/recall trade places if you swap the
passes while F1 stays fixed; F1 is the only claim that doesn't silently assert
who was right. Once `x.agreement.json` exists, `score` prints it beside every
subsequent F1 for that video as a ceiling — a tuned setting that scores above
it is fitting label noise, not detecting strikes better than a human would.

**Matching tolerance is pinned, not a free dial.** `DEFAULT_TOLERANCE_SECS` in
`score.py` is the single source of truth; `--tolerance-override` on `score` /
`agreement` warns loudly when used and should come with a reason recorded
somewhere. The report also separates **bias** (median signed offset — a
systematic lag, e.g. labeller reaction time) from **jitter** (median absolute
offset — genuine spread): a bias is a constant to subtract once, not a reason
to widen the tolerance window.

**Corner-swap recall.** `0a`'s mitigation for corner-assignment errors is that
the labeller *sees* a swap on the overlay and marks it — untested, and applied
to the hardest place on screen to notice anything (overlapping boxes
mid-clinch). Measure it before relying on it at volume:

```bash
python -m eval.cli inject-swap fight_videos/x.mp4 --start 3200 --end 3450
# label the fight normally, including the injected window, then:
python -m eval.cli export fight_videos/x.mp4
python -m eval.cli corner-swap-recall fight_videos/x.mp4 --start 3200 --end 3450
# UPDATE ... SET corner = 1 - corner is its own inverse:
python -m eval.cli inject-swap fight_videos/x.mp4 --start 3200 --end 3450   # restores
```

Two numbers matter: whether it was detected at all, and the boundary error in
frames per edge (a span that starts 30 frames late still exports 30 frames
with the wrong corner). Until this has been run and passed, "fraction of
labelled frames covered by a `corner_swap` span" is a **lower bound** on the
pipeline's corner-assignment error rate, not the real figure — report it as
one.

**Not yet built:** persisting `assign_corners()`'s own per-frame confidence
margin and pre-highlighting the marginal spans for review, so the labeller
scans a short candidate queue instead of 8,000 frames. The recall test above
works without it; it would make the mitigation itself cheaper to apply
correctly. Worth doing once the recall numbers say it's needed.

## Known gap

`fight_events.state` is now the structured source of truth for a
STRIKING/CLINCH/GROUND transition row (`predictions.py` reads it directly);
the free-text regex over `description` survives only as a fallback for rows
written before that column existed.

## Stage 1 finding: fixing the pose-sharing bug collapsed grappling detection

After landing Stage 1 steps 1–5 and 7 (Hungarian pose↔detection assignment,
confidence-gated geometry, round gating, scale-relative thresholds,
fps-invariant timing, temporal state smoothing — see `plan/03-stage1-artifacts.md`),
a full re-run on `JURICvsNOGUEIRA.mp4` fixed `no simultaneous mutual strikes`
and `no duplicate events` (both now PASS) but dropped `state does not flap`'s
input to zero transitions and cut total strikes from 93 to 7 — `strike rate
plausible` now FAILs low (3.1/min vs. the expected 5–60).

**This is very likely the pose-sharing bug's true effect being removed, not a
new regression.** Before step 1, red and blue could be assigned the *same*
pose skeleton, making torso-rect distance read exactly 0 — which reads as
maximally entangled. That is almost certainly what was driving the baseline's
27 `clinch_punch` + assorted ground events and its 44 state transitions in
2.3 minutes (55/min — already flagged as unrealistic flapping, not a real
state). With one-to-one assignment, real torso-rect separation is measured,
and a direct query against this run's `fighter_frames` shows only ~2% of
both-fighters-confident frames read as entangled at the current
`DISTANCE_GRAPPLING_RATIO` (0.11) — too sparse to ever hold the
`FIGHT_STATE_SMOOTHING_WINDOW_SECS`/`FIGHT_STATE_MIN_DWELL_SECS` window, so
the state machine never leaves its initial STRIKING seed and every
clinch/ground strike type becomes unreachable for this fight.

`DISTANCE_GRAPPLING_RATIO` (and the other new `_RATIO`/`_SECS` constants from
step 4/5) were calibrated by preserving the *old absolute-pixel threshold's*
apparent behaviour against this video's median torso scale — a reasonable
placeholder with no ground truth to do better, but not a real calibration.
**Do not hand-tune it further by eyeballing this one video** — that is
exactly the anti-pattern this whole harness exists to replace. This is
precisely what Stage 1 step 8 (the threshold sweep, blocked on Stage 0
labels) exists to fix properly. Baseline artifact:
`eval/baselines/JURICvsNOGUEIRA-stage1-partial.json`.
