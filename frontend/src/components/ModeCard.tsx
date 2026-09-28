interface ModeCardPoint {
  icon: string;
  text: string;
}

interface ModeCardProps {
  active: boolean;
  onClick: () => void;
  icon: string;
  badge?: string;
  badgeColor?: string;
  title: string;
  desc: string;
  points: ModeCardPoint[];
  comingSoon?: boolean;
}

export default function ModeCard({ active, onClick, icon, badge, badgeColor, title, desc, points, comingSoon }: ModeCardProps) {
  return (
    <button
      onClick={comingSoon ? undefined : onClick}
      disabled={comingSoon}
      style={{
        position: 'relative',
        textAlign: 'left',
        cursor: comingSoon ? 'not-allowed' : 'pointer',
        padding: '20px 18px 18px',
        borderRadius: 14,
        background: active ? 'color-mix(in srgb, var(--accent) 9%, transparent)' : 'var(--surface-inner)',
        border: `1.5px solid ${active ? 'var(--accent)' : 'var(--border-glass)'}`,
        boxShadow: 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        transition: 'transform .14s',
      }}
    >
      {comingSoon && (
        <span style={{
          position: 'absolute', inset: 0, zIndex: 2, borderRadius: 14, display: 'grid', placeItems: 'center',
          background: 'rgba(8,11,15,0.74)', backdropFilter: 'blur(1.5px)', WebkitBackdropFilter: 'blur(1.5px)',
        }}>
          <span style={{
            fontSize: 11, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase',
            color: 'rgba(241,245,249,0.8)', background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.07)', padding: '6px 13px', borderRadius: 999,
          }}>Coming soon</span>
        </span>
      )}

      <span style={{
        position: 'absolute', top: 14, right: 14, width: 20, height: 20, borderRadius: '50%',
        display: 'grid', placeItems: 'center',
        border: `1.5px solid ${active ? 'var(--accent)' : 'var(--border-glass)'}`,
        background: active ? 'var(--accent)' : 'transparent',
      }}>
        {active && <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--accent-on)' }}>check</span>}
      </span>

      <span style={{
        width: 42, height: 42, borderRadius: 11, display: 'grid', placeItems: 'center',
        background: active ? 'var(--accent)' : 'rgba(255,255,255,0.06)',
        color: active ? 'var(--accent-on)' : 'var(--text-tertiary)',
        boxShadow: 'none',
        transition: 'transform .14s',
      }}>
        <span className="material-symbols-outlined" style={{ fontSize: 24 }}>{icon}</span>
      </span>

      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>{title}</span>
          {badge && badgeColor && (
            <span style={{
              fontSize: 9.5, fontWeight: 800, letterSpacing: '0.06em', textTransform: 'uppercase',
              color: badgeColor, background: `color-mix(in srgb, ${badgeColor} 16%, transparent)`,
              border: `1px solid color-mix(in srgb, ${badgeColor} 36%, transparent)`,
              padding: '2px 7px', borderRadius: 5,
            }}>{badge}</span>
          )}
        </div>
        <p style={{ margin: '6px 0 0', fontSize: 12.5, lineHeight: 1.45, color: 'var(--text-tertiary)' }}>{desc}</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 2 }}>
        {points.map((p, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11.5, fontWeight: 600, color: 'var(--text-muted)' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, color: active ? 'var(--accent)' : 'var(--text-disabled)' }}>{p.icon}</span>
            {p.text}
          </span>
        ))}
      </div>
    </button>
  );
}
