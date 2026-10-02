import { useMemo, useState } from 'react';
import type { QAEvent } from '../../hooks/useTrainingDataEvents';
import type { TrainingClass } from '../../utils/trainingDataTaxonomy';
import { formatFrameClock } from '../annotate/taxonomy';
import { fightLabel } from '../../utils/fightLabel';
import VerdictBadge from './VerdictBadge';
import { classStats, verdictKey } from '../../utils/trainingDataStats';

const CORNER_C: Record<number, string> = { 0: 'var(--f-red)', 1: 'var(--f-blue)' };
const FILTERS = ['All', 'Pending', 'Confirmed', 'Declined'] as const;
const ALL_FIGHTS = 'All fights';

interface EventTableProps {
  cls: TrainingClass;
  events: QAEvent[];
  onBack: () => void;
  onOpen: (id: number) => void;
}

export default function EventTable({ cls, events, onBack, onOpen }: EventTableProps) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('All');
  const [fightId, setFightId] = useState<number | typeof ALL_FIGHTS>(ALL_FIGHTS);

  const s = classStats(events);

  const fightOptions = useMemo(() => {
    const seen = new Map<number, string>();
    events.forEach((e) => { if (!seen.has(e.fight.id)) seen.set(e.fight.id, fightLabel(e.fight)); });
    return [...seen.entries()];
  }, [events]);

  const rows = events
    .filter((e) => {
      const v = verdictKey(e.is_verified);
      if (filter === 'Pending' && v !== 'pending') return false;
      if (filter === 'Confirmed' && v !== 'confirmed') return false;
      if (filter === 'Declined' && v !== 'declined') return false;
      if (fightId !== ALL_FIGHTS && e.fight.id !== fightId) return false;
      return true;
    })
    .sort((a, b) => (a.fight.id === b.fight.id ? a.frame - b.frame : a.fight.id - b.fight.id));

  const firstPending = events.find((e) => e.is_verified == null);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 14, flexWrap: 'wrap' }}>
        <button type="button" className="btn-glass" onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', fontSize: 11.5, fontWeight: 600 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 15 }}>arrow_back</span>All classes
        </button>
        <span style={{ color: 'var(--text-disabled)', fontSize: 12 }}>/</span>
        <span style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-secondary)' }}>{cls.name}</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 18, flexWrap: 'wrap', marginBottom: 16 }}>
        <div style={{ minWidth: 0 }}>
          <h1 className="font-display" style={{ fontSize: 32, lineHeight: 0.94, margin: 0, color: 'var(--text-primary)' }}>{cls.name}</h1>
          <p style={{ margin: '5px 0 0', fontSize: 12.5, fontWeight: 500, color: 'var(--text-muted)' }}>
            {s.total} labelled events · exports as <code style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--text-primary)' }}>{cls.action}</code>
          </p>
        </div>
        <button
          type="button"
          className="btn-primary"
          disabled={!firstPending}
          onClick={() => firstPending && onOpen(firstPending.id)}
          style={{
            marginLeft: 'auto',
            fontWeight: 600, fontSize: 13, padding: '9px 16px',
            display: 'inline-flex', alignItems: 'center', gap: 6,
            opacity: firstPending ? 1 : 0.45,
            cursor: firstPending ? 'pointer' : 'default', fontFamily: 'inherit',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>play_arrow</span>
          {s.pending ? `Review ${s.pending} pending` : 'All reviewed'}
        </button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 11, flexWrap: 'wrap', padding: '9px 12px', marginBottom: 14, borderRadius: 8, background: 'var(--surface-glass)', border: '1px solid var(--border-glass)' }}>
        <div style={{ display: 'flex', gap: 4, padding: 3, borderRadius: 8, background: 'rgba(0,0,0,0.28)', border: '1px solid var(--border-subtle)' }}>
          {FILTERS.map((f) => (
            <button key={f} type="button" className={'pill' + (filter === f ? ' active' : '')} onClick={() => setFilter(f)} style={{ padding: '4px 9px', fontSize: 11 }}>{f}</button>
          ))}
        </div>
        {fightOptions.length > 1 && (
          <>
            <span style={{ width: 1, height: 20, background: 'rgba(255,255,255,0.08)' }} />
            <div style={{ display: 'flex', gap: 4, padding: 3, borderRadius: 8, background: 'rgba(0,0,0,0.28)', border: '1px solid var(--border-subtle)', flexWrap: 'wrap' }}>
              <button type="button" className={'pill' + (fightId === ALL_FIGHTS ? ' active' : '')} onClick={() => setFightId(ALL_FIGHTS)} style={{ padding: '4px 9px', fontSize: 11 }}>{ALL_FIGHTS}</button>
              {fightOptions.map(([id, label]) => (
                <button key={id} type="button" className={'pill' + (fightId === id ? ' active' : '')} onClick={() => setFightId(id)} style={{ padding: '4px 9px', fontSize: 11 }}>{label}</button>
              ))}
            </div>
          </>
        )}
        <span style={{ flex: 1 }} />
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500, color: 'var(--text-muted)' }}>{rows.length} shown</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {rows.map((e) => (
          <button
            key={e.id}
            type="button"
            className="td-row"
            onClick={() => onOpen(e.id)}
            style={{
              display: 'grid', gridTemplateColumns: '74px minmax(0,1fr) auto 18px', gap: 13, alignItems: 'center',
              padding: '10px 16px 10px 12px', borderRadius: 8, background: 'var(--surface-glass)',
              border: '1px solid var(--border-subtle)', cursor: 'pointer', fontFamily: 'inherit', textAlign: 'left',
              transition: 'border-color .12s, background .12s',
            }}
          >
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
              {formatFrameClock(e.frame, e.fight.fps)}
            </span>
            <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
              <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {fightLabel(e.fight)}
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, fontWeight: 400, color: 'var(--text-muted)' }}>
                <span style={{ width: 7, height: 7, borderRadius: 2, background: e.displayCorner != null ? CORNER_C[e.displayCorner] : 'var(--text-disabled)', flexShrink: 0 }} />
                {e.displayCorner === 0 ? 'Red' : e.displayCorner === 1 ? 'Blue' : 'No corner'} · {e.target ?? 'non-specific'}
              </span>
            </span>
            <VerdictBadge isVerified={e.is_verified} sm />
            <span className="material-symbols-outlined" style={{ fontSize: 16, color: 'var(--text-disabled)' }}>chevron_right</span>
          </button>
        ))}
        {rows.length === 0 && (
          <div style={{ padding: 26, textAlign: 'center', fontSize: 12, fontWeight: 500, color: 'var(--text-muted)' }}>
            No events match this filter.
          </div>
        )}
      </div>
    </div>
  );
}
