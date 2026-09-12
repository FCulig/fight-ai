import { useState } from 'react';
import { useWindowWidth } from '../../hooks/useWindowWidth';
import ScopeToggle from './ScopeToggle';
import type { Scope } from './ScopeToggle';
import FighterColumn from './FighterColumn';
import type { FighterProfile, ScopeStats } from '../../mocks/fightMock';
import type { Event } from '../../types/Event';
import type { Round } from '../../types/Round';
import { deriveStatsForRange } from '../../utils/liveStats';

interface Props {
  currentFrame: number;
  events: Event[];
  fps: number;
  rounds: Round[];
  fighters: { red: FighterProfile; blue: FighterProfile };
}

export default function FightStatistics({ currentFrame, events, fps, rounds, fighters }: Props) {
  const [scope, setScope] = useState<Scope>('fight');
  const width = useWindowWidth();
  const cols = width < 1100 ? '1fr' : '1fr 1fr';

  let st: ScopeStats;
  if (scope === 'live') {
    st = deriveStatsForRange(events, 0, currentFrame, fps);
  } else if (scope === 'fight') {
    st = deriveStatsForRange(events, 0, Infinity, fps);
  } else {
    // round number — scope to that round's frame range, fall back to fight-wide if unknown
    const round = rounds.find(r => r.round_number === scope);
    st = round
      ? deriveStatsForRange(events, round.start_frame, round.end_frame, fps)
      : deriveStatsForRange(events, 0, Infinity, fps);
  }

  return (
    <>
      <div className="glass" style={{ marginTop: 16, padding: '14px 22px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 18, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 20, color: 'var(--accent)' }}>monitoring</span>
          <span className="font-display" style={{ fontSize: 26, color: 'var(--text-primary)', letterSpacing: '0.04em' }}>FIGHT STATISTICS</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="label">Scope</span>
          <ScopeToggle scope={scope} setScope={setScope} rounds={rounds} />
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 16, marginTop: 16 }}>
        <FighterColumn f={fighters.red} s={st.red} />
        <FighterColumn f={fighters.blue} s={st.blue} />
      </div>
    </>
  );
}
