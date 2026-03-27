import { useEffect, useRef, useState } from 'react';
import type { Event } from '../types/Event';
import EventItem from './EventItem';
import { useWindowWidth } from '../hooks/useWindowWidth';

interface EventFeedProps {
  events: Event[];
  currentFrame: number;
  loading: boolean;
  error: string | null;
}

type Filter = 'all' | 'strikes' | 'ground';

function isStrikeEvent(desc: string) {
  return /punch|kick|jab|cross|hook|uppercut|elbow|knee|strike|hit|landed|blocked/i.test(desc);
}

function isGroundEvent(desc: string) {
  return /takedown|ground|grapple|clinch|mount|guard|submission|sprawl/i.test(desc);
}

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'strikes', label: 'Strikes' },
  { key: 'ground', label: 'Fight State' },
];

const glassPanel: React.CSSProperties = {
  background: 'rgba(255,255,255,0.04)',
  backdropFilter: 'blur(20px) saturate(160%)',
  WebkitBackdropFilter: 'blur(20px) saturate(160%)',
  border: '1px solid rgba(255,255,255,0.07)',
  borderRadius: 16,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
};

export default function EventFeed({ events, currentFrame, loading, error }: EventFeedProps) {
  const feedRef = useRef<HTMLDivElement>(null);
  const previousFrameRef = useRef<number>(-1);
  const [activeFilter, setActiveFilter] = useState<Filter>('all');
  const width = useWindowWidth();
  const isMobile = width < 768;

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [events, currentFrame]);

  const visibleEvents = events.filter(e => e.frame <= currentFrame);

  const newEventId =
    currentFrame > previousFrameRef.current
      ? visibleEvents[visibleEvents.length - 1]?.id
      : null;

  useEffect(() => {
    previousFrameRef.current = currentFrame;
  }, [currentFrame]);

  const filteredEvents = visibleEvents.filter(e => {
    if (activeFilter === 'strikes') return isStrikeEvent(e.description);
    if (activeFilter === 'ground') return isGroundEvent(e.description);
    return true;
  });

  if (loading) {
    return (
      <div style={{ ...glassPanel, height: 120, alignItems: 'center', justifyContent: 'center', color: '#475569', fontSize: 13 }}>
        Loading events...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ ...glassPanel, height: 120, alignItems: 'center', justifyContent: 'center', color: '#ff7043', fontSize: 13, padding: 16, textAlign: 'center' }}>
        {error}
      </div>
    );
  }

  return (
    <div style={{ ...glassPanel, maxHeight: isMobile ? 360 : 540 }}>
      {/* Header */}
      <div style={{ padding: '14px 14px 0' }}>
        <p style={{
          fontSize: 10,
          fontWeight: 700,
          color: 'rgba(255,255,255,0.28)',
          margin: '0 0 10px',
          textTransform: 'uppercase',
          letterSpacing: '0.12em',
        }}>
          Event Timeline
        </p>

        {/* Filter pills */}
        <div style={{
          display: 'flex',
          gap: 4,
          background: 'rgba(0,0,0,0.3)',
          padding: 3,
          borderRadius: 10,
          border: '1px solid rgba(255,255,255,0.05)',
        }}>
          {FILTERS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveFilter(key)}
              style={{
                flex: 1,
                padding: isMobile ? '7px 6px' : '5px 6px',
                fontSize: 11,
                fontWeight: 700,
                borderRadius: 7,
                background: activeFilter === key ? 'rgba(0,218,243,0.15)' : 'transparent',
                color: activeFilter === key ? '#00daf3' : '#475569',
                border: activeFilter === key ? '1px solid rgba(0,218,243,0.25)' : '1px solid transparent',
                transition: 'all 0.18s',
                boxShadow: activeFilter === key ? '0 0 12px rgba(0,218,243,0.12)' : 'none',
                minHeight: isMobile ? 36 : 'auto',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ height: 1, background: 'rgba(255,255,255,0.05)', margin: '10px 0 0' }} />

      {/* Events */}
      <div ref={feedRef} style={{ flex: 1, overflowY: 'auto', overscrollBehavior: 'contain' }}>
        {filteredEvents.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 28, color: 'rgba(255,255,255,0.08)', display: 'block', marginBottom: 8 }}>
              sports_martial_arts
            </span>
            <p style={{ color: '#334155', fontSize: 13, margin: 0 }}>No events yet</p>
          </div>
        ) : (
          [...filteredEvents].reverse().map(event => (
            <EventItem key={event.id} event={event} isNew={event.id === newEventId} />
          ))
        )}
      </div>

      {/* Footer */}
      <div style={{ padding: '10px 14px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        <button
          className="btn-glass"
          style={{
            width: '100%',
            padding: isMobile ? '11px 12px' : '7px 12px',
            fontSize: 12,
            fontWeight: 600,
            color: 'rgba(0,218,243,0.7)',
            background: 'rgba(0,218,243,0.05)',
            border: '1px solid rgba(0,218,243,0.12)',
            borderRadius: 8,
            minHeight: isMobile ? 44 : 'auto',
          }}
        >
          View Full Lab Report
        </button>
      </div>
    </div>
  );
}
