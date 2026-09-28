import type { FighterStats } from '../../mocks/fightMock';
import { ctrlFmt } from '../../mocks/fightMock';

interface CmpRowProps {
  label: string;
  r: number;
  b: number;
  fmt?: (v: number) => string;
}

function CmpRow({ label, r, b, fmt }: CmpRowProps) {
  const d = (x: number) => (fmt ? fmt(x) : x);
  const rWin = r > b, bWin = b > r;
  const max = Math.max(r, b, 0.001);
  return (
    <div style={{ padding: '13px 0', borderTop: '1px solid var(--border-subtle)' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'auto minmax(0,1fr) auto', gap: 14, alignItems: 'baseline' }}>
        <span className="font-display" style={{ fontSize: 24, letterSpacing: '-0.03em', color: rWin ? 'var(--text-primary)' : 'var(--text-muted)' }}>{d(r)}</span>
        <span style={{ textAlign: 'center', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>{label}</span>
        <span className="font-display" style={{ fontSize: 24, letterSpacing: '-0.03em', textAlign: 'right', color: bWin ? 'var(--text-primary)' : 'var(--text-muted)' }}>{d(b)}</span>
      </div>
      <div style={{ display: 'flex', gap: 3, height: 6, marginTop: 8 }}>
        <div style={{ flexGrow: Math.max(r, 0.001) / max, height: '100%', borderRadius: 3, background: 'var(--f-red)' }} />
        <div style={{ flexGrow: Math.max(b, 0.001) / max, height: '100%', borderRadius: 3, background: 'var(--f-blue)' }} />
      </div>
    </div>
  );
}

interface HeadToHeadProps {
  red: FighterStats;
  blue: FighterStats;
  redName: string;
  blueName: string;
}

/** Mirrored red-vs-blue comparison — the design's "Head to head" card. Same
 * per-fighter FighterStats as SummaryTiles/FighterColumn, just paired up
 * instead of shown per-fighter. */
export default function HeadToHead({ red, blue, redName, blueName }: HeadToHeadProps) {
  return (
    <div className="glass" style={{ padding: 22 }}>
      <h3 style={{ margin: 0, fontSize: 22, fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>Head to head.</h3>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, margin: '16px 0 4px', fontSize: 13, fontWeight: 800, color: 'var(--text-primary)' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <i style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--f-red)', display: 'block' }} />{redName}
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          {blueName}<i style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--f-blue)', display: 'block' }} />
        </span>
      </div>
      <CmpRow label="Significant strikes" r={red.sig[0]} b={blue.sig[0]} />
      <CmpRow label="Total strikes" r={red.total[0]} b={blue.total[0]} />
      <CmpRow label="Takedowns landed" r={red.td[0]} b={blue.td[0]} />
      <CmpRow label="Control time" r={red.ctrl} b={blue.ctrl} fmt={ctrlFmt} />
      <CmpRow label="Knockdowns" r={red.kd} b={blue.kd} />
      <CmpRow label="Submission attempts" r={red.sub} b={blue.sub} />
    </div>
  );
}
