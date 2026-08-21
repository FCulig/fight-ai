[← Back to plan index](../PLAN.md)

**Depends on:** [Checklist C1–C4](00-checklist.md) complete.
**Blocks:** [Stage 0](02-stage0-labelling.md), [Stage 1](03-stage1-artifacts.md), [Stage 2](04-stage2-model.md) — nothing in any of them begins until P1–P3 are done. [P4](#p4) specifically waits on [0c(5)](02b-label-schema.md#0c-5) inside Stage 0.

---

## Prerequisite — freeze the baseline

⚠️ **Blocking. No work in [Stage 0](02-stage0-labelling.md), [Stage 1](03-stage1-artifacts.md)
or [Stage 2](04-stage2-model.md) begins until P1–P3 are done — and P1–P3 do not
begin until the [C1–C4 checklist](00-checklist.md) is complete.**

Every number in the Context table describes the pipeline *as it exists at this
commit*. The moment a constant moves or a fix lands they become unreproducible,
and the plan loses the only evidence that its diagnosis was right. A plan whose
entire justification is "measure everything" cannot start by discarding its own
starting measurement.

✅ **DONE — P1, P2, P3.** ⏳ **BLOCKED — P4, P5** (need labelled data from Stage 0, which is not yet labelled).

<a id="p1"></a>
### P1. Tag the baseline commit

**Requires [C1](00-checklist.md#c1).** The tag must point at a commit that
contains `ai/eval/` and the current working-tree pipeline, or [P4](#p4) cannot
check it out and run `score`:

```bash
git status --short          # must be clean — see C1
git tag baseline/pre-stage-1
```

One command, and it is the difference between recovering a scored baseline later
and never having one ([P4](#p4)).

<a id="p2"></a>
### P2. Add `--json PATH` to `sanity` and `score`

New `ai/eval/report_io.py`. `SanityReport`, `Report`, `StrikeScore`,
`StateScore`, `RoundScore` and `PRF` are already dataclasses, so
`dataclasses.asdict()` does most of the work. Two members need handling:

- `StrikeScore.missed` / `.spurious` hold `Strike` / `PredictedStrike` objects —
  reuse the serialisation path `FightLabels.save()` already has.
- `StrikeScore.family_confusion` is keyed by a `(str, str)` tuple, which cannot
  be a JSON object key — join to `"gt>pred"` on write, split on read.

Every artifact records, beside the scores:

| Field | Why |
|---|---|
| `git_sha` | which code produced it |
| `constants_sha256` | hash of `models/constants.py` — the actual independent variable |
| `video` | which fight |
| `tolerance_frames` | a score at a different tolerance is not comparable ([0f](02d-label-quality.md#0f)) |

`constants_sha256` is the load-bearing one. It turns "before/after" into a
verifiable claim instead of an honour system, and it catches a threshold that
moved without being recorded.

<a id="p3"></a>
### P3. Capture the label-free baseline now

**Requires [C2](00-checklist.md#c2) and [C4](00-checklist.md#c4)** — there is
no baseline video on disk until then.

```bash
python main.py <video>
python -m eval.cli sanity <video> --json eval/baselines/<video>.<sha>.json
```

Commit the artifact. `sanity` needs no labels, so nothing else blocks it — which
is exactly why it is the prerequisite and not a later step.

Record the source video's `videocheck` result (reported vs. decoded frames)
in the artifact alongside `git_sha` and `constants_sha256`. A baseline taken
from a truncated file is worse than no baseline, because it looks like one — the
Context table is what that costs. Since the video itself is gitignored and
user-retained ([C3](00-checklist.md#c3)), the artifact is the only durable
record that the footage behind it was intact.

<a id="p4"></a>
### P4. Capture the scored baseline once labels exist — from the tag

`score` needs ground truth, which does not exist yet, while
[Stage 1](03-stage1-artifacts.md) steps 1–5 and 7 are deliberately sequenced
*before* labelling finishes. Left alone, that means the original pipeline is
**never scored at all** and every Stage 1 result is compared against nothing.

After [Stage 0](02-stage0-labelling.md) completes:

```bash
git checkout baseline/pre-stage-1
python main.py <video> && python -m eval.cli score <video> --json …
git checkout -
```

Five minutes with the tag; archaeology without it. This is the whole reason
[P1](#p1) runs first.

⚠️ **P4 runs after [0c(5)](02b-label-schema.md#0c-5), never before.** Until
labels live in their own `label_events` table, `python main.py <video>` opens
with `DELETE FROM fight_events WHERE fight_id = :fid` and destroys the ground
truth P4 exists to score against. Sequence:
[0c(5)](02b-label-schema.md#0c-5) → labels → P4.

<a id="p5"></a>
### P5. Make the closing rule enforceable

With baselines stored, "record before/after `score` in every commit that
touches `constants.py`" stops being a convention. `sweep.py`
([Stage 1 step 8](03-stage1-artifacts.md#st1-8)) refuses to report a result
with no stored baseline at a matching `tolerance_frames`, and a changed
`constants_sha256` with no accompanying artifact becomes a failed check rather
than a number nobody wrote down.

---

## Verification — Baseline

- `eval/baselines/<video>.<sha>.json` exists and is committed before any
  [Stage 1](03-stage1-artifacts.md) commit touches `constants.py`.
- Re-running `sanity --json` on an unchanged checkout reproduces the stored
  artifact byte-for-byte apart from timestamps — if it does not, the baseline is
  not a baseline.
- `constants_sha256` in the artifact matches `sha256sum models/constants.py` at
  the recorded `git_sha`.
- `git tag -l baseline/pre-stage-1` resolves.

---

Next: [Stage 0 — The labelling framework](02-stage0-labelling.md)
