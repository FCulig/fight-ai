import PaceChart from './PaceChart';
import { DURATION, R1_END } from '../../mocks/fightMock';
import type { FighterProfile } from '../../mocks/fightMock';
import type { Event } from '../../types/Event';
import { derivePaceBuckets } from '../../utils/liveStats';

interface MomentumProps {
  time: number;
  duration: number;
  r1EndSeconds: number;
  events: Event[];
  fps: number;
  fighters: { red: FighterProfile; blue: FighterProfile };
  redFighterId?: number | null;
  /** Skip the card chrome + header — used when a parent (FightReport) already
   * renders its own header above the chart. */
  bare?: boolean;
  height?: number;
}

export default function Momentum({ time, duration, r1EndSeconds, events, fps, fighters, redFighterId, bare, height = 150 }: MomentumProps) {
  const d = duration > 0 ? duration : DURATION;
  const r1 = r1EndSeconds > 0 ? r1EndSeconds : R1_END;
  const pace = derivePaceBuckets(events, fps, d, redFighterId);
  const chart = <PaceChart time={time} duration={d} r1End={r1} height={height} redPace={pace.red} bluePace={pace.blue} />;
  if (bare) return chart;
  return (
    <div className="glass" style={{ marginTop: 16, padding: '22px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14, gap: 12, flexWrap: 'wrap' }}>
        <span className="font-display" style={{ fontSize: 28, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>Momentum.</span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>Significant strikes landed across the fight</span>
        <div style={{ display: 'flex', gap: 16, fontSize: 11.5, fontWeight: 600 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, color: 'var(--text-secondary)' }}><i style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--f-red)', display: 'block' }} />{fighters.red.name}</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, color: 'var(--text-secondary)' }}><i style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--f-blue)', display: 'block' }} />{fighters.blue.name}</span>
        </div>
      </div>
      {chart}
    </div>
  );
}
