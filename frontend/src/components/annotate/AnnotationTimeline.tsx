import { useState, useRef, useEffect, useMemo } from 'react';
import type { Event } from '../../types/Event';
import type { Round } from '../../types/Round';
import { categoryForAction, colorForAction, iconForAction, matchFilter, formatFrameClock } from './taxonomy';

const TL = { ruler: 26, round: 30, state: 30, lane: 46, head: 132 };

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

function laneFor(e: Event, redId: number | null, blueId: number | null): 'red' | 'blue' | null {
  if (e.fighter_id == null) return null;
  if (e.fighter_id === redId) return 'red';
  if (e.fighter_id === blueId) return 'blue';
  return null;
}

interface Hover { e: Event; x: number; color: string }

interface ClipProps {
  e: Event;
  x: number;
  color: string;
  flash: boolean;
  onSeek: (frame: number) => void;
  onHover: (h: Hover | null) => void;
}

function Clip({ e, x, color, flash, onSeek, onHover }: ClipProps) {
  return (
    <button
      className="tl-clip"
      onPointerDown={ev => ev.stopPropagation()}
      onClick={ev => { ev.stopPropagation(); onSeek(e.frame); }}
      onMouseEnter={ev => onHover({ e, x: (ev.currentTarget as HTMLElement).offsetLeft, color })}
      onMouseLeave={() => onHover(null)}
      style={{
        position: 'absolute', left: x - 11, top: (TL.lane - 30) / 2, width: 22, height: 30, borderRadius: 7,
        display: 'grid', placeItems: 'center', cursor: 'pointer', zIndex: flash ? 6 : 4, padding: 0,
        transition: 'transform .1s',
        border: `1px solid color-mix(in srgb, ${color} ${flash ? 90 : 55}%, transparent)`,
        background: `color-mix(in srgb, ${color} ${flash ? 34 : 18}%, var(--surface-inner))`,
        boxShadow: flash ? `0 0 0 1.5px ${color}, 0 0 16px -2px ${color}` : 'none',
        animation: 'feed-in .25s ease-out',
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: 16, color }}>{iconForAction(e.action)}</span>
    </button>
  );
}

interface AnnotationTimelineProps {
  events: Event[];
  rounds: Round[];
  duration: number;
  fps: number;
  currentFrame: number;
  onSeek: (frame: number) => void;
  onSetPlaying: (playing: boolean) => void;
  flashId: number | null;
  filter: string;
  redFighterId: number | null;
  blueFighterId: number | null;
  redName: string;
  blueName: string;
}

export default function AnnotationTimeline({
  events, rounds, duration, fps, currentFrame, onSeek, onSetPlaying, flashId, filter,
  redFighterId, blueFighterId, redName, blueName,
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
  const lanesTop = TL.ruler + TL.round + TL.state;
  const totalH = lanesTop + TL.lane * 2;
  const boxH = totalH + 14;

  const fil = (e: Event) => matchFilter(categoryForAction(e.action), filter);
  const redEv = events.filter(e => laneFor(e, redFighterId, blueFighterId) === 'red' && e.action !== 'fight_end' && fil(e));
  const blueEv = events.filter(e => laneFor(e, redFighterId, blueFighterId) === 'blue' && e.action !== 'fight_end' && fil(e));
  const roundEv = events.filter(e => categoryForAction(e.action) === 'round' || e.action === 'fight_end');
  const stateEv = useMemo(
    () => events.filter(e => categoryForAction(e.action) === 'state').sort((a, b) => a.frame - b.frame),
    [events],
  );
  const segs = stateEv.map((e, i) => ({
    id: e.id,
    t0: (e.frame - 1) / fps,
    t1: i + 1 < stateEv.length ? (stateEv[i + 1].frame - 1) / fps : duration,
    grapple: e.action === 'state_grappling',
  }));

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
  const startScrub = (e: React.PointerEvent) => { draggingRef.current = true; onSetPlaying(false); scrubRef.current(e.clientX); };

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
              <div style={{ position: 'absolute', top: 4, left: xFor(r.start_frame) + 6, fontSize: 9.5, fontWeight: 800, letterSpacing: '0.08em', color: 'var(--text-disabled)', pointerEvents: 'none' }}>
                R{r.round_number}
              </div>
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

          {segs.map(s => {
            const c = s.grapple ? 'var(--orange-400)' : 'var(--accent)';
            const w = Math.max(2, s.t1 * pxPerSec - s.t0 * pxPerSec);
            return (
              <div
                key={'seg' + s.id}
                title={s.grapple ? 'Grappling' : 'Striking'}
                style={{
                  position: 'absolute', top: TL.ruler + TL.round + 5, left: s.t0 * pxPerSec, width: w, height: TL.state - 10,
                  borderRadius: 6, zIndex: 2, background: `color-mix(in srgb, ${c} 16%, transparent)`,
                  border: `1px solid color-mix(in srgb, ${c} 38%, transparent)`, borderLeft: `3px solid ${c}`,
                  overflow: 'hidden', display: 'flex', alignItems: 'center', paddingLeft: 8,
                }}
              >
                {w > 64 && <span style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.05em', color: c, whiteSpace: 'nowrap' }}>{s.grapple ? 'GRAPPLING' : 'STRIKING'}</span>}
              </div>
            );
          })}

          {roundEv.map(e => {
            const fe = e.action === 'fight_end';
            const c = colorForAction(e.action);
            return (
              <button
                key={'rp' + e.id}
                className="tl-clip"
                onPointerDown={ev => ev.stopPropagation()}
                onClick={ev => { ev.stopPropagation(); onSeek(e.frame); }}
                onMouseEnter={ev => setHover({ e, x: (ev.currentTarget as HTMLElement).offsetLeft, color: c })}
                onMouseLeave={() => setHover(null)}
                style={{
                  position: 'absolute', top: TL.ruler + 5, left: xFor(e.frame) - 10, width: 20, height: TL.round - 10,
                  borderRadius: 6, zIndex: 5, display: 'grid', placeItems: 'center', cursor: 'pointer', padding: 0,
                  border: `1px solid color-mix(in srgb, ${c} 60%, transparent)`,
                  background: `color-mix(in srgb, ${c} ${fe ? 30 : 18}%, var(--surface-inner))`,
                  boxShadow: e.id === flashId ? `0 0 0 1.5px ${c}, 0 0 14px -2px ${c}` : 'none',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 14, color: c }}>{iconForAction(e.action)}</span>
              </button>
            );
          })}

          {redEv.map(e => (
            <div key={e.id} style={{ position: 'absolute', top: lanesTop, left: 0 }}>
              <Clip e={e} x={xFor(e.frame)} color={colorForAction(e.action)} flash={e.id === flashId} onSeek={onSeek} onHover={setHover} />
            </div>
          ))}
          {blueEv.map(e => (
            <div key={e.id} style={{ position: 'absolute', top: lanesTop + TL.lane, left: 0 }}>
              <Clip e={e} x={xFor(e.frame)} color={colorForAction(e.action)} flash={e.id === flashId} onSeek={onSeek} onHover={setHover} />
            </div>
          ))}

          {[TL.ruler + TL.round, lanesTop, lanesTop + TL.lane].map((y, i) => (
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
