# How to label fight footage

A guide for whoever is sitting in front of the video marking strikes. Read it
once end to end before your first fight — most of the mistakes here are silent,
and a fight labelled under the wrong convention is worse than one not labelled
at all, because nothing downstream can tell.

If you want the reasoning behind any rule, it is in [PLAN.md](PLAN.md); this
document is the operating manual.

---

## What you are actually producing

Two things at once, from the same keystrokes:

1. **Ground truth** — the yardstick every pipeline change is measured against.
   An F1 score is a statement about your labels as much as about the model.
2. **The training set** — the skeleton action model learns from
   `fighter_frames.keypoints` (the pose the pipeline already extracted) paired
   with *your* frame numbers, corners and action names. A wrong label is not
   noise the model averages out; it is an instruction.

Which means: **consistency beats volume, and beats accuracy in the abstract.**
A rule you apply the same way 300 times is useful even if someone else would
have chosen differently. A rule you apply one way in round 1 and another way in
round 3 is not.

When you hit a case this document does not cover, do **not** improvise silently.
Pick a rule, write it down in `ai/eval/README.md` under the labelling
conventions, and apply it for the rest of the project.

---

## Before you label

### 1. The video must be intact

A truncated download opens fine, reports a full duration, and simply stops
decoding partway through. Every threshold in `models/constants.py` was tuned
against the first third of one broken fight, which is the reason this project
exists. Check before you spend two hours on it:

```bash
cd ai
python -m eval.cli video fight_videos/<your_video>.mp4   # must exit 0
```

### 2. The video must stay on disk, byte-identical, forever

`ai/.gitignore` excludes `*.mp4`, so **no video is ever in the repo**. Your
labels are frame numbers pointing into a file the repo cannot see. Delete it or
re-download it and every label silently detaches from the footage it describes —
a different encode shifts frame numbering, and nothing in the tooling can detect
that it happened. Keep every labelled source video until the project is
finished. Re-downloading "the same" video is not the same video.

### 3. Upload in **Manual** mode

In the upload dialog, choose the manual/self-annotate track, not "Upload &
analyze". Both tracks run detection, tracking, pose, corner assignment,
scoreboard OCR and round segmentation — the manual track just suppresses strike
detection and the state machine.

That is deliberate, and it is why you must not label an AI-processed fight:

- You still get **fighter boxes and keypoints**, which are the model's input
  features. A labelled fight without pose has labels and nothing to learn from.
- You still get **rounds** from segmentation, which seed your round bounds.
- You get **no predicted events on screen**, so nothing anchors you. If you
  could see the pipeline's guess you would agree with it more often than you
  should, and the score would flatter itself.

Wait for the fight to reach *Labeling in progress* — the annotate page will show
a spinner until detection has finished — then open it from the fight list.

---

## The mechanics

Everything is keyboard-driven. Your left hand lives on the transport keys, your
right hand on the palette.

### Transport

| Key | Action |
|---|---|
| `Space` | play / pause |
| `←` / `→` | seek ∓1 s |
| `⇧←` / `⇧→` | seek ∓5 s |
| `,` / `.` | step ∓1 frame |

There is **no playback-speed control**, so do not try to label in real time.

### Selecting the fighter

| Key | Action |
|---|---|
| `r` | select red corner |
| `b` | select blue corner |
| `Esc` | deselect |

The selected corner stays selected until you change it. Every strike key logs
against whoever is currently selected, so **the commonest single error in this
whole workflow is logging an exchange to the wrong corner because you forgot to
press `b`.** In a fast exchange, press the corner key *first*, every time, even
when you think it is unchanged.

If you press a strike key with nobody selected, nothing is logged and you get a
"select a fighter first" toast. That is a save you did not make — go back for it.

### The palette

Hand strikes use boxing numbering.

| Key | Action |
|---|---|
| `1` | jab |
| `2` | straight right |
| `3` | left hook |
| `4` | right hook |
| `5` | left uppercut |
| `6` | right uppercut |
| `c` | calf kick |
| `l` | low kick |
| `m` | middle kick |
| `h` | high kick |
| `e` | elbow |
| `n` | knee |
| `t` | takedown attempt |
| `d` | takedown defended |
| `s` | submission attempt |
| `x` | knockdown |
| `w` | fight state → striking |
| `g` | fight state → grappling |
| `z` / `Backspace` | undo last event *from this session* |

