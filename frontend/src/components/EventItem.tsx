import type { Event } from '../types/Event';

interface EventItemProps {
  event: Event;
  isNew?: boolean;
}

export default function EventItem({ event, isNew }: EventItemProps) {
  return (
    <div
      style={{
        padding: '12px 16px',
        borderBottom: '1px solid #2a2a2a',
        fontSize: '13px',
        lineHeight: '1.4',
        opacity: isNew ? 1 : 0.9,
      }}
    >
      <div style={{ color: '#999', fontSize: '12px', marginBottom: '4px' }}>
        Frame {event.frame}
      </div>
      <div style={{ color: '#e0e0e0' }}>
        {event.description}
      </div>
    </div>
  );
}
