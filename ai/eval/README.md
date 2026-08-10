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

```bash
cd ai

# 0. Check the source video decodes fully — do this FIRST, see below
python -m eval.cli video fight_videos/BATURvsSTAMATOVIC.mp4

# 1. Label a video (opens a video window; controls print to the terminal)
python -m eval.cli label fight_videos/BATURvsSTAMATOVIC.mp4 --labeler filip

# 2. Check pipeline output for impossible artifacts — needs no labels
python -m eval.cli sanity fight_videos/BATURvsSTAMATOVIC.mp4

# 3. Score the pipeline against ground truth
python -m eval.cli score fight_videos/BATURvsSTAMATOVIC.mp4

# 4. Track labelling progress
python -m eval.cli summary
```

Labels live in `eval/labels/<video_stem>.json` and **are committed to git** —
they are expensive hand work and the single most valuable artifact in the repo.

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

## Labelling guide

The labels are also the training set for the skeleton action model, so
consistency matters more than volume.

**Which frame to mark.** The frame of impact, or of peak extension for a strike
that misses. The scorer uses a ±0.25s window by default, so being a frame or two
off is harmless — being systematically early or late is not.

**Label every strike thrown, not just those that land.** The model needs
negatives. A punch that misses is a `missed` strike, not a non-event.

**Red vs. blue** is the fighter's corner as shown by glove tape / shorts, fixed
for the whole video. Do *not* copy whatever the pipeline decided — corner
assignment is one of the things being measured.

**Use `x` to exclude** replays, walkouts, corner rest between rounds, and camera
cuts away from the cage. Excluded spans are dropped from every metric, so a
predicted event inside one is neither a hit nor a false positive. Slow-motion
replays especially must be excluded: velocity thresholds are meaningless there.

**State spans** are marked as change points (`s` then `1`/`2`/`3`) and
materialised into contiguous spans on save. Mark the frame where the state
genuinely changes, not where you notice it.

**Elbows** have no pipeline equivalent yet. Label them anyway — they will score
as false negatives, which is the honest reading, and the action model will need
them.

### Controls

| | |
|---|---|
| `SPACE` | play / pause |
| `a` `d` | step ∓1 frame |
| `A` `D` | step ∓10 frames |
| `z` `c` | step ∓1 second |
| `Z` `C` | step ∓10 seconds |
| `-` `=` | playback speed |
| `r` `b` | begin strike — red / blue |
| then | `j`ab `k`=cross `h`ook `u`ppercut k`n`ee `m`=elbow `i`=kick |
| then | `1` `2` `3` = head/body/leg **landed**, `!` `@` `#` = **missed** |
| `s` then `1`/`2`/`3` | state STRIKING / CLINCH / GROUND from this frame |
| `[` `]` | round start / end |
| `x` | exclusion start, `x` again to close |
| `u` | undo last annotation |
| `o` | save |
| `ESC` | cancel pending chord, or quit |

Re-running `label` on a video resumes from the existing file.

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

## Known gap

Fight-state transitions are recovered from the free-text
`fight_events.description` column by regex (`predictions.py`), because `action`
is NULL for a STRIKING transition and the state is only written into the prose.
`fight_events` should grow a structured `state` column; until it does, that
parser is the contract and will break if the description wording changes.
