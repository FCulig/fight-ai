import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useWindowWidth } from '../hooks/useWindowWidth';
import UploadDialog from './UploadDialog';

const NAV_LINKS = [
  { label: 'Analysis', to: '/' },
  { label: 'Library', to: '/library' },
  { label: 'Accuracy', to: '/accuracy' },
  { label: 'Data QA', to: '/training-data' },
];

export default function Header() {
  const width = useWindowWidth();
  const isMobile = width < 640;
  const [uploadOpen, setUploadOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      gap: isMobile ? 10 : 6,
      padding: isMobile ? '0 14px' : '0 28px',
      height: 64,
      background: 'var(--header-bg)',
      backdropFilter: 'blur(18px) saturate(1.6)',
      WebkitBackdropFilter: 'blur(18px) saturate(1.6)',
      borderBottom: '1px solid var(--border-glass)',
      width: '100%',
      flexShrink: 0,
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Logo */}
      <span className="logo" style={{ fontSize: isMobile ? 20 : 26, marginRight: isMobile ? 10 : 22 }}>
        Fightlytics
      </span>

      {/* Nav */}
      <nav style={{ display: 'flex', gap: 2, flex: 1 }}>
        {NAV_LINKS.map(({ label, to }) => (
          <NavLink
            key={label}
            to={to}
            end={to === '/'}
            className={({ isActive }) => 'nav-link' + (isActive ? ' active' : '')}
            style={{
              padding: isMobile ? '5px 10px' : '8px 16px',
              fontSize: isMobile ? 12 : 13,
              whiteSpace: 'nowrap',
            }}
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
        <button
          className="btn-upload"
          onClick={() => setUploadOpen(true)}
          style={{
            fontWeight: 700,
            fontSize: 12,
            height: 36,
            padding: isMobile ? '0 10px' : '0 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 5,
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>upload</span>
          {!isMobile && 'Upload Video'}
        </button>

        {!isMobile && ['notifications', 'account_circle'].map(icon => (
          <button
            key={icon}
            className="icon-btn"
            style={{ width: 36, height: 36 }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{icon}</span>
          </button>
        ))}
      </div>
      {/* Both AI and manual uploads land on FightList — manual mode still needs
          detection/tracking/pose/corners/scoreboard/segmentation to run before
          the fight is ready to label, same live-progress UX as AI mode. */}
      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSuccess={() => { setUploadOpen(false); navigate('/', { state: { uploaded: Date.now() } }); }}
      />
    </header>
  );
}
