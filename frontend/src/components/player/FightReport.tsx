import { useState } from 'react';
import { useWindowWidth } from '../../hooks/useWindowWidth';
import ScopeToggle from './ScopeToggle';
import type { Scope } from './ScopeToggle';
import SummaryTiles from './SummaryTiles';
import FightBreakdown from './FightBreakdown';
import type { FighterProfile, FighterStats } from '../../mocks/fightMock';
import type { Event } from '../../types/Event';
import type { Round } from '../../types/Round';
import { deriveStatsForRange } from '../../utils/liveStats';

interface FightReportProps {
  currentFrame: number;
  events: Event[];
  fps: number;
  rounds: Round[];
  fighters: { red: FighterProfile; blue: FighterProfile };
  redFighterId?: number | null;
}

/** One real-data sentence in place of the design's hand-written fight
 * narrative — built entirely from the same FighterStats every tile on this
 * page already derives from real events, never a fabricated storyline. */
function summarize(red: FighterStats, blue: FighterStats, redName: string, blueName: string): string {
  if (red.sig[1] + blue.sig[1] === 0) return 'No strikes logged yet for this scope.';
  const clauses: string[] = [];
  if (red.sig[0] !== blue.sig[0]) {
    const [wName, wSig, lSig] = red.sig[0] > blue.sig[0] ? [redName, red.sig[0], blue.sig[0]] : [blueName, blue.sig[0], red.sig[0]];
    clauses.push(`${wName} out-landed the opponent ${wSig}–${lSig} in significant strikes`);
  } else {
    clauses.push(`${redName} and ${blueName} landed an even ${red.sig[0]} significant strikes apiece`);
  }
  if (red.ctrl + blue.ctrl > 0) {
    const [cName, cSec] = red.ctrl >= blue.ctrl ? [redName, red.ctrl] : [blueName, blue.ctrl];
    clauses.push(`${cName} controlled ${Math.round(cSec / 60)} min of mat time`);
  }
  if (red.kd + blue.kd > 0) {
    const kName = red.kd > blue.kd ? redName : blueName;
    clauses.push(`${kName} scored the only knockdown`);
  }
  return clauses.join('. ') + '.';
}

export default function FightReport({ currentFrame, events, fps, rounds, fighters, redFighterId }: FightReportProps) {
  const [scope, setScope] = useState<Scope>('fight');
  const width = useWindowWidth();
  const narrow = width < 1100;

  let st: { red: FighterStats; blue: FighterStats };
  let scopeLabel: string;
  if (scope === 'live') {
    st = deriveStatsForRange(events, 0, currentFrame, fps, redFighterId);
    scopeLabel = 'the fight so far';
  } else if (scope === 'fight') {
    st = deriveStatsForRange(events, 0, Infinity, fps, redFighterId);
    scopeLabel = 'the fight';
  } else {
    const round = rounds.find(r => r.round_number === scope);
    st = round
      ? deriveStatsForRange(events, round.start_frame, round.end_frame, fps, redFighterId)
      : deriveStatsForRange(events, 0, Infinity, fps, redFighterId);
    scopeLabel = `round ${scope}`;
  }

  const redName = fighters.red.name, blueName = fighters.blue.name;

  return (
    <section style={{ marginTop: 56 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 20, flexWrap: 'wrap', marginBottom: 22 }}>
        <div style={{ minWidth: 0 }}>
          <span className="eyebrow">Report</span>
          <h2 className="font-display" style={{ fontSize: 'clamp(28px, 3.4vw, 40px)', lineHeight: 1, margin: '10px 0 0', color: 'var(--text-primary)' }}>
            The whole fight, broken down.
          </h2>
          <p style={{ margin: '10px 0 0', fontSize: 14, fontWeight: 500, color: 'var(--text-muted)', maxWidth: '52ch' }}>
            {summarize(st.red, st.blue, redName, blueName)}
          </p>
        </div>
        <div style={{ marginLeft: 'auto' }}>
          <ScopeToggle scope={scope} setScope={setScope} rounds={rounds} />
        </div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <SummaryTiles red={st.red} blue={st.blue} redName={redName} blueName={blueName} scopeLabel={scopeLabel} />
      </div>

      <FightBreakdown fighters={fighters} red={st.red} blue={st.blue} narrow={narrow} />

    </section>
  );
}
