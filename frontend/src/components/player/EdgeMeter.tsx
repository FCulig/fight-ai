export interface EdgeTape {
  label: string;
  r: string | number;
  b: string | number;
  lowerWins?: boolean;
}

function tapeNum(v: string | number): number {
  if (typeof v === 'number') return v;
  const ft = /(\d+)'(\d+)/.exec(v);
  if (ft) return (+ft[1]) * 12 + (+ft[2]);
  const inch = /(\d+)"/.exec(v);
  if (inch) return +inch[1];
  return parseFloat(v) || 0;
}

function tapeDelta(t: EdgeTape) {
  const rn = tapeNum(t.r), bn = tapeNum(t.b);
  const rWin = t.lowerWins ? rn < bn : rn > bn;
  const bWin = t.lowerWins ? bn < rn : bn > rn;
  const diff = Math.abs(rn - bn);
  const unit = t.label === 'Age' ? (diff === 1 ? ' yr' : ' yrs') : '"';
  const winnerColor = rWin ? 'var(--f-red)' : (bWin ? 'var(--f-blue)' : 'var(--text-disabled)');
  return { rWin, bWin, diff, unit, winnerColor };
}

export function EdgeRow({ t }: { t: EdgeTape }) {
  const { rWin, bWin, diff, unit, winnerColor } = tapeDelta(t);
  const lean = Math.min(diff / 8, 1) * 50;
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '58px 1fr 58px', alignItems: 'center', gap: 16 }}>
        <span className="font-display" style={{ fontSize: 23, textAlign: 'right', color: rWin ? 'var(--f-red)' : 'var(--text-tertiary)' }}>{t.r}</span>
        <div>
          <div style={{ textAlign: 'center', fontSize: 9.5, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase' as const, color: 'var(--text-muted)', marginBottom: 7 }}>
            {t.label}
          </div>
          <div style={{ position: 'relative', height: 12 }}>
            <div style={{ position: 'absolute', inset: 0, borderRadius: 6, background: 'var(--surface-inner)', border: '1px solid var(--border-subtle)' }} />
            <div style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', width: 1, background: 'var(--border-glass)' }} />
            {diff > 0 && (
              <div style={{ position: 'absolute', top: 1, bottom: 1, left: rWin ? `${50 - lean}%` : '50%', width: `${lean}%`, borderRadius: 6, background: winnerColor, boxShadow: `0 0 10px ${winnerColor}` }} />
            )}
          </div>
          <div style={{ textAlign: 'center', marginTop: 7, fontSize: 10, fontWeight: 800, letterSpacing: '0.04em', color: winnerColor }}>
            {diff > 0 ? `+${diff}${unit}` : 'EVEN'}
          </div>
        </div>
        <span className="font-display" style={{ fontSize: 23, textAlign: 'left', color: bWin ? 'var(--f-blue)' : 'var(--text-tertiary)' }}>{t.b}</span>
      </div>
    </div>
  );
}
