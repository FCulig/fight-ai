import { useState, useRef, useEffect, useMemo } from 'react';
import type { LabelEvent } from '../../types/LabelEvent';
import type { LabelSpan, SpanKind } from '../../types/LabelSpan';
import type { Round } from '../../types/Round';
import { categoryForAction, colorForAction, iconForAction, matchFilter, formatFrameClock } from './taxonomy';

const TL = { ruler: 26, round: 30, state: 30, span: 26, lane: 46, head: 132 };

const SPAN_COLOR: Record<SpanKind, string> = {
  round: 'var(--green-500)',
  corner_swap: 'var(--purple-600)',
  excluded: 'var(--text-muted)',
};

function useMeasure(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(es => { for (const e of es) setW(e.contentRect.width); });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function fmtSec(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, '0')}`;
}

function laneFor(e: LabelEvent): 'red' | 'blue' | null {
  if (e.corner === 0) return 'red';
  if (e.corner === 1) return 'blue';
  return null;
}

interface Hover { e: LabelEvent; x: number; color: string }

interface ClipProps {
  e: LabelEvent;
  x: number;
  color: string;
  flash: boolean;
  selected: boolean;
  onSeek: (frame: number) => void;
  onSelect: (id: number) => void;
  onHover: (h: Hover | null) => void;
}

function Clip({ e, x, color, flash, selected, onSeek, onSelect, onHover }: ClipProps) {
  return (
    <button
      className="tl-clip"
      onPointerDown={ev => ev.stopPropagation()}
      onClick={ev => { ev.stopPropagation(); onSeek(e.frame); onSelect(e.id); }}
      onMouseEnter={ev => onHover({ e, x: (ev.currentTarget as HTMLElement).offsetLeft, color })}
      onMouseLeave={() => onHover(null)}
      title={selected ? `${e.description} · Delete to remove` : e.description}
      style={{
        position: 'absolute', left: x - 11, top: (TL.lane - 30) / 2, width: 22, height: 30, borderRadius: 7,
        display: 'grid', placeItems: 'center', cursor: 'pointer', zIndex: flash || selected ? 6 : 4, padding: 0,
        transition: 'transform .1s',
        border: `1px solid color-mix(in srgb, ${color} ${flash || selected ? 90 : 55}%, transparent)`,
        background: `color-mix(in srgb, ${color} ${flash || selected ? 34 : 18}%, var(--surface-inner))`,
        boxShadow: selected ? `0 0 0 2px #fff, 0 0 0 3.5px ${color}` : flash ? `0 0 0 1.5px ${color}, 0 0 16px -2px ${color}` : 'none',
        animation: 'feed-in .25s ease-out',
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: 16, color }}>{iconForAction(e.action)}</span>
    </button>
  );
}

interface AnnotationTimelineProps {
  events: LabelEvent[];
  spans: LabelSpan[];
  rounds: Round[];
  duration: number;
  fps: number;
  currentFrame: number;
  onSeek: (frame: number) => void;
  onSetPlaying: (playing: boolean) => void;
  onUpdateSpan: (id: number, patch: { start_frame?: number; end_frame?: number }) => void;
  onDeleteSpan: (id: number) => void;
  flashId: number | null;
  selectedEventId: number | null;
  onSelectEvent: (id: number | null) => void;
  filter: string;
  redName: string;
  blueName: string;
}

