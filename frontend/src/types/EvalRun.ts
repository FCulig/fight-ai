/**
 * One `python -m eval.cli score-pair` run: a `purpose='reference'` fight's
 * hand labels scored against a `purpose='ai_labeled'` fight's pipeline
 * predictions — two different fight ids, per the real accuracy workflow (see
 * frontend/CLAUDE.md "Fight purpose" and backend/CLAUDE.md).
 *
 * `f1`/`precision`/`recall`/`tp`/`fp`/`fn`/`offset_bias_frames`/
 * `offset_jitter_frames` are computed server-side at read time from the
 * stored report's raw tp/fp/fn/matched_offsets — mirrors ai/eval/score.py's
 * PRF properties, since dataclasses.asdict() doesn't serialise properties.
 */
export interface EvalRunSummary {
  id: number;
  reference_fight_id: number;
  scored_fight_id: number;
  /** 1-based rank of `scored_fight_id` among this fixture's scored fights, in
   * upload order — a fight's pipeline never re-runs, so each new pipeline
   * version is a new ai_labeled upload. Stamped server-side. */
  pipeline_version: number;
  /** The scorer's HEAD when this run was scored — NOT the code that produced
   * the scored fight's predictions. */
  git_sha: string;
  constants_sha256: string;
  tolerance_secs: number;
  tolerance_frames: number;
  scored_minutes: number;
  generated_at: string;
  triggered_by: string | null;
  f1: number | null;
  precision: number | null;
  recall: number | null;
  tp: number | null;
  fp: number | null;
  fn: number | null;
  offset_bias_frames: number | null;
  offset_jitter_frames: number | null;
}

/** e.g. `v1 · #62` — the pipeline version and the ai_labeled fight it is. */
export const versionLabel = (run: EvalRunSummary) => `v${run.pipeline_version} · #${run.scored_fight_id}`;

/** One run per pipeline version, oldest version first — each version's latest
 * scoring (`runs` arrive oldest first, so later runs overwrite earlier ones).
 * Re-scoring the same fight, e.g. after a scorer fix, replaces its point
 * rather than posing as a new version. */
export const latestPerVersion = (runs: EvalRunSummary[]): EvalRunSummary[] =>
  [...new Map(runs.map((r) => [r.pipeline_version, r])).values()]
    .sort((a, b) => a.pipeline_version - b.pipeline_version);

/** A ground-truth (label) strike — see ai/eval/schema.py's `Strike`. */
export interface LabelStrike {
  frame: number;
  fighter: 'red' | 'blue';
  family: string;
  target: string;
  landed: boolean | null;
}

/** A pipeline-predicted strike — `Strike` plus the raw pipeline action
 * string (e.g. `jab_head`) — see ai/eval/predictions.py's `PredictedStrike`. */
export interface PredictedStrikeItem extends LabelStrike {
  action: string;
}

/** One round's match — see ai/eval/score.py's `RoundScore.matched`:
 * [round_num, iou, start_offset_secs, end_offset_secs, seeded]. `seeded`
 * true means the label round is unverified (still byte-identical to what it
 * was auto-seeded from) — its IoU would be circular, so show that instead. */
export type MatchedRound = [number, number, number, number, boolean];

/** The full ai/eval/score.py `Report`, as persisted by report_io.save_report
 * / save_eval_run_db — same shape whether it came from the DB or a checked-in
 * ai/eval/baselines/*.json file. */
export interface EvalReport {
  video: string;
  fps: number;
  scored_minutes: number;
  strikes: {
    detection: { tp: number; fp: number; fn: number };
    tolerance_frames: number;
    fighter_correct: number;
    fighter_total: number;
    family_correct: number;
    family_total: number;
    target_correct: number;
    target_total: number;
    landed_correct: number;
    landed_total: number;
    nonspecific_matches: number;
    /** Keyed `"<truth>>predicted>"` → count — see report_io._confusion_to_json. */
    family_confusion: Record<string, number>;
    matched_offsets: number[];
    missed: LabelStrike[];
    spurious: PredictedStrikeItem[];
  };
  state: {
    frames_scored: number;
    frames_correct: number;
    confusion: Record<string, number>;
    gt_transitions_per_min: number;
    pred_transitions_per_min: number;
    gt_median_dwell_secs: number;
    pred_median_dwell_secs: number;
  };
  rounds: {
    matched: MatchedRound[];
    gt_count: number;
    pred_count: number;
  };
}

/** Single-run shape — adds the full nested report for the E3-E9 drill-down. */
export interface EvalRunResponse extends EvalRunSummary {
  report: EvalReport;
}

/** One row of `GET /eval-runs/fixtures` — every labelled `purpose='reference'`
 * fight, with its latest run or `is_measurable=false` (Section E's "E0 — not
 * measurable yet" state) when none exists. */
export interface FixtureSummary {
  reference_fight_id: number;
  video_path: string;
  labeled_at: string;
  is_measurable: boolean;
  latest_run: EvalRunSummary | null;
}
