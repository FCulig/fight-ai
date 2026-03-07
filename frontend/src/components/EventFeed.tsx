import { useEffect, useRef } from 'react';
import type { Event } from '../types/Event';
import EventItem from './EventItem';

interface EventFeedProps {
  events: Event[];
  currentFrame: number;
  loading: boolean;
  error: string | null;
}

export default function EventFeed({ events, currentFrame, loading, error }: EventFeedProps) {
  const feedRef = useRef<HTMLDivElement>(null);
  const previousFrameRef = useRef<number>(-1);

  // Auto-scroll to bottom when new events appear
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [events, currentFrame]);

  // Filter events to show only those up to current frame
  const visibleEvents = events.filter(event => event.frame <= currentFrame);
  
  // Determine which event is new (appeared in the last frame)
  const newEventId =
    currentFrame > previousFrameRef.current
      ? visibleEvents[visibleEvents.length - 1]?.id
      : null;

  useEffect(() => {
    previousFrameRef.current = currentFrame;
  }, [currentFrame]);

  if (loading) {
    return (
      <div
        style={{
          width: '320px',
          height: '600px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#1a1a1a',
          borderRadius: '8px',
          border: '1px solid #2a2a2a',
          color: '#999',
          fontSize: '13px',
        }}
      >
        Loading events...
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          width: '320px',
          height: '600px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#1a1a1a',
          borderRadius: '8px',
          border: '1px solid #2a2a2a',
          color: '#ff6b6b',
          fontSize: '13px',
          padding: '16px',
          textAlign: 'center',
        }}
      >
        {error}
      </div>
    );
  }

  return (
    <div
      style={{
        width: '320px',
        height: '600px',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#1a1a1a',
        borderRadius: '8px',
        border: '1px solid #2a2a2a',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #2a2a2a',
          backgroundColor: '#0f0f0f',
          fontSize: '14px',
          fontWeight: '600',
          color: '#e0e0e0',
        }}
      >
        Fight Events
      </div>

      {/* Events List */}
      <div
        ref={feedRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          overscrollBehavior: 'contain',
        }}
      >
        {visibleEvents.length === 0 ? (
          <div
            style={{
              padding: '16px',
              color: '#666',
              fontSize: '13px',
              textAlign: 'center',
              marginTop: '24px',
            }}
          >
            No events yet...
          </div>
        ) : (
          visibleEvents.map(event => (
            <EventItem
              key={event.id}
              event={event}
              isNew={event.id === newEventId}
            />
          ))
        )}
      </div>

      {/* Footer */}
      <div
        style={{
          padding: '8px 16px',
          borderTop: '1px solid #2a2a2a',
          backgroundColor: '#0f0f0f',
          fontSize: '11px',
          color: '#666',
        }}
      >
        {visibleEvents.length} event{visibleEvents.length !== 1 ? 's' : ''} up to frame {currentFrame}
      </div>
    </div>
  );
}
