import { Fragment } from 'react';

interface ConfusionHeatmapProps {
  /** Keyed `"<truth>>predicted>"` → count. */
  confusion: Record<string, number>;
  emptyLabel?: string;
}

const ramp = (t: number) => `color-mix(in srgb, var(--accent) ${8 + Math.max(0, Math.min(1, t)) * 84}%, #0b1417)`;
const rampInk = (t: number) => (t > 0.55 ? '#04181c' : '#f1f5f9');

/**
 * Shared truth-rows × predicted-columns heatmap — Section E4 (strike family
 * confusion) and E6 (STRIKING/CLINCH/GROUND confusion) both use this, keyed
 * by whichever taxonomy applies. Row/column labels are derived from the
 * confusion dict itself rather than a hardcoded taxonomy list, so it stays
 * correct as ai/eval/schema.py's FAMILIES/STATES evolve.
 */
export default function ConfusionHeatmap({ confusion, emptyLabel = 'No matched pairs yet.' }: ConfusionHeatmapProps) {
  const entries = Object.entries(confusion).filter(([, n]) => n > 0);
  if (entries.length === 0) {
    return <div style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)' }}>{emptyLabel}</div>;
  }

  const truths = new Set<string>();
  const preds = new Set<string>();
  const cell = new Map<string, number>();
  for (const [key, n] of entries) {
    const idx = key.indexOf('>');
    const t = key.slice(0, idx);
    const p = key.slice(idx + 1);
    truths.add(t);
    preds.add(p);
    cell.set(key, n);
  }
  const rows = Array.from(truths).sort();
  const cols = Array.from(preds).sort();
  const max = Math.max(...entries.map(([, n]) => n));

  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ display: 'grid', gridTemplateColumns: `84px repeat(${cols.length}, minmax(48px, 1fr))`, gap: 5, minWidth: 84 + cols.length * 52 }}>
        <span />
        {cols.map((c) => (
          <span key={c} style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textAlign: 'center' }}>{c}</span>
        ))}
        {rows.map((r) => (
          <Fragment key={r}>
            <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-muted)', alignSelf: 'center' }}>{r}</span>
            {cols.map((c) => {
              const n = cell.get(`${r}>${c}`) ?? 0;
              const t = max ? n / max : 0;
              const diag = r === c;
              return (
                <div key={`${r}-${c}`} title={`${r} → ${c}: ${n}`} style={{
                  height: 32, borderRadius: 6, display: 'grid', placeItems: 'center',
                  background: n ? ramp(t) : 'rgba(255,255,255,0.02)',
                  border: '1px solid rgba(255,255,255,0.05)',
                }}>
                  <span style={{
                    fontSize: 12, fontWeight: diag ? 800 : 600, fontVariantNumeric: 'tabular-nums',
                    color: n ? rampInk(t) : 'var(--text-disabled)',
                  }}>{n || 0}</span>
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