Note the palette names hands **absolutely** (`left hook`, `straight right`), not
by stance (`jab`/`cross`). Label what the fighter's body did — a southpaw's lead
hand is their right, and the lead/rear distinction is derivable later from
stance. Do not mentally convert.

Undo only walks back events you logged in the current page session. To remove
anything older, click it in the annotation panel below the video.

---

## The conventions

These are the rules. They are not preferences.

### Which frame to mark

**The frame of impact.** For a strike that misses, **the frame of peak
extension** — the moment the limb is furthest out, whether or not it reached
anything.

The scorer matches within a window (currently ±0.25 s), so being a frame or two
off is harmless. Being *systematically* late is not — a consistent reaction lag
looks exactly like detection error and will push the tuning of every velocity
threshold in the wrong direction.

So do not press the key while the video is playing at speed. Work in passes:

1. Play until you see a strike, then hit `Space`.
2. Seek back a second (`←`), then step forward frame by frame (`.`) to the
   impact frame.
3. Press the corner key, then the strike key.
4. Resume.

It feels slow. It is roughly 1 minute of labelling per 5–10 seconds of round
time, and there is no faster way to get the frame right.

### Log every strike *thrown*, outcome unknown

Not just the ones that land. A punch that misses, gets blocked, gets slipped,
gets checked, or grazes is still a strike thrown, and it is exactly the negative
the model needs. Landed-vs-missed is deliberately out of scope for now — depth
is invisible to a 2D pose model, so "did it land" is the least reliable thing
anyone can ask of it. The task is **count strikes thrown**, and that is a
coherent task on its own.

> ⚠️ **Known bug, being fixed:** the palette currently records `success = true`
> for every strike, i.e. it claims everything landed. Ignore what the row says —
> label every strike thrown regardless, which is what makes the data correct once
> that field is switched to `null`. Do **not** compensate by only labelling
> strikes that land.

What is *not* a strike:

- **Feints.** No real extension, no intent to reach. Nothing is logged.
- **Range-finding paws** where the arm never extends. Judgement call — if the
  arm straightens toward the opponent, it is a jab; if it hovers, it is not.
  Pick the reading you can repeat.
- **Posturing, framing, gripping, swimming for underhooks** in the clinch. Hand
  movement is not a strike. This is precisely the false positive the pipeline
  makes most, so do not hand it a confirmation.

### Red and blue are what *you* see

Corner is the fighter's actual corner — glove tape, shorts, the graphic at the
start. Fixed for the whole fight.

**Do not copy the coloured box the overlay draws.** Corner assignment is one of
the components being measured, and it is one of the unreliable ones. If it
flips mid-clinch, the skeleton stored as "red" belongs to the other fighter
while your label says red threw a hook — silent training-data corruption caused
by the exact bug we are trying to fix.

So while you label, **watch the overlay boxes for a swap**, especially coming out
of a clinch. It is worth a deliberate glance every time the fighters separate.

> ⚠️ **Not yet implemented:** the `corner_swap` span (mark the stretch where red
> and blue are flipped) does not exist yet. Until it does, if you see a swap,
> **stop and note the frame range** — video name, start frame, end frame — and
> report it rather than working around it. Do not "fix" it by inverting your own
> labels for that stretch; that produces labels that disagree with the keypoints
> in a way nothing can detect afterwards.

### Fight state is marked as *change points*

You do not mark "clinch from frame 3001 to 3400". You mark **the frame where the
state changes**, and the span runs to the next mark. The fight is always in
exactly one state, so this halves the keystrokes and cannot produce a gap or an
overlap.

Mark the frame where the state *genuinely* changes, not where you notice it.
Same discipline as strikes: pause, step back, find the frame.

- `w` — striking (open range, exchanging at distance)
- `g` — grappling

> ⚠️ **Changing soon:** `state_grappling` is being split into **clinch** (`f`)
> and **ground** (`g`), because the pipeline distinguishes them and emits
> different events for each. Until that ships, existing `state_grappling` marks
> will be **deleted rather than guessed at**, so do not invest effort in state
> marks on a long fight yet. If you are labelling now, prioritise strikes.

### Rounds define what counts

Everything outside a round — intros, walkouts, between-round rest, replays
between rounds, post-fight — is simply not training data and is not scored. You
do not need a separate concept for any of it, and you should not label strikes
there.

