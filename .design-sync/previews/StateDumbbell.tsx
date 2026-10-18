import { StateDumbbell } from 'fightlytics';

const state = (over: object) => ({
  frames_scored: 26250, frames_correct: 21780, confusion: {},
  gt_transitions_per_min: 1.4, pred_transitions_per_min: 1.9,
  gt_median_dwell_secs: 38.5, pred_median_dwell_secs: 29.2, ...over,
});

// Truth (purple) vs predicted (orange) for fight-state stability.
export const Stable = () => <div style={{ width: 460 }}><StateDumbbell state={state({})} /></div>;

// Predicted state flapping far faster than reality raises the warning.
export const Flapping = () => (
  <div style={{ width: 460 }}><StateDumbbell state={state({ pred_transitions_per_min: 6.8, pred_median_dwell_secs: 6.1 })} /></div>
);
