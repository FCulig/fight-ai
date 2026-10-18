import { ChangeTile } from 'fightlytics';

const run = (v: number, f1: number, over: object = {}) => ({
  id: v, reference_fight_id: 12, scored_fight_id: 60 + v, pipeline_version: v, git_sha: 'a1b2c3d',
  constants_sha256: 'c0ffee', tolerance_secs: 0.5, tolerance_frames: 15, scored_minutes: 14.6,
  generated_at: '2026-10-01T12:00:00Z', triggered_by: 'dev', f1, precision: f1 + 3, recall: f1 - 4,
  tp: 120, fp: 30, fn: 38, offset_bias_frames: 2, offset_jitter_frames: 4, ...over,
});

const tile = { width: 300, display: 'flex' };

export const Improved = () => <div style={tile}><ChangeTile current={run(3, 71.4)} previous={run(2, 66.2)} /></div>;
export const Regressed = () => <div style={tile}><ChangeTile current={run(3, 61.0)} previous={run(2, 66.2)} /></div>;
export const NotComparable = () => <div style={tile}><ChangeTile current={run(3, 71.4)} previous={run(2, 66.2, { tolerance_frames: 10 })} /></div>;
export const FirstVersion = () => <div style={tile}><ChangeTile current={run(1, 58.3)} previous={null} /></div>;
