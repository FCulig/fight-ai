import { useEffect, useCallback, useState } from 'react';
import type { QAEvent } from '../../hooks/useTrainingDataEvents';
import { TRAINING_CLASSES, type TrainingClass } from '../../utils/trainingDataTaxonomy';
import type { ClassStats } from '../../utils/trainingDataStats';
import { formatFrameClock } from '../annotate/taxonomy';
import { fightLabel } from '../../utils/fightLabel';
import ClipPlayer from './ClipPlayer';
import VerdictBadge from './VerdictBadge';

const CORNER_C: Record<number, string> = { 0: 'var(--f-red)', 1: 'var(--f-blue)' };

// Same grouping ClassGrid/the Annotate palette use, computed once — a
// <select> with <optgroup>s so "retype this strike" reads like the palette
// it was originally logged from, not a flat alphabetical dump.
const TYPE_GROUPS: { name: string; items: TrainingClass[] }[] = (() => {
  const groups: { name: string; items: TrainingClass[] }[] = [];
  TRAINING_CLASSES.forEach((c) => {
    let g = groups.find((x) => x.name === c.group);
    if (!g) { g = { name: c.group, items: [] }; groups.push(g); }
    g.items.push(c);
  });
  return groups;
})();

/** EventReview's "Type" dropdown — retypes a mislabelled strike in place.
 * Saves on change (no separate confirm step); disables itself and shows an
 * inline error if the write fails, same pattern as the rest of Annotate's
 * autosave. */
function TypeSelect({ action, onChange }: { action: string; onChange: (newAction: string) => Promise<void> }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    if (next === action) return;
    setSaving(true);
    setError(null);
    onChange(next)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to save'))
      .finally(() => setSaving(false));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
      <select
        value={action}
        onChange={handleChange}
        disabled={saving}
        style={{
          fontSize: 11.5, fontWeight: 600, color: 'var(--text-secondary)', textAlign: 'right',
          fontFamily: 'inherit', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)',
          borderRadius: 6, padding: '3px 6px', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.6 : 1,
        }}
      >
        {TYPE_GROUPS.map((g) => (
          <optgroup key={g.name} label={g.name}>
            {g.items.map((c) => (
              <option key={c.action} value={c.action} style={{ color: '#000' }}>{c.name}</option>
            ))}
          </optgroup>
        ))}
      </select>
      {error && <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--red-500)' }}>{error}</span>}
    </div>
  );
}

function Meta({ k, v, mono }: { k: string; v: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, padding: '7px 0', borderBottom: '1px solid rgba(255,255,255,0.045)' }}>
      <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-muted)' }}>{k}</span>
      <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', textAlign: 'right', fontFamily: mono ? 'var(--mono)' : 'inherit', fontVariantNumeric: 'tabular-nums' }}>{v}</span>
    </div>
  );
}

interface EventReviewProps {
  event: QAEvent;
  cls: TrainingClass;
  onVerdict: (isVerified: boolean | null) => void;
  onReclassify: (newAction: string) => Promise<void>;
  onBack: () => void;
  onJumpRelative: (delta: 1 | -1) => void;
  onJumpTo: (id: number) => void;
  queue: QAEvent[];
  pos: ClassStats;
  narrow?: boolean;
}

