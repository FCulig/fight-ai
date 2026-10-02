import SegBar from './SegBar';
import { ctrlFmt } from '../../mocks/fightMock';
import type { FighterProfile, FighterStats } from '../../mocks/fightMock';

interface MirrorRowProps {
  label: string;
  /** What decides the bar length and the winner. */
  r: number;
  b: number;
  /** What is printed, when it differs from the raw number (a clock, "3/5", a percentage). */
  show?: (v: number, side: 'r' | 'b') => string;
  /** Scale both bars to this instead of the larger of the two (accuracy uses 100). */
  max?: number;
  sub?: [string, string];
  labelWidth: number;
  /** Fixed, so every row's bars start at the same x. */
  valueWidth: number;
}

/** One metric, red growing left from the centre label and blue growing right. */
function MirrorRow({ label, r, b, show, max, sub, labelWidth, valueWidth }: MirrorRowProps) {
  const scale = max ?? Math.max(r, b, 0.001);
  const value = (v: number, side: 'r' | 'b', wins: boolean) => (
    <div style={{ textAlign: side === 'r' ? 'right' : 'left', minWidth: 0 }}>
      <span className="font-num" style={{ fontSize: 19, color: wins ? 'var(--text-primary)' : 'var(--text-muted)' }}>
        {show ? show(v, side) : v}
      </span>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{sub[side === 'r' ? 0 : 1]}</div>}
    </div>
  );
  const bar = (v: number, side: 'r' | 'b') => (
    <div style={{ display: 'flex', justifyContent: side === 'r' ? 'flex-end' : 'flex-start', height: 8 }}>
      <div style={{ width: `${Math.min(100, (v / scale) * 100)}%`, minWidth: v > 0 ? 3 : 0, height: '100%', borderRadius: 2, background: side === 'r' ? 'var(--f-red)' : 'var(--f-blue)' }} />
    </div>
  );
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: `${valueWidth}px minmax(0, 1fr) ${labelWidth}px minmax(0, 1fr) ${valueWidth}px`,
      gap: 12, alignItems: 'center', padding: '11px 0', borderTop: '1px solid var(--border-subtle)',
    }}>
      {value(r, 'r', r > b)}
      {bar(r, 'r')}
      <span style={{ textAlign: 'center', fontSize: 12.5, fontWeight: 500, color: 'var(--text-secondary)', lineHeight: 1.25 }}>{label}</span>
      {bar(b, 'b')}
      {value(b, 'b', b > r)}
    </div>
  );
}

function Name({ f, align }: { f: FighterProfile; align: 'left' | 'right' }) {
  const right = align === 'right';
  return (
    <div style={{ minWidth: 0, textAlign: align }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexDirection: right ? 'row-reverse' : 'row' }}>
        <span style={{ width: 10, height: 10, borderRadius: 2, background: f.color, flexShrink: 0 }} />
        <span className="font-display" style={{ fontSize: 26, lineHeight: 1, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.name}</span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>"{f.nick}" · {f.record} · {f.corner}</div>
    </div>
  );
}

function Split({ title, f, red, blue }: { title: string; f: { red: FighterProfile; blue: FighterProfile }; red: React.ReactNode; blue: React.ReactNode }) {
  const who = (p: FighterProfile) => (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 7 }}>
      <i style={{ width: 8, height: 8, borderRadius: 2, background: p.color, display: 'block' }} />{p.name}
    </span>
  );
  return (
    <div>
      <div className="label" style={{ marginBottom: 11 }}>{title}</div>
      <div style={{ display: 'grid', gap: 14 }}>
        <div>{who(f.red)}{red}</div>
        <div>{who(f.blue)}{blue}</div>
      </div>
    </div>
  );
}

interface FightBreakdownProps {
  fighters: { red: FighterProfile; blue: FighterProfile };
  red: FighterStats;
  blue: FighterStats;
  narrow: boolean;
}

const INK_MID = 'rgba(242,241,238,0.55)';
const INK_LOW = 'rgba(242,241,238,0.28)';

/**
 * The whole per-fighter comparison in one block: every metric once, red on the
 * left and blue on the right, then where each fighter's strikes went. Same
 * FighterStats as SummaryTiles (utils/liveStats.ts deriveStatsForRange).
 */
export default function FightBreakdown({ fighters, red, blue, narrow }: FightBreakdownProps) {
  const sizes = { labelWidth: narrow ? 104 : 150, valueWidth: narrow ? 66 : 92 };
  const target = (s: FighterStats) => (
    <SegBar parts={[
      { val: s.head, color: 'var(--text-primary)', label: 'Head' },
      { val: s.body, color: INK_MID, label: 'Body' },
      { val: s.leg, color: INK_LOW, label: 'Leg' },
    ]} />
  );
  const position = (s: FighterStats) => (
    <SegBar parts={[
      { val: s.distance, color: 'var(--state-striking)', label: 'Distance' },
      { val: s.clinch, color: 'var(--state-clinch)', label: 'Clinch' },
      { val: s.ground, color: 'var(--state-ground)', label: 'Ground' },
    ]} />
  );

  return (
    <div className="glass" style={{ padding: narrow ? '20px 18px' : '22px 24px' }}>
      <h3 className="font-display" style={{ margin: '0 0 18px', fontSize: 24, lineHeight: 1, color: 'var(--text-primary)' }}>Head to head.</h3>
      <div style={{ display: 'grid', gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : 'minmax(0, 1.35fr) minmax(0, 1fr)', gap: narrow ? 26 : 40, alignItems: 'start' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 16, marginBottom: 14 }}>
            <Name f={fighters.red} align="left" />
            <Name f={fighters.blue} align="right" />
          </div>
          <MirrorRow {...sizes} label="Significant strikes" r={red.sig[0]} b={blue.sig[0]} sub={[`of ${red.sig[1]} thrown`, `of ${blue.sig[1]} thrown`]} />
          <MirrorRow {...sizes} label="Accuracy" r={red.acc} b={blue.acc} max={100} show={(v) => `${v}%`} />
          <MirrorRow {...sizes} label="Total strikes" r={red.total[0]} b={blue.total[0]} />
          <MirrorRow {...sizes} label="Takedowns" r={red.td[0]} b={blue.td[0]} show={(_, side) => (side === 'r' ? `${red.td[0]}/${red.td[1]}` : `${blue.td[0]}/${blue.td[1]}`)} />
          <MirrorRow {...sizes} label="Control time" r={red.ctrl} b={blue.ctrl} show={ctrlFmt} />
          <MirrorRow {...sizes} label="Knockdowns" r={red.kd} b={blue.kd} />
          <MirrorRow {...sizes} label="Submission attempts" r={red.sub} b={blue.sub} />
        </div>
        <div style={{ display: 'grid', gap: 24, minWidth: 0, paddingLeft: narrow ? 0 : 40, borderLeft: narrow ? 'none' : '1px solid var(--border-subtle)' }}>
          <Split title="Strikes by target" f={fighters} red={target(red)} blue={target(blue)} />
          <Split title="Strikes by position" f={fighters} red={position(red)} blue={position(blue)} />
        </div>
      </div>
    </div>
  );
}