export default function AnnotationTimeline({
  events, spans, rounds, duration, fps, currentFrame, onSeek, onSetPlaying, onUpdateSpan, onDeleteSpan,
  flashId, selectedEventId, onSelectEvent, filter, redName, blueName,
}: AnnotationTimelineProps) {
  const [zoom, setZoom] = useState(1);
  const [hover, setHover] = useState<Hover | null>(null);
  const [scrollRef, scrollW] = useMeasure();
  const draggingRef = useRef(false);

  const time = (currentFrame - 1) / fps;
  const frameFor = (t: number) => Math.max(1, Math.round(t * fps) + 1);
  const xFor = (frame: number) => ((frame - 1) / fps) * pxPerSec;

  const fitPx = scrollW > 0 ? scrollW / Math.max(duration, 1) : 2.2;
  const pxPerSec = fitPx * zoom;
  const W = duration * pxPerSec;
  const spansTop = TL.ruler + TL.round + TL.state;
  const lanesTop = spansTop + TL.span * 2;
  const totalH = lanesTop + TL.lane * 2;
  const boxH = totalH + 14;

  // Live edge being dragged, so the block redraws smoothly before the PUT commits.
  const dragRef = useRef<{ id: number; edge: 'start' | 'end' } | null>(null);
  const [dragFrame, setDragFrame] = useState<number | null>(null);

  const fil = (e: LabelEvent) => matchFilter(categoryForAction(e.action), filter);
  const redEv = events.filter(e => laneFor(e) === 'red' && e.action !== 'fight_end' && fil(e));
  const blueEv = events.filter(e => laneFor(e) === 'blue' && e.action !== 'fight_end' && fil(e));
  const roundEv = events.filter(e => categoryForAction(e.action) === 'round' || e.action === 'fight_end');
  // Everything after fight_end is dead air (celebration, doctor check, corner
  // talk) — the round span and the last state segment are visually capped
  // here to end there, so the timeline actually looks like the fight is
  // over. The underlying round span's real end_frame is untouched (only the
  // auto-created `excluded` span makes the tail harmless for scoring/export
  // — see Annotate.tsx's confirmFightEnd); this is display-only.
  const fightEndFrame = events.find(e => e.action === 'fight_end')?.frame ?? null;
  const stateEv = useMemo(
    () => events.filter(e => categoryForAction(e.action) === 'state').sort((a, b) => a.frame - b.frame),
    [events],
  );
  const segs = stateEv
    .map((e, i) => {
      const rawT1 = i + 1 < stateEv.length ? (stateEv[i + 1].frame - 1) / fps : duration;
      const t1 = fightEndFrame != null ? Math.min(rawT1, (fightEndFrame - 1) / fps) : rawT1;
      return {
        id: e.id,
        t0: (e.frame - 1) / fps,
        t1,
        state: e.action === 'state_clinch' ? 'CLINCH' : e.action === 'state_ground' ? 'GROUND' : 'STRIKING',
      };
    })
    .filter(s => s.t1 >= s.t0); // drop a segment that starts entirely after fight_end

  // Same display-only capping as the state segments above: the round block
  // that contains fight_end is drawn ending there instead of at its real
  // (now-stale) end_frame. Edge-drag still targets the real span by id, so
  // dragging the end handle still writes the true end_frame — it just
  // starts from the visually-capped position rather than the stale one.
  const roundSpans = spans
    .filter(s => s.kind === 'round')
    .map(s => (
      fightEndFrame != null && s.end_frame != null &&
      s.start_frame <= fightEndFrame && fightEndFrame < s.end_frame
        ? { ...s, end_frame: fightEndFrame }
        : s
    ));
  const cornerSwapSpans = spans.filter(s => s.kind === 'corner_swap');
  const excludedSpans = spans.filter(s => s.kind === 'excluded');

  const targets = [5, 10, 15, 30, 60, 120, 180];
  const tickEvery = targets.find(s => s * pxPerSec >= 64) || 240;
  const ticks: number[] = [];
  for (let t = 0; t <= duration; t += tickEvery) ticks.push(t);

  const scrubRef = useRef<(clientX: number) => void>(() => {});
  scrubRef.current = (clientX: number) => {
    const el = scrollRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const t = (clientX - r.left + el.scrollLeft) / pxPerSec;
    onSeek(frameFor(Math.max(0, Math.min(duration, t))));
  };
  useEffect(() => {
    const move = (e: PointerEvent) => { if (draggingRef.current) scrubRef.current(e.clientX); };
    const up = () => { draggingRef.current = false; };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    return () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
  }, []);
  const startScrub = (e: React.PointerEvent) => {
    draggingRef.current = true;
    onSetPlaying(false);
    onSelectEvent(null); // clicking the background/ruler deselects whatever clip was selected
    scrubRef.current(e.clientX);
  };

  // Edge-drag for span blocks (round / corner_swap / excluded resize handles).
  useEffect(() => {
    const move = (e: PointerEvent) => {
      const d = dragRef.current;
      const el = scrollRef.current;
      if (!d || !el) return;
      const r = el.getBoundingClientRect();
      const t = (e.clientX - r.left + el.scrollLeft) / pxPerSec;
      setDragFrame(frameFor(Math.max(0, Math.min(duration, t))));
    };
    const up = () => {
      const d = dragRef.current;
      if (d && dragFrame != null) {
        onUpdateSpan(d.id, d.edge === 'start' ? { start_frame: dragFrame } : { end_frame: dragFrame });
      }
      dragRef.current = null;
      setDragFrame(null);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    return () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pxPerSec, duration, dragFrame]);
  const startEdgeDrag = (id: number, edge: 'start' | 'end') => (e: React.PointerEvent) => {
    e.stopPropagation();
    onSetPlaying(false);
    dragRef.current = { id, edge };
  };

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const x = xFor(currentFrame);
    const L = el.scrollLeft;
    const R = L + el.clientWidth;
    if (x < L + 48 || x > R - 48) el.scrollLeft = x - el.clientWidth / 2;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [time, pxPerSec]);

  const TrackHead = ({ h, children, top }: { h: number; children: React.ReactNode; top: number }) => (
    <div style={{
      position: 'absolute', top, left: 0, height: h, width: TL.head, display: 'flex', alignItems: 'center', gap: 8,
      padding: '0 12px', boxSizing: 'border-box', borderBottom: '1px solid var(--border-subtle)',
      borderRight: '1px solid var(--border-glass)', background: 'var(--surface-inner)',
    }}>{children}</div>
  );

  const playX = xFor(currentFrame);

  // A span block with draggable edges (round/corner_swap) or a plain block
  // with a delete button (corner_swap/excluded). `end_frame == null` means
  // the start/end toggle is still open — draw it running to the playhead.
  const SpanBlock = ({ s, top, h, deletable }: { s: LabelSpan; top: number; h: number; deletable: boolean }) => {
    const dragging = dragRef.current?.id === s.id;
    const start = dragging && dragRef.current?.edge === 'start' && dragFrame != null ? dragFrame : s.start_frame;
    const end = dragging && dragRef.current?.edge === 'end' && dragFrame != null
      ? dragFrame
      : s.end_frame ?? currentFrame;
    const open = s.end_frame == null;
    const x0 = xFor(Math.min(start, end));
    const w = Math.max(4, xFor(Math.max(start, end)) - x0);
    const c = SPAN_COLOR[s.kind];
    return (
      <div
        style={{
          position: 'absolute', top, left: x0, width: w, height: h, borderRadius: 5, zIndex: 3,
          background: `color-mix(in srgb, ${c} ${open ? 10 : 16}%, transparent)`,
          border: `1px solid color-mix(in srgb, ${c} ${open ? 55 : 38}%, transparent)`,
          borderStyle: open ? 'dashed' : 'solid',
          display: 'flex', alignItems: 'center', overflow: 'hidden',
        }}
        title={s.value ? `${s.kind} — ${s.value}` : s.kind}
      >
        <div
          onPointerDown={startEdgeDrag(s.id, 'start')}
          title="Drag to move the start"
          style={{
            position: 'absolute', left: -5, top: 0, width: 13, height: '100%', cursor: 'ew-resize', zIndex: 4,
            display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 4,
          }}
        >
          <span style={{ width: 2, height: '55%', borderRadius: 1, background: `color-mix(in srgb, ${c} 70%, transparent)` }} />
        </div>
        {!open && (
          <div
            onPointerDown={startEdgeDrag(s.id, 'end')}
            title="Drag to move the end"
            style={{
              position: 'absolute', right: -5, top: 0, width: 13, height: '100%', cursor: 'ew-resize', zIndex: 4,
              display: 'flex', alignItems: 'center', justifyContent: 'flex-start', paddingLeft: 4,
            }}
          >
            <span style={{ width: 2, height: '55%', borderRadius: 1, background: `color-mix(in srgb, ${c} 70%, transparent)` }} />
          </div>
        )}
        {w > 30 && (
          <span style={{ fontSize: 9.5, fontWeight: 800, color: c, whiteSpace: 'nowrap', paddingLeft: 8, pointerEvents: 'none' }}>
            {s.kind === 'round' ? `R${s.value ?? ''}` : s.value ?? s.kind.toUpperCase()}{open ? '…' : ''}
          </span>
        )}
        {deletable && !open && (
          <button
            onPointerDown={ev => ev.stopPropagation()}
            onClick={ev => { ev.stopPropagation(); onDeleteSpan(s.id); }}
            title="Delete"
            style={{
              position: 'absolute', right: 2, top: '50%', transform: 'translateY(-50%)', width: 14, height: 14,
              borderRadius: 4, border: 'none', background: 'rgba(0,0,0,0.35)', color: c, cursor: 'pointer',
              display: 'grid', placeItems: 'center', padding: 0, zIndex: 5,
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 10 }}>close</span>
          </button>
        )}
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', position: 'relative', height: boxH, borderRadius: 12, overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
      <div style={{ position: 'relative', width: TL.head, flexShrink: 0, background: 'var(--surface-inner)', zIndex: 8 }}>
        <div style={{
          position: 'absolute', top: 0, height: TL.ruler, width: TL.head, borderBottom: '1px solid var(--border-glass)',
          borderRight: '1px solid var(--border-glass)', display: 'flex', alignItems: 'center', padding: '0 12px',
          fontSize: 9, fontWeight: 800, letterSpacing: '0.1em', color: 'var(--text-disabled)',
        }}>TRACKS</div>
        <TrackHead top={TL.ruler} h={TL.round}>
          <span className="material-symbols-outlined" style={{ fontSize: 15, color: 'var(--green-500)' }}>flag</span>
          <span style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>ROUNDS</span>
        </TrackHead>
        <TrackHead top={TL.ruler + TL.round} h={TL.state}>
          <span className="material-symbols-outlined" style={{ fontSize: 15, color: 'var(--slate-400)' }}>change_circle</span>
          <span style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: '0.06em', color: 'var(--text-tertiary)' }}>STATE</span>
        </TrackHead>
        <TrackHead top={spansTop} h={TL.span}>
          <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--purple-600)' }}>swap_horiz</span>
          <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>CORNER SWAP</span>
        </TrackHead>
        <TrackHead top={spansTop + TL.span} h={TL.span}>
          <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--text-muted)' }}>visibility_off</span>
          <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.05em', color: 'var(--text-tertiary)' }}>EXCLUDED</span>
        </TrackHead>
        <TrackHead top={lanesTop} h={TL.lane}>
          <span style={{ width: 9, height: 9, borderRadius: 2, background: 'var(--f-red)' }} />
          <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--text-secondary)' }}>{redName}</span>
        </TrackHead>
        <TrackHead top={lanesTop + TL.lane} h={TL.lane}>
          <span style={{ width: 9, height: 9, borderRadius: 2, background: 'var(--f-blue)' }} />
          <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--text-secondary)' }}>{blueName}</span>
        </TrackHead>
      </div>

      <div ref={scrollRef} className="tl-scroll" style={{ flex: 1, overflowX: 'auto', overflowY: 'hidden', position: 'relative' }}>
        <div style={{ position: 'relative', width: W, height: totalH, minWidth: '100%' }}>
          <div style={{ position: 'absolute', top: TL.ruler, left: 0, width: '100%', height: TL.round, background: 'rgba(255,255,255,0.018)' }} />
          <div style={{ position: 'absolute', top: lanesTop + TL.lane, left: 0, width: '100%', height: TL.lane, background: 'rgba(255,255,255,0.022)' }} />

          {rounds.map(r => (
            <div key={'rb' + r.id}>
              {r.round_number > 1 && (
                <div style={{ position: 'absolute', top: TL.ruler, left: xFor(r.start_frame), width: 1, height: totalH - TL.ruler, background: 'rgba(255,255,255,0.12)' }} />
              )}
            </div>
          ))}

          <div
            onPointerDown={startScrub}
            className="tl-ruler"
            style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: TL.ruler, cursor: 'ew-resize', borderBottom: '1px solid var(--border-glass)' }}
          >
            {ticks.map(t => (
              <div key={t} style={{ position: 'absolute', left: t * pxPerSec, top: 0, height: '100%', pointerEvents: 'none' }}>
                <div style={{ position: 'absolute', left: 0, bottom: 0, width: 1, height: 7, background: 'rgba(255,255,255,0.22)' }} />
                <span style={{ position: 'absolute', left: 5, top: 5, fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{fmtSec(t)}</span>
              </div>
            ))}
          </div>

          <div onPointerDown={startScrub} style={{ position: 'absolute', top: TL.ruler, left: 0, width: '100%', height: totalH - TL.ruler, cursor: 'ew-resize', zIndex: 1 }} />

          {roundSpans.map(s => (
            <SpanBlock key={'rs' + s.id} s={s} top={TL.ruler + 4} h={TL.round - 8} deletable />
          ))}

          {segs.map(s => {
            const c = s.state === 'GROUND' ? 'var(--f-red)' : s.state === 'CLINCH' ? 'var(--orange-400)' : 'var(--accent)';
            const w = Math.max(2, s.t1 * pxPerSec - s.t0 * pxPerSec);
            return (
              <div
                key={'seg' + s.id}
                title={s.state}
                style={{
                  position: 'absolute', top: TL.ruler + TL.round + 5, left: s.t0 * pxPerSec, width: w, height: TL.state - 10,
                  borderRadius: 6, zIndex: 2, background: `color-mix(in srgb, ${c} 16%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${c} 38%, transparent)`, borderLeft: `3px solid ${c}`,
                  overflow: 'hidden', display: 'flex', alignItems: 'center', paddingLeft: 8,
                }}
              >
                {w > 64 && <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.05em', color: c, whiteSpace: 'nowrap' }}>{s.state}</span>}
              </div>
            );
          })}

          {cornerSwapSpans.map(s => (
            <SpanBlock key={'cs' + s.id} s={s} top={spansTop + 3} h={TL.span - 6} deletable />
          ))}
          {excludedSpans.map(s => (
            <SpanBlock key={'ex' + s.id} s={s} top={spansTop + TL.span + 3} h={TL.span - 6} deletable />
          ))}

          {roundEv.map(e => {
            const fe = e.action === 'fight_end';
            const c = colorForAction(e.action);
            const selected = e.id === selectedEventId;
            return (
              <button
                key={'rp' + e.id}
                className="tl-clip"
                onPointerDown={ev => ev.stopPropagation()}
                onClick={ev => { ev.stopPropagation(); onSeek(e.frame); onSelectEvent(e.id); }}
                onMouseEnter={ev => setHover({ e, x: (ev.currentTarget as HTMLElement).offsetLeft, color: c })}
                onMouseLeave={() => setHover(null)}
                title={selected ? `${e.description} · Delete to remove` : e.description}
                style={{
                  position: 'absolute', top: TL.ruler + 5, left: xFor(e.frame) - 10, width: 20, height: TL.round - 10,
                  borderRadius: 6, zIndex: selected ? 6 : 5, display: 'grid', placeItems: 'center', cursor: 'pointer', padding: 0,
                  border: `1px solid color-mix(in srgb, ${c} 60%, transparent)`,
                  background: `color-mix(in srgb, ${c} ${fe ? 30 : 18}%, var(--surface-inner))`,
                  boxShadow: selected ? `0 0 0 2px #fff, 0 0 0 3.5px ${c}` : e.id === flashId ? `0 0 0 1.5px ${c}, 0 0 14px -2px ${c}` : 'none',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 14, color: c }}>{iconForAction(e.action)}</span>
              </button>
            );
          })}

          {redEv.map(e => (
            <div key={e.id} style={{ position: 'absolute', top: lanesTop, left: 0 }}>
              <Clip e={e} x={xFor(e.frame)} color={colorForAction(e.action)} flash={e.id === flashId} selected={e.id === selectedEventId} onSeek={onSeek} onSelect={onSelectEvent} onHover={setHover} />
            </div>
          ))}
          {blueEv.map(e => (
            <div key={e.id} style={{ position: 'absolute', top: lanesTop + TL.lane, left: 0 }}>
              <Clip e={e} x={xFor(e.frame)} color={colorForAction(e.action)} flash={e.id === flashId} selected={e.id === selectedEventId} onSeek={onSeek} onSelect={onSelectEvent} onHover={setHover} />
            </div>
          ))}

          {[TL.ruler + TL.round, TL.ruler + TL.round + TL.state, spansTop + TL.span, lanesTop, lanesTop + TL.lane].map((y, i) => (
            <div key={'ld' + i} style={{ position: 'absolute', top: y, left: 0, width: '100%', height: 1, background: 'var(--border-subtle)', pointerEvents: 'none' }} />
          ))}

          <div style={{ position: 'absolute', top: 0, left: playX, width: 2, height: totalH, background: 'var(--accent)', boxShadow: '0 0 8px var(--accent)', zIndex: 7, pointerEvents: 'none' }}>
            <div style={{ position: 'absolute', top: 0, left: -6, width: 14, height: 11, background: 'var(--accent)', clipPath: 'polygon(0 0,100% 0,50% 100%)' }} />
          </div>

          {hover && (
            <div style={{ position: 'absolute', left: Math.max(4, hover.x - 70), top: lanesTop - 4, transform: 'translateY(-100%)', zIndex: 20, width: 200, pointerEvents: 'none' }}>
              <div className="glass" style={{ padding: '9px 11px', borderRadius: 9, borderLeft: `3px solid ${hover.color}` }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.3 }}>{hover.e.description}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 4, fontSize: 10.5, color: 'var(--text-muted)' }}>
                  <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 700 }}>{formatFrameClock(hover.e.frame, fps)}</span>
                  <span style={{ marginLeft: 'auto', opacity: 0.7 }}>#{hover.e.frame}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div style={{
        position: 'absolute', right: 10, bottom: 10, display: 'flex', alignItems: 'center', gap: 4, zIndex: 9,
        background: 'rgba(8,11,15,0.72)', backdropFilter: 'blur(8px)', padding: 4, borderRadius: 9, border: '1px solid var(--border-glass)',
      }}>
        <button className="icon-btn" title="Zoom out" onClick={() => setZoom(z => Math.max(1, +(z - 0.5).toFixed(1)))} style={{ width: 28, height: 28 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 17 }}>remove</span>
        </button>
        <button className="icon-btn" title="Fit" onClick={() => setZoom(1)} style={{ width: 28, height: 28, color: zoom === 1 ? 'var(--accent)' : 'var(--text-secondary)' }}>
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>fit_screen</span>
        </button>
        <button className="icon-btn" title="Zoom in" onClick={() => setZoom(z => Math.min(12, +(z + 0.5).toFixed(1)))} style={{ width: 28, height: 28 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 17 }}>add</span>
        </button>
      </div>
    </div>
  );
}
