import { useState } from 'react';
import { useWindowWidth } from '../../hooks/useWindowWidth';
import ScopeToggle from './ScopeToggle';
import type { Scope } from './ScopeToggle';
import FighterColumn from './FighterColumn';
import SummaryTiles from './SummaryTiles';
import HeadToHead from './HeadToHead';
import Momentum from './Momentum';
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
  time: number;
  duration: number;
  r1EndSeconds: number;
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

export default function FightReport({ currentFrame, events, fps, rounds, fighters, redFighterId, time, duration, r1EndSeconds }: FightReportProps) {
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
          <p style={{ margin: '10px 0 0', fontSize: 14, fontWeight: 600, color: 'var(--text-muted)', maxWidth: '52ch' }}>
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

      <div style={{ display: 'grid', gridTemplateColumns: narrow ? 'minmax(0,1fr)' : 'minmax(0,1fr) minmax(0,1fr)', gap: 12 }}>
        <HeadToHead red={st.red} blue={st.blue} redName={redName} blueName={blueName} />
        <div style={{ display: 'grid', gap: 12 }}>
          <FighterColumn f={fighters.red} s={st.red} />
          <FighterColumn f={fighters.blue} s={st.blue} />
        </div>
      </div>

      <div className="glass" style={{ marginTop: 12, padding: '22px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, flexWrap: 'wrap', marginBottom: 18 }}>
          <h3 style={{ margin: 0, fontSize: 22, fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>Momentum.</h3>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)' }}>Significant strikes landed per 30 seconds</span>
          <span style={{ display: 'flex', gap: 16, fontSize: 11.5, fontWeight: 700, marginLeft: 'auto' }}>
            <span style={{ color: 'var(--f-red)' }}>{redName}</span>
            <span style={{ color: 'var(--f-blue)' }}>{blueName}</span>
          </span>
        </div>
        <Momentum time={time} duration={duration} r1EndSeconds={r1EndSeconds} events={events} fps={fps} fighters={fighters} redFighterId={redFighterId} bare />
      </div>
    </section>
  );
}
