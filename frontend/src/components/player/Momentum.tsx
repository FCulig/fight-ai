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
}

export default function Momentum({ time, duration, r1EndSeconds, events, fps, fighters, redFighterId }: MomentumProps) {
  const d = duration > 0 ? duration : DURATION;
  const r1 = r1EndSeconds > 0 ? r1EndSeconds : R1_END;
  const pace = derivePaceBuckets(events, fps, d, redFighterId);
  return (
    <div className="glass" style={{ marginTop: 16, padding: '22px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14, gap: 12, flexWrap: 'wrap' }}>
        <span className="font-display" style={{ fontSize: 34, letterSpacing: '0.04em', color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>MOMENTUM</span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>Significant strikes landed across the fight</span>
        <div style={{ display: 'flex', gap: 16, fontSize: 11.5, fontWeight: 700 }}>
          <span style={{ color: 'var(--f-red)' }}>{fighters.red.name}</span>
          <span style={{ color: 'var(--f-blue)' }}>{fighters.blue.name}</span>
        </div>
      </div>
      <PaceChart time={time} duration={d} r1End={r1} height={150} redPace={pace.red} bluePace={pace.blue} />
    </div>
  );
}
