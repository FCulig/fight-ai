import { NavLink } from 'react-router-dom';
import { useWindowWidth } from '../hooks/useWindowWidth';

const NAV_LINKS = [
  { label: 'Analysis', to: '/' },
  { label: 'Library', to: '/library' },
];

export default function Header() {
  const width = useWindowWidth();
  const isMobile = width < 640;

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      gap: isMobile ? 10 : 24,
      padding: isMobile ? '0 14px' : '0 28px',
      height: 58,
      background: 'rgba(5, 7, 9, 0.72)',
      backdropFilter: 'blur(24px) saturate(160%)',
      WebkitBackdropFilter: 'blur(24px) saturate(160%)',
      borderBottom: '1px solid rgba(255,255,255,0.06)',
      width: '100%',
      flexShrink: 0,
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Logo */}
      <span style={{
        fontSize: isMobile ? 15 : 17,
        fontWeight: 800,
        background: 'linear-gradient(90deg, #00daf3, #7c3aed)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        backgroundClip: 'text',
        letterSpacing: '-0.03em',
        flexShrink: 0,
      }}>
        Fight.AI
      </span>

      {/* Nav */}
      <nav style={{ display: 'flex', gap: 2, flex: 1 }}>
        {NAV_LINKS.map(({ label, to }) => (
          <NavLink
            key={label}
            to={to}
            end={to === '/'}
            className="nav-link"
            style={({ isActive }) => ({
              padding: isMobile ? '5px 10px' : '5px 14px',
              borderRadius: 8,
              fontSize: isMobile ? 12 : 13,
              fontWeight: 600,
              color: isActive ? '#00daf3' : '#64748b',
              background: isActive ? 'rgba(0,218,243,0.1)' : 'transparent',
              border: isActive ? '1px solid rgba(0,218,243,0.18)' : '1px solid transparent',
              transition: 'all 0.2s',
              textDecoration: 'none',
              whiteSpace: 'nowrap',
            })}
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        <button
          className="btn-primary"
          style={{
            background: 'linear-gradient(135deg, #00daf3 0%, #0099b0 100%)',
            color: '#001f24',
            fontWeight: 700,
            fontSize: 12,
            padding: isMobile ? '6px 10px' : '6px 16px',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            boxShadow: '0 0 16px rgba(0,218,243,0.2)',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>upload</span>
          {!isMobile && 'Upload Video'}
        </button>

        {!isMobile && ['notifications', 'account_circle'].map(icon => (
          <button
            key={icon}
            className="btn-glass"
            style={{ padding: 7, borderRadius: 8, minWidth: 34, minHeight: 34 }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{icon}</span>
          </button>
        ))}
      </div>
    </header>
  );
}
