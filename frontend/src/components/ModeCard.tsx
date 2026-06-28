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
        background: active ? 'rgba(0,218,243,0.09)' : 'rgba(0,0,0,0.30)',
        border: `1.5px solid ${active ? 'rgba(0,218,243,0.6)' : 'rgba(255,255,255,0.07)'}`,
        boxShadow: active ? '0 0 0 3px rgba(0,218,243,0.15), 0 12px 34px -16px rgba(0,218,243,0.6)' : 'none',
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
        border: `1.5px solid ${active ? '#00daf3' : 'rgba(255,255,255,0.07)'}`,
        background: active ? '#00daf3' : 'transparent',
      }}>
        {active && <span className="material-symbols-outlined" style={{ fontSize: 14, color: '#001f24' }}>check</span>}
      </span>

      <span style={{
        width: 42, height: 42, borderRadius: 11, display: 'grid', placeItems: 'center',
        background: active ? '#00daf3' : 'rgba(255,255,255,0.06)',
        color: active ? '#001f24' : '#94a3b8',
        boxShadow: active ? '0 0 18px rgba(0,218,243,0.45)' : 'none',
        transition: 'transform .14s',
      }}>
        <span className="material-symbols-outlined" style={{ fontSize: 24 }}>{icon}</span>
      </span>

      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 16, fontWeight: 800, color: '#f1f5f9', letterSpacing: '-0.01em' }}>{title}</span>
          {badge && badgeColor && (
            <span style={{
              fontSize: 9.5, fontWeight: 800, letterSpacing: '0.06em', textTransform: 'uppercase',
              color: badgeColor, background: `color-mix(in srgb, ${badgeColor} 16%, transparent)`,
              border: `1px solid color-mix(in srgb, ${badgeColor} 36%, transparent)`,
              padding: '2px 7px', borderRadius: 5,
            }}>{badge}</span>
          )}
        </div>
        <p style={{ margin: '6px 0 0', fontSize: 12.5, lineHeight: 1.45, color: '#94a3b8' }}>{desc}</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 2 }}>
        {points.map((p, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11.5, fontWeight: 600, color: '#64748b' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, color: active ? '#00daf3' : '#475569' }}>{p.icon}</span>
            {p.text}
          </span>
        ))}
      </div>
    </button>
  );
}
