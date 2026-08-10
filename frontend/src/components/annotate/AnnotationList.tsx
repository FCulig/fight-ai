import { useRef, useEffect } from 'react';
import type { Event } from '../../types/Event';
import { colorForAction, iconForAction, formatFrameClock } from './taxonomy';

interface AnnotationListProps {
  shown: Event[];
  fps: number;
  onSeek: (frame: number) => void;
  onDelete: (id: number) => void;
  flashId: number | null;
}

export default function AnnotationList({ shown, fps, onSeek, onDelete, flashId }: AnnotationListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [shown.length]);

  return (
    <div
      ref={scrollRef}
      style={{
        maxHeight: 256, overflowY: 'auto', padding: '4px 2px',
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(320px,1fr))', gap: 9,
      }}
    >
      {shown.length === 0 && (
        <div style={{ gridColumn: '1/-1', textAlign: 'center', color: 'var(--text-disabled)', fontSize: 13, padding: '30px 20px' }}>
          <span className="material-symbols-outlined" style={{ fontSize: 34, opacity: 0.3, display: 'block', marginBottom: 8 }}>add_box</span>
          No annotations yet. Select a fighter, then log an event.
        </div>
      )}
      {shown.map(e => {
        const c = colorForAction(e.action);
        return (
          <div
            key={e.id}
            onClick={() => onSeek(e.frame)}
            style={{
              display: 'flex', gap: 11, alignItems: 'flex-start', padding: '11px 12px', borderRadius: 11,
              cursor: 'pointer', position: 'relative', border: '1px solid var(--border-subtle)',
              background: 'var(--surface-inner)', borderLeft: `3px solid ${c}`,
              boxShadow: e.id === flashId ? `0 0 0 1.5px ${c}, 0 0 18px -4px ${c}` : 'none',
              animation: 'feed-in .3s ease-out',
            }}
          >
            <span style={{
              width: 28, height: 28, flexShrink: 0, borderRadius: 7, display: 'grid', placeItems: 'center',
              background: `color-mix(in srgb, ${c} 14%, transparent)`, border: `1px solid color-mix(in srgb, ${c} 30%, transparent)`,
            }}>
              <span className="material-symbols-outlined" style={{ fontSize: 16, color: c }}>{iconForAction(e.action)}</span>
            </span>
            <span style={{ minWidth: 0, flex: 1 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 2 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.25 }}>{e.description}</span>
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text-disabled)' }}>
                <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-muted)', fontWeight: 700 }}>{formatFrameClock(e.frame, fps)}</span>
                <span style={{ marginLeft: 'auto', opacity: 0.7 }}>#{e.frame}</span>
              </span>
            </span>
            <button
              title="Delete"
              onClick={ev => { ev.stopPropagation(); onDelete(e.id); }}
              style={{
                position: 'absolute', top: 8, right: 8, width: 22, height: 22, borderRadius: 6, border: 'none',
                cursor: 'pointer', background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)',
                display: 'grid', placeItems: 'center',
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>close</span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
