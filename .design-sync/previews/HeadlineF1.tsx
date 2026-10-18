import { HeadlineF1 } from 'fightlytics';

const run = (v: number, f1: number) => ({
  id: v, reference_fight_id: 12, scored_fight_id: 60 + v, pipeline_version: v, git_sha: 'a1b2c3d',
  constants_sha256: 'c0ffee', tolerance_secs: 0.5, tolerance_frames: 15, scored_minutes: 14.6,
  generated_at: '2026-10-01T12:00:00Z', triggered_by: 'dev', f1, precision: 74, recall: 69,
  tp: 120, fp: 42, fn: 54, offset_bias_frames: 2, offset_jitter_frames: 4,
});

// The Accuracy page's headline group: F1 ring, timing tiles, change vs previous version.
export const Headline = () => (
  <div style={{ width: 860 }}>
    <HeadlineF1 current={run(3, 71.4)} previous={run(2, 66.2)} />
  </div>
);
