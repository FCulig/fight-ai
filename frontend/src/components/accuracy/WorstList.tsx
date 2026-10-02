import type { LabelStrike, PredictedStrikeItem } from '../../types/EvalRun';

interface WorstListProps {
  title: string;
  fps: number;
  items: (LabelStrike | PredictedStrikeItem)[];
  emptyLabel: string;
  limit?: number;
}

const fmtClock = (frame: number, fps: number) => {
  const t = frame / fps;
  const m = Math.floor(t / 60);
  const s = (t % 60).toFixed(2).padStart(5, '0');
  return `${m}:${s}`;
};

/** Section E9 — worst misses (false negatives) / false positives, the
 * review queue. Shared by both lists — same row shape either side. */
export default function WorstList({ title, fps, items, emptyLabel, limit = 8 }: WorstListProps) {
  const shown = items.slice(0, limit);
  return (
    <div>
      <div className="label" style={{ marginBottom: 9 }}>{title} ({items.length})</div>
      {shown.length === 0 ? (
        <div style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-muted)' }}>{emptyLabel}</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {shown.map((it, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 9, padding: '7px 10px',
              borderRadius: 8, background: 'rgba(0,0,0,0.24)', border: '1px solid var(--border-subtle)',
              fontSize: 11.5, fontWeight: 500, fontVariantNumeric: 'tabular-nums',
            }}>
              <span style={{ color: 'var(--text-muted)', minWidth: 62 }}>{fmtClock(it.frame, fps)}</span>
              <span style={{
                width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                background: it.fighter === 'red' ? 'var(--f-red)' : 'var(--f-blue)',
              }} title={it.fighter} />
              <span style={{ color: 'var(--text-secondary)' }}>
                {'action' in it ? it.action : `${it.family}_${it.target}`}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
