import type { EvalReport } from '../../types/EvalRun';

interface StateDumbbellProps {
  state: EvalReport['state'];
}

function Row({ label, truth, pred, unit, max, warn }: { label: string; truth: number; pred: number; unit: string; max: number; warn?: string }) {
  const x = (v: number) => Math.min(100, (v / max) * 100);
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ fontSize: 11, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: 'var(--text-tertiary)' }}>
          truth {truth.toFixed(1)}{unit} · predicted {pred.toFixed(1)}{unit}
        </span>
      </div>
      <div style={{ position: 'relative', height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3 }}>
        <div style={{ position: 'absolute', top: -3, left: `${x(truth)}%`, width: 12, height: 12, borderRadius: '50%', background: 'var(--purple-600)', transform: 'translateX(-50%)' }} title="Truth" />
        <div style={{ position: 'absolute', top: -3, left: `${x(pred)}%`, width: 12, height: 12, borderRadius: '50%', background: 'var(--cyan-400)', transform: 'translateX(-50%)' }} title="Predicted" />
      </div>
      {warn && <div style={{ marginTop: 6, fontSize: 10.5, fontWeight: 700, color: '#fab219' }}>⚠ {warn}</div>}
    </div>
  );
}

/** Section E6 — fight-state leads with stability (transition rate, dwell
 * time), not raw per-frame accuracy, which is dominated by the majority
 * state and hides a flapping state machine (honesty rule 7). */
export default function StateDumbbell({ state }: StateDumbbellProps) {
  const flapping = state.pred_transitions_per_min > 3 * Math.max(state.gt_transitions_per_min, 0.1);
  const accuracy = state.frames_scored > 0 ? (state.frames_correct / state.frames_scored) * 100 : null;

  return (
    <div>
      <Row
        label="Transitions per minute"
        truth={state.gt_transitions_per_min}
        pred={state.pred_transitions_per_min}
        unit="/min"
        max={Math.max(state.gt_transitions_per_min, state.pred_transitions_per_min, 1) * 1.2}
        warn={flapping ? 'predicted state flaps far faster than reality — hysteresis is not holding' : undefined}
      />
      <Row
        label="Median dwell"
        truth={state.gt_median_dwell_secs}
        pred={state.pred_median_dwell_secs}
        unit="s"
        max={Math.max(state.gt_median_dwell_secs, state.pred_median_dwell_secs, 1) * 1.2}
      />
      <div style={{ marginTop: 10, fontSize: 10.5, fontWeight: 600, color: 'var(--text-muted)' }}>
        Per-frame accuracy {accuracy != null ? `${accuracy.toFixed(1)}%` : '—'} ({state.frames_scored} frames) — dominated by the most common state, shown small on purpose.
      </div>
    </div>
  );
}
