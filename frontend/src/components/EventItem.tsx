import type { Event } from '../types/Event';

interface EventItemProps {
  event: Event;
  isNew?: boolean;
}

function getEventMeta(desc: string): { icon: string; color: string } {
  if (/punch|jab|cross|hook|uppercut|elbow|strike|hit|landed/i.test(desc))
    return { icon: 'bolt', color: '#00daf3' };
  if (/kick|knee/i.test(desc))
    return { icon: 'sports_martial_arts', color: '#00daf3' };
  if (/blocked|check/i.test(desc))
    return { icon: 'shield', color: '#94a3b8' };
  if (/takedown|ground|grapple|clinch|mount|guard|submission|sprawl/i.test(desc))
    return { icon: 'sports_kabaddi', color: '#ff7043' };
  if (/round/i.test(desc))
    return { icon: 'timer', color: '#a3c900' };
  return { icon: 'radio_button_checked', color: '#64748b' };
}

export default function EventItem({ event, isNew }: EventItemProps) {
  const { icon, color } = getEventMeta(event.description);

  return (
    <div
      className="event-item"
      style={{
        display: 'flex',
        gap: 10,
        padding: '10px 14px',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        borderLeft: `2px solid ${color}`,
        background: isNew ? 'rgba(0,218,243,0.05)' : 'transparent',
        transition: 'background 0.3s',
        cursor: 'default',
      }}
    >
      <div style={{
        width: 28,
        height: 28,
        borderRadius: 7,
        background: `${color}18`,
        border: `1px solid ${color}28`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        marginTop: 2,
      }}>
        <span className="material-symbols-outlined" style={{ fontSize: 14, color }}>
          {icon}
        </span>
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          fontSize: 10,
          color: 'rgba(255,255,255,0.2)',
          margin: '0 0 2px',
          fontVariantNumeric: 'tabular-nums',
          letterSpacing: '0.02em',
          fontWeight: 600,
        }}>
          Frame {event.frame}
        </p>
        <p style={{
          fontSize: 13,
          color: '#cbd5e1',
          margin: 0,
          lineHeight: 1.45,
          fontWeight: 500,
        }}>
          {event.description}
        </p>
      </div>
    </div>
  );
}
