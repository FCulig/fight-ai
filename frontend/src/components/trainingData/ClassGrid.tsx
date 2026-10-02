import type { QAEvent } from '../../hooks/useTrainingDataEvents';
import { TRAINING_CLASSES } from '../../utils/trainingDataTaxonomy';
import { classStats } from '../../utils/trainingDataStats';

interface ClassGridProps {
  eventsByAction: Map<string, QAEvent[]>;
  onOpen: (action: string) => void;
  narrow?: boolean;
}

const COLUMNS = '34px minmax(0, 1.4fr) minmax(0, 1fr) 70px minmax(120px, 1.6fr) 84px 76px 92px 20px';
const num: React.CSSProperties = { fontFamily: 'var(--mono)', fontSize: 12.5, fontVariantNumeric: 'tabular-nums', textAlign: 'right' };

/**
 * Every training class as one row, the classes with the most events still
 * waiting for a verdict first, so "what needs review?" is the top of the table.
 * Classes with no events yet sink to the bottom.
 */
export default function ClassGrid({ eventsByAction, onOpen, narrow }: ClassGridProps) {
  const rows = TRAINING_CLASSES
    .map((c, i) => ({ c, i, s: classStats(eventsByAction.get(c.action) ?? []) }))
    .sort((a, b) => Number(b.s.total > 0) - Number(a.s.total > 0) || b.s.pending - a.s.pending || a.i - b.i);

  return (
    <div className="glass" style={{ overflow: 'hidden' }}>
      {!narrow && (
        <div style={{ display: 'grid', gridTemplateColumns: COLUMNS, gap: 14, alignItems: 'center', padding: '11px 18px', borderBottom: '1px solid var(--border-glass)' }}>
          <span className="label">Key</span>
          <span className="label">Class</span>
          <span className="label">Group</span>
          <span className="label" style={{ textAlign: 'right' }}>Events</span>
          <span className="label">Reviewed</span>
          <span className="label" style={{ textAlign: 'right' }}>Confirmed</span>
          <span className="label" style={{ textAlign: 'right' }}>Declined</span>
          <span className="label" style={{ textAlign: 'right' }}>Pending</span>
          <span />
        </div>
      )}
      {rows.map(({ c, s }, row) => {
        const empty = s.total === 0;
        const bar = empty ? <span /> : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <div style={{ flex: 1, display: 'flex', gap: 2, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
              <div style={{ background: 'var(--green-500)', width: `${(s.confirmed / s.total) * 100}%` }} />
              <div style={{ background: 'var(--red-500)', width: `${(s.declined / s.total) * 100}%` }} />
            </div>
            <span style={{ ...num, fontSize: 11.5, color: 'var(--text-muted)', minWidth: '7ch' }}>{s.reviewed}/{s.total}</span>
          </div>
        );
        const pending = empty ? (
          <span style={{ fontSize: 12, color: 'var(--text-disabled)', textAlign: 'right', whiteSpace: 'nowrap' }}>No events yet</span>
        ) : s.pending > 0 ? (
          <span style={{ ...num, fontSize: 13.5, fontWeight: 600, color: 'var(--text-primary)' }}>{s.pending}</span>
        ) : (
          <span style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'flex-end', gap: 5, fontSize: 12, fontWeight: 500, color: 'var(--green-500)' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>check_circle</span>Done
          </span>
        );
        const name = (
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.name}</span>
        );
        return (
          <button
            key={c.action}
            type="button"
            className="td-class"
            onClick={() => onOpen(c.action)}
            disabled={empty}
            style={{
              display: 'grid', gridTemplateColumns: narrow ? '34px minmax(0, 1fr) auto 20px' : COLUMNS, gap: narrow ? 12 : 14, alignItems: 'center',
              width: '100%', padding: narrow ? '12px 14px' : '12px 18px', textAlign: 'left', fontFamily: 'inherit',
              background: 'transparent', border: 'none', borderRadius: 0,
              borderTop: row > 0 ? '1px solid var(--border-subtle)' : 'none',
              cursor: empty ? 'default' : 'pointer', opacity: empty ? 0.45 : 1,
            }}
          >
            <span className="kbd">{c.key}</span>
            {narrow ? (
              <>
                <div style={{ minWidth: 0, display: 'grid', gap: 7 }}>
                  {name}
                  {bar}
                </div>
                {pending}
              </>
            ) : (
              <>
                {name}
                <span style={{ fontSize: 12.5, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.group}</span>
                <span style={{ ...num, color: empty ? 'var(--text-disabled)' : 'var(--text-primary)' }}>{s.total}</span>
                {bar}
                <span style={{ ...num, color: 'var(--text-secondary)' }}>{empty ? '' : s.confirmed}</span>
                <span style={{ ...num, color: s.declined > 0 ? 'var(--text-secondary)' : 'var(--text-disabled)' }}>{empty ? '' : s.declined}</span>
                {pending}
              </>
            )}
            <span className="material-symbols-outlined" style={{ fontSize: 17, color: 'var(--text-disabled)', visibility: empty ? 'hidden' : 'visible' }}>chevron_right</span>
          </button>
        );
      })}
    </div>
  );
}
