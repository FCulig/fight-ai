import { useState } from 'react';
import { useWindowWidth } from '../../hooks/useWindowWidth';
import ScopeToggle from './ScopeToggle';
import type { Scope } from './ScopeToggle';
import FighterColumn from './FighterColumn';
import { stats } from '../../mocks/fightMock';
import type { ScopeStats } from '../../mocks/fightMock';
import type { Event } from '../../types/Event';
import type { Round } from '../../types/Round';
import { deriveLiveStats } from '../../utils/liveStats';

interface Props {
  currentFrame: number;
  events: Event[];
  fps: number;
  rounds: Round[];
}

export default function FightStatistics({ currentFrame, events, fps, rounds }: Props) {
  const [scope, setScope] = useState<Scope>('fight');
  const width = useWindowWidth();
  const cols = width < 1100 ? '1fr' : '1fr 1fr';

  let st: ScopeStats;
  if (scope === 'live') {
    st = deriveLiveStats(events, currentFrame, fps);
  } else if (scope === 'fight') {
    st = stats['fight'];
  } else {
    // round number — fall back to fight-wide if this round isn't in the mock
    st = (stats as Record<string | number, ScopeStats>)[scope] ?? stats['fight'];
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
        <FighterColumn corner="red" s={st.red} />
        <FighterColumn corner="blue" s={st.blue} />
      </div>
    </>
  );
}
