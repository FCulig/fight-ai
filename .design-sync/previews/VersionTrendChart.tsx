import { useState } from 'react';
import { VersionTrendChart } from 'fightlytics';

const run = (v: number, f1: number, p: number, r: number, over: object = {}) => ({
  id: v, reference_fight_id: 12, scored_fight_id: 58 + v * 3, pipeline_version: v, git_sha: 'a1b2c3d',
  constants_sha256: v >= 3 ? 'c0ffee2' : 'c0ffee', tolerance_secs: 0.5, tolerance_frames: 15, scored_minutes: 14.6,
  generated_at: `2026-0${v + 4}-1${v}T12:00:00Z`, triggered_by: 'dev', f1, precision: p, recall: r,
  tp: 120, fp: 30, fn: 38, offset_bias_frames: 2, offset_jitter_frames: 4, ...over,
});

const versions = [run(1, 52.1, 58, 47), run(2, 61.8, 66, 58), run(3, 66.2, 70, 63), run(4, 71.4, 74, 69, { tolerance_frames: 10 })];

// F1 / precision / recall across pipeline versions; click a point to select it.
export const Versions = () => {
  const [sel, setSel] = useState(4);
  return <div style={{ width: 680 }}><VersionTrendChart versions={versions} selectedId={sel} onSelect={setSel} /></div>;
};
