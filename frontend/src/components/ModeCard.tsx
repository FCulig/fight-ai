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
        borderRadius: 8,
        background: active ? 'rgba(255,255,255,0.05)' : 'var(--surface-inner)',
        border: `1.5px solid ${active ? 'var(--text-primary)' : 'var(--border-glass)'}`,
        boxShadow: 'none',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        transition: 'transform .14s',
      }}
    >
      {comingSoon && (
        <span style={{
          position: 'absolute', inset: 0, zIndex: 2, borderRadius: 8, display: 'grid', placeItems: 'center',
          background: 'rgba(11,11,12,0.74)', backdropFilter: 'blur(1.5px)', WebkitBackdropFilter: 'blur(1.5px)',
        }}>
          <span style={{
            fontSize: 12, fontWeight: 500,
            color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.06)',
            border: '1px solid var(--border-glass)', padding: '6px 13px', borderRadius: 6,
          }}>Coming soon</span>
        </span>
      )}

      <span style={{
        position: 'absolute', top: 14, right: 14, width: 20, height: 20, borderRadius: '50%',
        display: 'grid', placeItems: 'center',
        border: `1.5px solid ${active ? 'var(--text-primary)' : 'var(--border-strong)'}`,
        background: active ? 'var(--text-primary)' : 'transparent',
      }}>
        {active && <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--bg-base)' }}>check</span>}
      </span>

      <span style={{
        width: 42, height: 42, borderRadius: 6, display: 'grid', placeItems: 'center',
        background: active ? 'var(--text-primary)' : 'rgba(255,255,255,0.06)',
        color: active ? 'var(--bg-base)' : 'var(--text-tertiary)',
        boxShadow: 'none',
        transition: 'transform .14s',
      }}>
        <span className="material-symbols-outlined" style={{ fontSize: 24 }}>{icon}</span>
      </span>

      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
          {badge && badgeColor && (
            <span style={{
              fontSize: 11, fontWeight: 500,
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
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11.5, fontWeight: 500, color: 'var(--text-muted)' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, color: active ? 'var(--text-primary)' : 'var(--text-disabled)' }}>{p.icon}</span>
            {p.text}
          </span>
        ))}
      </div>
    </button>
  );
}
