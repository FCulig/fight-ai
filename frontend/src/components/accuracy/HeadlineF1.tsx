import AccGauge from '../player/AccGauge';
import MiniStat from '../player/MiniStat';
import type { EvalRunSummary } from '../../types/EvalRun';
import ChangeTile from './ChangeTile';

interface HeadlineF1Props {
  /** The version currently being viewed — not necessarily the latest one. */
  current: EvalRunSummary;
  /** The version immediately before `current`, chronologically by pipeline
   * version — null when `current` is v1 (nothing to compare against). */
  previous: EvalRunSummary | null;
}

/** Section E1 — the headline stat group: F1 ring, P/R/TP/FP/FN/n tiles, and
 * the change-vs-previous-version tile. Reuses the Player's AccGauge/MiniStat
 * rather than inventing new stat primitives. */
export default function HeadlineF1({ current, previous }: HeadlineF1Props) {
  const labelled = (current.tp ?? 0) + (current.fn ?? 0);
  const predicted = (current.tp ?? 0) + (current.fp ?? 0);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr 1fr', gap: 14, alignItems: 'stretch' }}>
      <div className="inner-tile" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
        <AccGauge pct={Math.round(current.f1 ?? 0)} color="var(--cyan-400)" label="Strike F1" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-tertiary)', fontVariantNumeric: 'tabular-nums' }}>
            P {current.precision}% · R {current.recall}%
          </span>
          <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
            TP {current.tp} · FP {current.fp} · FN {current.fn}
          </span>
          <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)' }}>
            {labelled} labelled · {predicted} predicted
          </span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <MiniStat value={`${current.offset_bias_frames ?? '—'}${current.offset_bias_frames != null ? 'f' : ''}`} label="Timing bias" />
        <MiniStat value={`${current.offset_jitter_frames ?? '—'}${current.offset_jitter_frames != null ? 'f' : ''}`} label="Timing jitter" />
        <MiniStat value={current.scored_minutes.toFixed(1)} label="Minutes scored" />
      </div>
      <ChangeTile current={current} previous={previous} />
    </div>
  );
}
