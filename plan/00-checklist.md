[← Back to plan index](../PLAN.md)

**Depends on:** nothing — these are the first actions in the project.
**Blocks:** [Prerequisite](01-prerequisite.md) — [P1](01-prerequisite.md#p1) needs C1, [P3](01-prerequisite.md#p3) needs C2 and C4.

---

## ⛔ Blocking user checklist — done by hand, before anything else

These are the steps only the user can do, and every one of them is a
prerequisite to the prerequisites. **[P1](01-prerequisite.md#p1) cannot be
executed correctly until C1 is done, and [P3](01-prerequisite.md#p3) cannot be
executed at all until C2 is done.** Tick every box before starting.

<a id="c1"></a>
- [x] **C1 — Commit the working tree.** `git status` currently shows ~139
  uncommitted insertions across `ai/fight_processing/fight_processing.py`,
  `ai/pipeline.py`, `ai/main.py`, `ai/models/FightProcessingState.py` and
  `ai/CLAUDE.md`, plus the entirely untracked `ai/eval/`. **The code that
  produced every number in this document is the working tree, not `HEAD`.**
  Tagging `HEAD` ([P1](01-prerequisite.md#p1)) would freeze a commit that has
  no `eval/` in it at all, so `git checkout baseline/pre-stage-1` in
  [P4](01-prerequisite.md#p4) would check out a tree that cannot run `score`.
  Commit first, then tag. Also delete the stray
  `db/alembic/versions/__pycache__/` that is currently untracked.

<a id="c2"></a>
- [x] **C2 — Put an intact fight video in `ai/fight_videos/`.** `fight_videos/`
  now holds only `JURICvsNOGUEIRA.mp4`; `BATURvsSTAMATOVIC.mp4`, which every
  number in the Context table was measured on, is gone. Confirm the replacement
  decodes fully before using it for anything:

  ```bash
  cd ai && python -m eval.cli video fight_videos/<video>   # must exit 0
  ```

<a id="c3"></a>
- [x] **C3 — Keep every source video for the life of the project, and treat that
  as a standing commitment.** Training data is user-supplied and user-retained.
  `ai/.gitignore` excludes `*.mp4` and `fight_videos/`, so **no video is ever in
  the repo** — a deleted or re-downloaded file silently invalidates the labels,
  the baselines and the training set that reference it, and nothing in the
  tooling can detect that it happened. Concretely, this means: the C2 baseline
  video, every video labelled in Stage 0, and every evaluation fixture must stay
  on disk, byte-identical, until Stage 2 is finished. Re-downloading a "same"
  video is not equivalent — a different encode shifts frame numbering and
  detaches every label from the frames it describes.

<a id="c4"></a>
- [x] **C4 — Re-measure the Context table on the C2 video.** Run the pipeline,
  then `sanity`, and replace rows 1–5 with the new figures plus the video name.
  This is the measurement [P3](01-prerequisite.md#p3) freezes. Until it exists
  there is no baseline, only a recollection of one taken from a corrupt file.

---

Next: [Prerequisite — freeze the baseline](01-prerequisite.md)
