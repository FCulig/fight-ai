# ai/ — video processing pipeline

Takes an MMA fight video and writes everything to PostgreSQL. The steps are detection (boxes and skeletons) → tracking → corner assignment → scoreboard OCR → round segmentation → fight processing (the state machine plus the strike model). **Postgres is a hard dependency.** There is no no-DB path, and `.env` must set `DATABASE_URL`.

Subsystem rules load when you open matching files:
- `.claude/rules/ai-detection-tracking.md`
- `.claude/rules/ai-corner-assignment.md`
- `.claude/rules/ai-scoreboard.md`
- `.claude/rules/ai-segmentation.md`
- `.claude/rules/ai-fight-processing.md`
- `.claude/rules/ai-action-model.md`

`eval/README.md` covers the eval harness.

## Architecture rules
- `main.py` is argparse plus one call to `run_pipeline()` or `run_batch()`. It holds no logic, path building, timing, or processing imports.
- `pipeline.py` owns orchestration: step order, skip and fallback logic, timing, and the manifest.
- All debug output goes through `debug.py`'s `DebugContext` (`ctx.save_image`, `ctx.save_json`, `ctx.log`). Don't scatter `print` or `cv2.imwrite` calls.
- Every numeric threshold and frame count lives in `models/constants.py`.
- **No intermediate data files.** Steps hand dicts to each other in memory, and Postgres is the only store. The dev skip-flags (`--detection-file`, `--track-file`, `--pose-results`, `--scoreboard-samples`) only *load* files. `--verify-pose` and `--verify-scoreboard` are opt-in diagnostic outputs, and they skip `process_fight`.
- The `models/geometry.py` helpers return `None` when keypoints aren't confident. Treat `None` as "unusable this frame" and never substitute a default: an unknown distance must never count as "far apart".
- `eval/` is never imported by the pipeline. It only reads back what the pipeline persisted.

## Measure before you change a threshold
- **Fight-state and strike constants, `fight_processing/` logic, and strike-model weights** need a before/after `score-pair` result, with both numbers in the commit message. The constants are the `constants.py` block from `FIGHT_STATE_SMOOTHING_WINDOW_SECS` to `HEAD_ABOVE_SHOULDER_RATIO`. Use the `measure-pipeline-change` skill, and for retrains the `retrain-strike-model` skill.
- **Segmentation constants (`MIN_FIGHT_END_GAP_SECS` … `ROUND_DISENGAGED_RATIO`) and `SCOREBOARD_*` don't need a `score` delta.** Validate them against their own subsystem (see the segmentation and scoreboard rules). Don't trust round IoU: label `round` spans are copied from the pipeline's own `rounds` the first time Annotate opens a fight, so unless a person moved them, IoU scores ~1.000 against itself.
- **Every processed fight** gets the label-free checks (`sanity`, `corner_accuracy`) from the `check-processed-fight` skill, whatever changed.

## Running
- `python main.py` runs batch mode. It registers new files in `fight_videos/` with `ON CONFLICT DO NOTHING`, then processes every fight not in `completed`, `labeling_*`, `validating` or `invalid`. `failed` fights are retried on purpose. A file replaced at the same path isn't picked up again, so use single-file mode for it.
- `python main.py fight.mp4` runs single-file mode. Its upsert resets `state='queued'`, and existing child rows are treated as stale. With `--skip-events` it stops at `labeling_in_progress` (the manual-labelling track).
- Uploads don't start here. The backend first runs `eval.cli video --fight-id <id>` (full decode, state `validating`). That marks a truncated file `invalid`, or spawns `main.py` itself and hands over the pid (`_validate_and_dispatch` in `eval/cli.py`). With `PIPELINE_DISPATCH=queue`, set on the deployed server because it has no torch, it stops at `queued` instead, for a pipeline worker to pick up.

## Weights
- `yolo26x-pose.pt` (working dir): the XL pose model. It supplies every box and skeleton.
- `video_processing/weights.pt`: the nano detector, used only as a fighter-vs-referee mask. Its red/blue class head is ignored.
- `action_model/weights/strike_model.pt`: the strike model `process_fight` loads. It is committed to git.