Round bounds come pre-seeded from the AI segmentation, which is *also* a
component being measured. Check them: if a round really starts 100 frames before
the seeded boundary, that is 100 frames of real strikes sitting in a region
treated as "not fight". Confirming or nudging a bound is a handful of keystrokes
per fight and it yields ground-truth rounds to score segmentation against.

> ⚠️ **Not yet implemented:** editable round spans, and the `excluded` span for
> **mid-round replays and camera cuts away from the cage**. Slow-motion replays
> especially must eventually be excluded — velocity is meaningless in them. For
> now: **do not label anything inside a mid-round replay**, and note the frame
> range so it can be marked when spans land.

### Elbows

The pipeline has no elbow detector. Label them anyway (`e`). They will score as
false negatives, which is the honest reading, and the action model will need
them.

### When you genuinely cannot tell

Do not guess, and do not split the difference. If the camera cut away, if both
fighters are out of frame, if the exchange is a blur you cannot resolve after
stepping through it — **leave it unlabelled** and note the frame range as one to
exclude. A guessed label is worse than a missing one: a missing strike costs the
score one false negative, a wrong one teaches the model something false.

---

## Finishing a fight

1. When the fight ends, mark it with the **fight-end** button in the palette —
   method (KO/TKO, submission, decision, draw, DQ), winner, and any detail.
2. Hit **Finish Labeling**. That transitions the fight to *Labeling complete* and
   stamps it as having finalised ground truth.
3. Export and sanity-check what you produced:

```bash
cd ai
python -m eval.cli export  <video>   # writes eval/labels/<video>.json
python -m eval.cli summary           # progress toward the volume target
```

Label files in `ai/eval/labels/` **are committed to git**. They are the most
expensive artifact in the repo and the only one that cannot be regenerated.

> ⚠️ **Live data-loss bug:** labels are currently written into `fight_events`,
> the same table the pipeline writes predictions to — and the pipeline opens by
> deleting every row for that fight. **Running the AI pipeline over a fight you
> have labelled destroys the labels, with no warning.** Until labels move to
> their own `label_events` table, do not re-run `python main.py <video>` on a
> labelled fight, and export to JSON as soon as you finish so there is a copy
> outside the database.

---

## How much, and in what order

| Milestone | Volume |
|---|---|
| Useful for evaluation | ~50 strikes, one round |
| Needed for training | ~300 strikes, 2–3 fights, 10–15 min of round time |

Do **not** start by labelling three fights.

**Label one round first, then stop.** Have that same round labelled a second
time — by a second person if you can find one, otherwise by yourself after at
least a week's gap — and compare the two passes:

```bash
python -m eval.cli agreement <video>
```

This exists for two reasons, and the smaller one is the number.

The number is a **ceiling**: an F1 of 68% means something completely different
depending on whether two humans agree 95% of the time or 75%. Without it, the
threshold sweep will happily tune the pipeline to reproduce one labeller's
quirks and report it as an improvement. Only F1 is reported, never precision or
recall — between two humans there is no truth, and "annotator B recall 91%"
would be a claim about who was right that nobody can make.

The bigger payoff is **the disagreement list**. Walking the events where the two
passes differ tells you which distinctions are genuinely ambiguous — expect
hook-vs-uppercut to dominate — *before* 300 strikes are committed to a taxonomy
that turns out to be underspecified. Every decision you make resolving that list
goes into `ai/eval/README.md` as a convention.

If you re-labelled solo, record in the README that the ceiling is an optimistic
upper bound. You remember the fight; you agree with yourself more than two people
would.

---

## Checklist

Before you start a fight:

- [ ] `python -m eval.cli video <path>` exits 0
- [ ] Uploaded in **Manual** mode, state is *Labeling in progress*
- [ ] The video file is somewhere it will not be deleted or replaced

While labelling:

- [ ] Corner key pressed **before** every strike key
- [ ] Frame stepped to impact / peak extension, not tagged during playback
- [ ] Every strike thrown logged, landed or not
- [ ] Nothing logged in replays, walkouts, or between rounds
- [ ] Overlay boxes watched for a corner swap; any swap's frame range noted

After:

- [ ] Fight end marked, **Finish Labeling** pressed
- [ ] `export` run and the JSON committed
- [ ] AI pipeline **not** re-run over this fight
- [ ] Any new judgement call written into `ai/eval/README.md`
