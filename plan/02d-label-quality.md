[← Back to Stage 0 index](02-stage0-labelling.md) · [Plan index](../PLAN.md)

**Depends on:** taxonomy settled — [0c(3)](02b-label-schema.md#0c-3)/[0c(3b)](02b-label-schema.md#0c-3b)/[0c(4)](02b-label-schema.md#0c-4) — and [0d](02c-labelling-ui.md#0d) working, so at least one fight can be fully labelled to measure against.
**Blocks:** [Stage 1 step 8](03-stage1-artifacts.md#st1-8) (needs the 0e ceiling to be meaningful). Run this on the *first* labelled fight, before bulk labelling — that's the whole point.

---

<a id="0e"></a>
## 0e. Measure label quality before labelling at volume

✅ **Tooling DONE** — `passes_for_video`, `agreement` CLI command (bias/jitter
split, three ceilings, asymmetry regression-tested), and `--tolerance-override`
pinned to `DEFAULT_TOLERANCE_SECS`, all verified with synthetic passes.
⏳ **Not yet run for real** — needs an actual double-labelled fight, which
requires a human to label through the UI. See [0g](#0g) below for the same
caveat on corner-swap recall.

Every number in this document is measured against hand labels treated as ground
truth — the [Stage 1](03-stage1-artifacts.md) threshold sweep, the
[Stage 2](04-stage2-model.md) training set, the headline F1.
Nothing measures the labels themselves: one labeller, one pass, no agreement
number.

Two consequences, both silent:

- **The sweep optimises to noise.** [Step 8](03-stage1-artifacts.md#st1-8) keeps
  whichever threshold setting scores best. If a meaningful share of the
  disagreement is label noise, it will select the constants that best reproduce
  one labeller's quirks.
- **The headline F1 is uninterpretable.** An F1 of 68% is a different verdict
  depending on whether two humans agree 95% of the time or 75%.

**Double-label one round and report the agreement as a ceiling on every
subsequent score.**

<a id="0f"></a>
## 0f. Pin the matching tolerance

✅ **DONE.** `cli.py` imports `DEFAULT_TOLERANCE_SECS` (no more duplicated
`0.25`); `--tolerance-override` warns loudly on use; signed offset (bias) vs.
absolute offset (jitter) both recorded and reported; the `score.py:157`/`251`
bugs (`m.action` on a plain `Strike`, `state_at()` treating `None` as a
mismatch) are fixed; `score` prints the agreement ceiling beside F1 when
tolerances match and skips it (with a stated reason) when they don't.
⏳ **Floor/ceiling derivation from real data** still needs an actual
double-labelled fight — same blocker as 0e.

Every score in this document depends on one undeclared number: how far apart a
predicted strike and a labelled strike can be and still count as the same event.
`DEFAULT_TOLERANCE_SECS = 0.25` ([score.py:34](../ai/eval/score.py)) is the de
facto answer, and it is unjustified, duplicated and freely tunable.

- [cli.py:124](../ai/eval/cli.py) hardcodes `default=0.25` rather than
  importing the constant, so there are two sources of truth and every run goes
  through the one that is not authoritative.
- No persisted artifact records which tolerance produced it.
- During the Stage 1 sweep, tolerance is one more dial that raises F1 — and
  unlike `constants.py`, moving it leaves no trace.

**Structural fix.** `cli.py` imports `DEFAULT_TOLERANCE_SECS`; the flag becomes
`--tolerance-override` and warns loudly when it differs from the default;
`tolerance_frames` (already on `StrikeScore`) is written into every persisted
report, and two artifacts with different values are refused for comparison.

**Then derive the value rather than inheriting it.** The tolerance absorbs two
distinguishable things — labelling jitter and detection timing — and one bug
currently prevents telling them apart:
[score.py:196](../ai/eval/score.py) records `abs(g.frame - p.frame)`, so a
*systematic* lag (labeller reaction time) is indistinguishable from spread. A
consistent lag is a bias to subtract once, not a reason to widen the window.

Record the signed offset (`p.frame - g.frame`) and report both: median signed is
the **bias**, median absolute is the **jitter**. The cost matrix at
[score.py:157](../ai/eval/score.py) stays absolute — that use is correct.

The tolerance is then bounded on both sides:

| Bound | Source | Meaning |
|---|---|---|
| floor | p95 of human-vs-human `matched_offsets` from the [0e](#0e) agreement run | genuine labelling jitter must not count as a miss |
| ceiling | p5 of the gap between consecutive strikes by the same fighter, over the labelled set | two strikes in a combination must not be matchable to each other |

⚠️ **The current value may already breach the ceiling.** `_match_strikes`
minimises *total* offset within the window, so a combination with one missed
detection can shift-match — predicted cross to labelled jab, predicted hook to
labelled cross — reporting three true positives where the truth is two TP, one
FN and one FP. At 50fps a ±12-frame window needs punches closer than 0.24s to do
this; a fast 1-2 is 0.15–0.2s. This inflates F1 in precisely the situation that
matters most.

If the floor exceeds the ceiling, strike-level matching cannot resolve
combinations and scoring moves to the combination level. Better to learn that
here than at Stage 2.

**Depends on [0e](#0e)** for the floor measurement; the ceiling needs only the labels.
Both are a few lines in `summary`.

### This is the existing scorer, not a new one

`PredictedStrike` subclasses `Strike`
([predictions.py:32](../ai/eval/predictions.py)), and `FightLabels` already
exposes everything `score()` reads off its second argument — `.fps`,
`.strikes`, `.rounds`, `.state_at()`. So `score(pass_a, pass_b)` is nearly
callable as-is: agreement is not a new metric but a new *input pairing* for the
existing one.

A standalone agreement calculator is the obvious-looking alternative and the
wrong one. It would drift from `score.py` — different matcher, different
tolerance, different handling of excluded spans — and a ceiling computed
differently from the score is not a ceiling on anything.

Two incompatibilities, both one-liners:

| Where | Problem | Fix |
|---|---|---|
| [score.py:395](../ai/eval/score.py) | `format_report` reads `m.action`; `Strike` has none | `getattr(m, "action", f"{m.family}_{m.target}")` |
| [score.py:251](../ai/eval/score.py) | assumes `preds.state_at()` returns a string; `FightLabels.state_at()` returns `None` outside a state span | skip the frame when either side is `None` — a latent sharp edge regardless |

### Storage and CLI

`FightLabels` already carries `labeler` ([schema.py:140](../ai/eval/schema.py));
it just never distinguishes files. A second pass is
`labels/<video>.<labeler>.json` beside the primary `labels/<video>.json`.
`for_video()` keeps returning the primary; add `passes_for_video()`. New
subcommand: `python -m eval.cli agreement <video>`.

### Report F1 only

`score()` is asymmetric — `labels` is truth, `preds` is on trial. Between two
humans there is no truth. Swapping the arguments turns every false positive into
a false negative, so precision and recall trade places while **F1 is
unchanged**. F1 is the only symmetric, and the only honest, headline. Say so in
the docstring: "annotator B recall 91%" reads as a claim about who was right,
and that claim cannot be made.

Three ceilings, not one:

| Ceiling | From | Caps |
|---|---|---|
| detection F1 | `StrikeScore.detection` | pipeline strike F1 |
| family agreement | `family_accuracy` + `family_confusion` | family accuracy |
| corner agreement | `fighter_accuracy` | attribution accuracy — expect ~100%; anything less is a labelling-UI defect, not a labeller one |

`family_confusion` ([score.py:210](../ai/eval/score.py)) is more useful than
the scalar: it names *which* distinctions are unreliable. Expect
hook-vs-uppercut and lead-vs-rear (see the handedness note in
[0c(3b)](02b-label-schema.md#0c-3b)) to dominate.

### Wire the ceiling into the normal report

Save to `labels/<video>.agreement.json` and have `format_report` print
`F1 68.2%  (human ceiling 91.4%)` when present. This is the step that makes the
exercise pay for itself — a bare F1 is not actionable.

⚠️ **The tolerance must match.** `--tolerance` is a per-invocation flag
defaulting to 0.25s ([cli.py:124](../ai/eval/cli.py)). A ceiling computed at a
different tolerance than the score is not comparable to it. Record
`tolerance_frames` in the agreement JSON and refuse to print the ceiling when it
differs from the current run (this section).

### Do it on the first labelled round, not the last

The number is the smaller half of the payoff. The disagreement list —
`StrikeScore.missed` and `.spurious`, already populated — is the review queue:
walking those events fixes the primary label file *and* reveals which categories
are genuinely ambiguous, before 300 strikes are committed to a taxonomy that
turns out to be underspecified. Those decisions become the labelling conventions
in `ai/eval/README.md`.

**A second labeller is worth finding.** The same person twice will remember the
fight and agree with themselves, so a solo re-label is an optimistic bound. If
solo is the only option, leave a week between passes and record in the README
that the ceiling is an upper bound.

**Ordering:** 0e assumes the taxonomy from [0c](02b-label-schema.md#0c) is
settled — re-labelling against a changed vocabulary invalidates the comparison.
It lands after [0c(3)](02b-label-schema.md#0c-3)/[0c(3b)](02b-label-schema.md#0c-3b)/[0c(4)](02b-label-schema.md#0c-4)
and before bulk labelling.

**Scope:** one round, ~100 strikes — enough to tell 0.95 from 0.75, which is the
only resolution the decision needs.

<a id="0g"></a>
## 0g. Validate the corner-swap mitigation before labelling at volume

✅ **Tooling DONE** — `inject-swap` (its own inverse, verified round-trip
against real `fighter_frames`) and `corner-swap-recall` (detected/missed +
per-edge boundary error, verified both branches with a synthetic labelled
span) are implemented and tested. ⏳ **Not yet run for real** — needs an
actual labeller working an injected-swap fight. The "persist per-frame
assignment margin + pre-highlight" turn-detection-into-verification
follow-up (below) is **not built** — flagged as a good next step once real
recall numbers say it's needed, not required for the recall test itself.

[0a](02a-upload-tracks.md#0a)'s answer to silent training-data corruption is
that the labeller will *see* a corner swap on the overlay and mark it. That is
an assumption about human attention, applied to mid-clinch frames — two
overlapping boxes during a one-second exchange, the hardest place on screen to
notice anything. Nothing tests it, and the failure is silent by construction: a
missed swap produces training rows whose keypoints belong to the other fighter,
with a confident label attached.

**Inject a known swap and measure recall.** On an already-labelled fight, flip
`corner` on `fighter_frames` across a known ~200-frame mid-clinch window:

```sql
UPDATE fighter_frames SET corner = 1 - corner
WHERE fight_id = :fid AND frame BETWEEN :start AND :end;
```

Have the labeller work the fight normally, then compare their `corner_swap` spans
against the injected window. Two numbers, both needed:

| Metric | Why it matters |
|---|---|
| **detection rate** | whether the mitigation works at all |
| **boundary error** (frames, per edge) | the flip is applied at export — a span 30 frames short leaves 30 frames of corrupted training data |

⚠️ **This qualifies a claim in [0d](02c-labelling-ui.md#0d).** "Fraction of
labelled frames covered by a `corner_swap` span = the pipeline's
corner-assignment error rate" holds only at 100% labeller recall. Until this
test produces a recall number, that figure is a **lower bound** and must be
reported as one.

### Turn detection into verification

Scanning 8 000 frames for a rare event is the task humans are worst at;
confirming ~20 flagged candidates is one they are good at. `assign_corners()`
already computes everything needed to make that switch — a combined tape +
histogram distance per detection, a `CORNER_TEMPLATE_MIN_SEPARATION` trust gate
and a `CORNER_SWAP_CONFIRM_FRAMES` hysteresis counter — and then discards the
margin, keeping only the decision.

**Persist the per-frame assignment margin** and pre-highlight the spans where it
was marginal. The labeller reviews a candidate queue instead of the whole video,
and the same stored margin yields the corner-assignment error rate directly,
measured from the pipeline's own uncertainty rather than inferred from labeller
behaviour.

**Ordering:** runs on the first labelled fight, alongside [0e](#0e), before bulk
labelling. Its entire purpose is to find out whether the mitigation works while
one fight is at risk instead of three.

---

## Verification — Corner-swap recall (0g)

- With a 200-frame swap injected into `fighter_frames`, the labeller's
  `corner_swap` span overlaps it; record detection rate and per-edge boundary
  error in `ai/eval/README.md`.
- Restore the injected window afterwards (`UPDATE … SET corner = 1 - corner` is
  its own inverse) and confirm the fight's exported tensor is unchanged from
  before the injection.

---

Next: [Stage 1 — Fix the artifacts](03-stage1-artifacts.md)
