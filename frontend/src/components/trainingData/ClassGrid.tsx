import type { QAEvent } from '../../hooks/useTrainingDataEvents';
import { TRAINING_CLASSES } from '../../utils/trainingDataTaxonomy';
import { classStats } from '../../utils/trainingDataStats';

interface ClassGridProps {
  eventsByAction: Map<string, QAEvent[]>;
  onOpen: (action: string) => void;
}

export default function ClassGrid({ eventsByAction, onOpen }: ClassGridProps) {
  const groups: { name: string; items: typeof TRAINING_CLASSES }[] = [];
  TRAINING_CLASSES.forEach((c) => {
    let g = groups.find((x) => x.name === c.group);
    if (!g) { g = { name: c.group, items: [] }; groups.push(g); }
    g.items.push(c);
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      {groups.map((g) => (
        <section key={g.name}>
          <div className="label" style={{ paddingBottom: 8, marginBottom: 12, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            {g.name}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
            {g.items.map((c) => {
              const evs = eventsByAction.get(c.action) ?? [];
              const s = classStats(evs);
              return (
                <button
                  key={c.action}
                  type="button"
                  className="glass"
                  onClick={() => onOpen(c.action)}
                  disabled={s.total === 0}
                  style={{
                    display: 'flex', flexDirection: 'column', gap: 9, padding: '13px 14px 14px', textAlign: 'left',
                    cursor: s.total === 0 ? 'default' : 'pointer', fontFamily: 'inherit', transition: 'border-color .14s, transform .14s',
                    opacity: s.total === 0 ? 0.45 : 1,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {c.name}
                    </span>
                    <span className="material-symbols-outlined" style={{ fontSize: 17, color: 'var(--text-disabled)', marginLeft: 'auto' }}>chevron_right</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span className="font-display" style={{ fontSize: 24, lineHeight: 1, color: 'var(--text-primary)' }}>{s.total}</span>
                    <span style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)' }}>events</span>
                  </div>
                  {s.total > 0 && (
                    <div style={{ display: 'flex', gap: 2, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                      <div style={{ background: '#0ca30c', width: `${(s.confirmed / s.total) * 100}%` }} />
                      <div style={{ background: '#ef4444', width: `${(s.declined / s.total) * 100}%` }} />
                    </div>
                  )}
                  <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--text-muted)' }}>
                    {s.total === 0 ? 'No events yet' : s.reviewed === 0 ? 'Not reviewed' : `${s.reviewed}/${s.total} reviewed`}
                    {s.declined > 0 && <span style={{ color: '#ef4444' }}> · {s.declined} declined</span>}
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
