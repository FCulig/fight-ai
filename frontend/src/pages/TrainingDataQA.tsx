import { useMemo, useCallback, useEffect } from 'react';
import { useNavigate, useLocation, useParams, Link } from 'react-router-dom';
import { useTrainingDataEvents } from '../hooks/useTrainingDataEvents';
import type { QAEvent } from '../hooks/useTrainingDataEvents';
import { CLASS_BY_ACTION, reclassifyPayload } from '../utils/trainingDataTaxonomy';
import { useWindowWidth } from '../hooks/useWindowWidth';
import ClassGrid from '../components/trainingData/ClassGrid';
import { classStats } from '../utils/trainingDataStats';
import EventTable from '../components/trainingData/EventTable';
import EventReview from '../components/trainingData/EventReview';

const classesPath = () => '/training-data';
const eventsPath = (action: string) => `/training-data/${action}`;
const detailPath = (action: string, id: number) => `/training-data/${action}/${id}`;

const sortEvents = (evs: QAEvent[]) =>
  [...evs].sort((a, b) => (a.fight.id === b.fight.id ? a.frame - b.frame : a.fight.id - b.fight.id));

export default function TrainingDataQA() {
  const width = useWindowWidth();
  const isMobile = width < 640;
  const narrow = width < 1080;

  const navigate = useNavigate();
  const location = useLocation();
  // `action` selects the training class, `eventId` (only present one level
  // deeper) selects the reviewed event within it — both real URL segments,
  // so a class list or a specific event's review is directly linkable/
  // bookmarkable/shareable, and browser back/forward walk the review history.
  const { action, eventId } = useParams<{ action?: string; eventId?: string }>();
  const id = eventId != null ? Number(eventId) : null;

  const { events, fights, loading, error, setVerdict, reclassify } = useTrainingDataEvents();

  const eventsByAction = useMemo(() => {
    const m = new Map<string, QAEvent[]>();
    events.forEach((e) => {
      const key = e.action ?? '';
      const bucket = m.get(key);
      if (bucket) bucket.push(e); else m.set(key, [e]);
    });
    return m;
  }, [events]);

  const totals = classStats(events);

  const cls = action ? CLASS_BY_ACTION[action] : undefined;
  const evs = useMemo(() => (cls ? sortEvents(eventsByAction.get(cls.action) ?? []) : []), [cls, eventsByAction]);
  const ev = id != null ? evs.find((e) => e.id === id) ?? null : null;

  useEffect(() => { window.scrollTo({ top: 0 }); }, [action, id]);

  const nextPending = useCallback((fromId: number): number | null => {
    const idx = evs.findIndex((e) => e.id === fromId);
    if (idx === -1) return null;
    for (let k = 1; k <= evs.length; k++) {
      const c = evs[(idx + k) % evs.length];
      // `evs` is still last render's snapshot here (setVerdict's update hasn't
      // committed yet) — exclude fromId explicitly so a class with exactly
      // one pending event doesn't "advance" back onto itself.
      if (c.id !== fromId && c.is_verified == null) return c.id;
    }
    return null;
  }, [evs]);

  const onVerdict = useCallback((isVerified: boolean | null) => {
    if (!cls || id == null) return;
    const fightId = ev?.fight.id;
    if (fightId == null) return;
    setVerdict(id, fightId, isVerified);
    if (isVerified == null) return; // clearing a verdict never auto-advances
    const nx = nextPending(id);
    if (nx != null) setTimeout(() => navigate(detailPath(cls.action, nx), { replace: true }), 170);
    else setTimeout(() => navigate(eventsPath(cls.action), { replace: true, state: { justFinished: true } }), 240);
  }, [cls, id, ev, setVerdict, nextPending, navigate]);

  // Retyping a strike almost always moves it out of the class page it's
  // being reviewed from (evs is keyed by e.action === cls.action) — so on
  // success this advances exactly like a verdict does: to the next pending
  // event in the class just left, or back to that class's list if none
  // remain. Re-throws on failure so TypeSelect's own catch can surface the
  // error instead of silently navigating away from a failed save.
  const onReclassify = useCallback(async (newAction: string) => {
    if (!cls || id == null || ev == null) return;
    const fightId = ev.fight.id;
    const payload = reclassifyPayload(newAction, ev.target);
    await reclassify(id, fightId, payload.action, payload.target, payload.success);
    if (payload.action === cls.action) return; // stayed in this class — nothing to navigate away from
    const nx = nextPending(id);
    if (nx != null) setTimeout(() => navigate(detailPath(cls.action, nx), { replace: true }), 170);
    else setTimeout(() => navigate(eventsPath(cls.action), { replace: true, state: { justFinished: true } }), 240);
  }, [cls, id, ev, reclassify, nextPending, navigate]);

  const onJumpRelative = useCallback((delta: 1 | -1) => {
    if (!cls || id == null || evs.length === 0) return;
    const idx = evs.findIndex((e) => e.id === id);
    const n = evs[(idx + delta + evs.length) % evs.length];
    navigate(detailPath(cls.action, n.id), { replace: true });
  }, [cls, id, evs, navigate]);

  const onJumpTo = useCallback((jumpId: number) => {
    if (!cls) return;
    navigate(detailPath(cls.action, jumpId), { replace: true });
  }, [cls, navigate]);

  const justFinished = (location.state as { justFinished?: boolean } | null)?.justFinished === true;

  let body: React.ReactNode;

  if (loading) {
    body = <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading…</div>;
  } else if (error) {
    body = <div style={{ fontSize: 13, color: 'var(--red-500)' }}>{error}</div>;
  } else if (fights.length === 0) {
    body = (
      <div className="glass" style={{ padding: '20px 22px', fontSize: 13, color: 'var(--text-muted)' }}>
        No labelled fights yet. Upload a fight as "Self-annotate" and start labelling it in Annotate to build training data.
      </div>
    );
  } else if (!action) {
    body = (
      <>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 24, flexWrap: 'wrap', marginBottom: 14 }}>
          <div style={{ minWidth: 0 }}>
            <span className="eyebrow">Data QA</span>
            <h1 className="font-display" style={{ fontSize: isMobile ? 32 : 'clamp(36px, 4.6vw, 60px)', lineHeight: 0.94, margin: '10px 0 0', color: 'var(--text-primary)' }}>
              Every label. Checked.
            </h1>
            <p style={{ margin: '10px 0 0', fontSize: 13.5, fontWeight: 600, color: 'var(--text-muted)' }}>
              Replay each event exactly as the trainer sees it. Keep it or drop it.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 26, flexWrap: 'wrap', marginLeft: 'auto' }}>
            <Stat label="events" value={totals.total} />
            <Stat label="confirmed" value={totals.confirmed} color="var(--green-500)" />
            <Stat label="declined" value={totals.declined} color="var(--red-500)" />
          </div>
        </div>
        {totals.total > 0 && (
          <div style={{ display: 'flex', gap: 2, height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.05)', overflow: 'hidden', marginBottom: 7 }}>
            <div style={{ width: `${(totals.confirmed / totals.total) * 100}%`, background: 'var(--green-500)' }} />
            <div style={{ width: `${(totals.declined / totals.total) * 100}%`, background: 'var(--red-500)' }} />
          </div>
        )}
        <div style={{ margin: '0 0 22px', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>
          {totals.reviewed} of {totals.total} reviewed · {totals.pending} pending · across {fights.length} labelled fight{fights.length === 1 ? '' : 's'}
        </div>
        <ClassGrid eventsByAction={eventsByAction} onOpen={(a) => navigate(eventsPath(a))} />
      </>
    );
  } else if (!cls) {
    body = (
      <div className="glass" style={{ padding: '20px 22px', fontSize: 13, color: 'var(--text-muted)' }}>
        "{action}" isn't a training class. <Link to={classesPath()}>Back to all classes</Link>.
      </div>
    );
  } else if (id == null) {
    body = justFinished ? (
      <div className="glass" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 11, padding: '46px 30px', textAlign: 'center' }}>
        <span className="material-symbols-outlined" style={{ fontSize: 40, color: 'var(--accent)' }}>task_alt</span>
        <div className="font-display" style={{ fontSize: 28, lineHeight: 1, color: 'var(--text-primary)' }}>{cls.name} reviewed</div>
        <p style={{ margin: 0, maxWidth: '46ch', fontSize: 12.5, fontWeight: 500, lineHeight: 1.6, color: 'var(--text-muted)' }}>
          Every {cls.name.toLowerCase()} event has a verdict. Pick another class or re-open the list.
        </p>
        <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap', justifyContent: 'center' }}>
          <button type="button" className="btn-glass" onClick={() => navigate(eventsPath(cls.action))} style={{ padding: '9px 16px', fontSize: 12.5, fontWeight: 600 }}>
            Back to events
          </button>
          <button
            type="button"
            onClick={() => navigate(classesPath())}
            style={{
              background: 'linear-gradient(135deg, var(--accent), var(--accent-deep))', color: 'var(--accent-on)', fontWeight: 700, fontSize: 13,
              border: 'none', borderRadius: 999, padding: '9px 16px', cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            All classes
          </button>
        </div>
      </div>
    ) : (
      <EventTable cls={cls} events={evs} onBack={() => navigate(classesPath())} onOpen={(openId) => navigate(detailPath(cls.action, openId))} />
    );
  } else if (ev) {
    body = (
      <>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 14, flexWrap: 'wrap' }}>
          <button type="button" className="btn-glass" onClick={() => navigate(classesPath())} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', fontSize: 11.5, fontWeight: 700 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>arrow_back</span>All classes
          </button>
          <span style={{ color: 'var(--text-disabled)', fontSize: 12 }}>/</span>
          <button type="button" className="btn-glass" onClick={() => navigate(eventsPath(cls.action))} style={{ padding: '7px 14px', fontSize: 11.5, fontWeight: 700, background: 'none', border: '1px solid transparent' }}>
            {cls.name}
          </button>
          <span style={{ color: 'var(--text-disabled)', fontSize: 12 }}>/</span>
          <span style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--text-secondary)' }}>{`f${ev.frame}`}</span>
        </div>
        <EventReview
          event={ev}
          cls={cls}
          onVerdict={onVerdict}
          onReclassify={onReclassify}
          onBack={() => navigate(eventsPath(cls.action))}
          onJumpRelative={onJumpRelative}
          onJumpTo={onJumpTo}
          queue={evs.filter((e) => e.is_verified == null && e.id !== ev.id)}
          pos={classStats(evs)}
          narrow={narrow}
        />
      </>
    );
  } else {
    body = (
      <div className="glass" style={{ padding: '20px 22px', fontSize: 13, color: 'var(--text-muted)' }}>
        That event isn't in {cls.name}. <Link to={eventsPath(cls.action)}>Back to {cls.name}</Link>.
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', zIndex: 1, maxWidth: 1320, margin: '0 auto', padding: isMobile ? '18px 16px 70px' : '22px 30px 90px' }}>
      {body}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{
        fontFamily: 'Manrope, sans-serif', fontWeight: 800, letterSpacing: '-0.05em', lineHeight: 0.9,
        fontVariantNumeric: 'tabular-nums', fontSize: 40, color: color ?? 'var(--text-primary)',
      }}>{value}</span>
      <span className="label">{label}</span>
    </div>
  );
}
