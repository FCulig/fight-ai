import { useState, useEffect, useRef, useMemo } from 'react';
import type { Event } from '../../types/Event';
import { deriveEventCat, eventColor, eventIcon } from './eventMeta';

interface LiveFeedProps {
  events: Event[];
  currentFrame: number;
  fps: number;
  onSeek: (time: number) => void;
}

type Filter = 'all' | 'strike' | 'state' | 'grapple';

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all',    label: 'All' },
  { key: 'strike', label: 'Strikes' },
  { key: 'state',  label: 'Fight State' },
  { key: 'grapple',label: 'Grapple' },
];

function matchFilter(cat: string, filter: Filter): boolean {
  if (filter === 'all') return true;
  if (filter === 'grapple') return cat === 'grapple' || cat === 'event';
  if (filter === 'state') return cat === 'state' || cat === 'round';
  return cat === filter;
}

function fmtFrame(frame: number, fps: number): string {
  const secs = Math.max(0, Math.floor((frame - 1) / fps));
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function LiveFeed({ events, currentFrame, fps, onSeek }: LiveFeedProps) {
  const [filter, setFilter] = useState<Filter>('all');
  const scrollRef = useRef<HTMLDivElement>(null);

  const enriched = useMemo(() => events.map(e => ({
    ...e,
    cat: deriveEventCat(e.description),
    tc: fmtFrame(e.frame, fps),
  })), [events, fps]);

  const visible = useMemo(() =>
    enriched.filter(e => e.frame <= currentFrame && matchFilter(e.cat, filter)),
    [enriched, currentFrame, filter],
  );

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [visible.length]);

  return (
    <div className="glass" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '14px 16px 10px', display: 'flex', flexDirection: 'column', gap: 11, borderBottom: '1px solid var(--border-subtle)', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--f-red)', animation: 'pulse-ring 1.4s infinite', flexShrink: 0 }} />
          <span className="label" style={{ color: 'rgba(255,255,255,0.55)' }}>Live Play-by-Play</span>
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-disabled)', fontWeight: 600 }}>
            {visible.length} events
          </span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {FILTERS.map(f => (
            <button key={f.key} className={'pill' + (filter === f.key ? ' active' : '')} onClick={() => setFilter(f.key)}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Event list */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: 8, display: 'flex', flexDirection: 'column', gap: 9, overscrollBehavior: 'contain' }}>
        {visible.length === 0 ? (
          <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-disabled)', fontSize: 13, padding: 30 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 34, opacity: 0.3, display: 'block', marginBottom: 8 }}>sensors</span>
            Waiting for events…
          </div>
        ) : visible.map(e => {
          const c = eventColor(e.cat);
          const icon = eventIcon(e.cat);
          return (
            <button
              key={e.id}
              onClick={() => onSeek((e.frame - 1) / fps)}
              style={{ display: 'flex', gap: 11, alignItems: 'flex-start', textAlign: 'left', padding: '11px 13px', borderRadius: 11, border: `1px solid var(--border-subtle)`, background: 'var(--surface-inner)', borderLeft: `3px solid ${c}`, cursor: 'pointer', animation: 'feed-in .35s ease-out', width: '100%' }}
            >
              <span style={{ width: 28, height: 28, flexShrink: 0, borderRadius: 7, display: 'grid', placeItems: 'center', background: `color-mix(in srgb, ${c} 14%, transparent)`, border: `1px solid color-mix(in srgb, ${c} 30%, transparent)` }}>
                <span className="material-symbols-outlined" style={{ fontSize: 16, color: c }}>{icon}</span>
              </span>
              <span style={{ minWidth: 0, flex: 1 }}>
                <span style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.25, marginBottom: 2 }}>
                  {e.description}
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text-disabled)' }}>
                  <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-muted)', fontWeight: 700 }}>{e.tc}</span>
                  <span style={{ marginLeft: 'auto', opacity: 0.7 }}>#{e.frame}</span>
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