export default function EventReview({ event, cls, onVerdict, onReclassify, onBack, onJumpRelative, onJumpTo, queue, pos, narrow }: EventReviewProps) {
  const v = event.is_verified;

  const act = useCallback((target: boolean) => {
    onVerdict(v === target ? null : target);
  }, [v, onVerdict]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT') return;
      if (e.key === 'c' || e.key === 'C') act(true);
      else if (e.key === 'x' || e.key === 'X') act(false);
      else if (e.key === 'ArrowRight') onJumpRelative(1);
      else if (e.key === 'ArrowLeft') onJumpRelative(-1);
      else if (e.key === 'Escape') onBack();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [act, onJumpRelative, onBack]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: narrow ? 'minmax(0,1fr)' : 'minmax(0,1fr) 330px', gap: 16, alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <div className="glass" style={{ padding: '14px 14px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 11 }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, flexShrink: 0, background: event.displayCorner != null ? CORNER_C[event.displayCorner] : 'var(--text-disabled)' }} />
            <div style={{ minWidth: 0 }}>
              <div className="font-display" style={{ fontSize: 22, lineHeight: 1, color: 'var(--text-primary)' }}>
                {cls.name}{event.target && <span> · {event.target}</span>}
              </div>
              <div style={{ marginTop: 4, fontSize: 12, fontWeight: 400, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                {fightLabel(event.fight)} · {formatFrameClock(event.frame, event.fight.fps)} · f{event.frame}
              </div>
            </div>
          </div>
          <ClipPlayer fight={event.fight} frame={event.frame} corner={event.corner} />
        </div>

        <div className="glass" style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap', padding: '14px 16px' }}>
          <div style={{ minWidth: 0 }}>
            <div className="label" style={{ marginBottom: 5 }}>Is this training-worthy?</div>
            <div style={{ fontSize: 12.5, fontWeight: 400, lineHeight: 1.5, color: 'var(--text-muted)', maxWidth: '44ch' }}>
              Confirm keeps the event in the training export. Decline drops it.
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, marginLeft: 'auto', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => act(false)}
              style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, height: 48, padding: '0 24px', borderRadius: 6,
                fontFamily: 'inherit', fontSize: 15, fontWeight: 600, cursor: 'pointer', border: '1px solid',
                background: v === false ? 'var(--red-500)' : 'rgba(239,68,68,0.12)',
                borderColor: v === false ? 'var(--red-500)' : 'rgba(239,68,68,0.34)',
                color: v === false ? '#2a0606' : '#f87171',
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>Decline
              <kbd style={{ display: 'inline-grid', placeItems: 'center', minWidth: 17, height: 17, borderRadius: 4, background: 'rgba(0,0,0,0.28)', fontSize: 11, fontWeight: 700, fontFamily: 'var(--mono)', opacity: 0.75 }}>X</kbd>
            </button>
            <button
              type="button"
              onClick={() => act(true)}
              style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, height: 48, padding: '0 24px', borderRadius: 6,
                fontFamily: 'inherit', fontSize: 15, fontWeight: 600, cursor: 'pointer', border: '1px solid',
                background: v === true ? 'var(--green-500)' : 'rgba(12,163,12,0.14)',
                borderColor: v === true ? 'var(--green-500)' : 'rgba(12,163,12,0.38)',
                color: v === true ? '#04180a' : '#4ade5e',
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>check</span>Confirm
              <kbd style={{ display: 'inline-grid', placeItems: 'center', minWidth: 17, height: 17, borderRadius: 4, background: 'rgba(0,0,0,0.28)', fontSize: 11, fontWeight: 700, fontFamily: 'var(--mono)', opacity: 0.75 }}>C</kbd>
            </button>
          </div>
        </div>
      </div>

      <aside style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <div className="glass" style={{ padding: '16px 18px 18px' }}>
          <div className="label" style={{ marginBottom: 8 }}>Event</div>
          <Meta k="Verdict" v={<VerdictBadge isVerified={v} sm />} />
          <Meta k="Type" v={<TypeSelect action={event.action ?? cls.action} onChange={onReclassify} />} />
          <Meta k="Corner" v={
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              {event.displayCorner != null && <i style={{ width: 8, height: 8, borderRadius: 2, background: CORNER_C[event.displayCorner], display: 'block' }} />}
              {event.displayCorner === 0 ? 'Red' : event.displayCorner === 1 ? 'Blue' : 'None'}
            </span>
          } />
          <Meta k="Target" v={event.target ?? 'Non-specific'} />
          <Meta k="Frame" v={`f${event.frame}`} mono />
          <Meta k="Timecode" v={formatFrameClock(event.frame, event.fight.fps)} mono />
          <Meta k="Fight" v={fightLabel(event.fight)} />
          <Meta k="Labeller" v={event.labeler ?? 'Not recorded'} />
        </div>

        <div className="glass" style={{ padding: '16px 18px 18px' }}>
          <div className="label" style={{ marginBottom: 9 }}>Queue · {cls.name}</div>
          <div style={{ display: 'flex', height: 5, borderRadius: 2, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
            <div style={{ width: `${(pos.reviewed / pos.total) * 100}%`, background: 'var(--text-primary)' }} />
          </div>
          <div style={{ marginTop: 7, fontSize: 11.5, fontWeight: 400, color: 'var(--text-muted)' }}>{pos.reviewed} of {pos.total} reviewed · {pos.pending} pending</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 11, flexWrap: 'wrap' }}>
            <button type="button" className="btn-glass" onClick={() => onJumpRelative(-1)} style={{ padding: '6px 12px', fontSize: 11.5, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>chevron_left</span>Prev
            </button>
            <button type="button" className="btn-glass" onClick={() => onJumpRelative(1)} style={{ padding: '6px 12px', fontSize: 11.5, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              Next<span className="material-symbols-outlined" style={{ fontSize: 14 }}>chevron_right</span>
            </button>
            <span style={{ flex: 1 }} />
            <button type="button" className="btn-glass" onClick={onBack} style={{ padding: '6px 12px', fontSize: 11.5 }}>All events</button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 11, paddingTop: 10, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
            {queue.slice(0, 4).map((q) => (
              <button
                key={q.id}
                type="button"
                onClick={() => onJumpTo(q.id)}
                style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', borderRadius: 6, background: 'rgba(0,0,0,0.22)', border: '1px solid var(--border-subtle)', cursor: 'pointer', fontFamily: 'inherit' }}
              >
                <span style={{ width: 7, height: 7, borderRadius: 2, background: q.displayCorner != null ? CORNER_C[q.displayCorner] : 'var(--text-disabled)', flexShrink: 0 }} />
                <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500, color: 'var(--text-primary)' }}>{formatFrameClock(q.frame, q.fight.fps)}</span>
                <span style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fightLabel(q.fight).split(' vs ')[0]}</span>
              </button>
            ))}
            {queue.length === 0 && <div style={{ marginTop: 4, fontSize: 11.5, fontWeight: 400, color: 'var(--text-muted)' }}>Nothing left pending in this class.</div>}
          </div>
        </div>
      </aside>
    </div>
  );
}
