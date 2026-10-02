import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useWindowWidth } from '../hooks/useWindowWidth';
import { useAuth } from '../hooks/useAuth';
import type { Role } from '../types/User';
import UploadDialog from './UploadDialog';

const NAV_LINKS: { label: string; to: string; minRole?: Role }[] = [
  { label: 'Analysis', to: '/' },
  { label: 'Library', to: '/library' },
  { label: 'Accuracy', to: '/accuracy' },
  { label: 'Data QA', to: '/training-data', minRole: 'labeller' },
  { label: 'Users', to: '/users', minRole: 'admin' },
];

export default function Header() {
  const width = useWindowWidth();
  const isMobile = width < 640;
  const [uploadOpen, setUploadOpen] = useState(false);
  const navigate = useNavigate();
  const { user, can, signOut } = useAuth();

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
      <nav style={{ display: 'flex', gap: 2, flex: 1, minWidth: 0, overflowX: 'auto', scrollbarWidth: 'none' }}>
        {NAV_LINKS.filter(({ minRole }) => !minRole || can(minRole)).map(({ label, to }) => (
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
        {can('admin') && (
          <button
            className="btn-upload"
            onClick={() => setUploadOpen(true)}
            style={{
              fontWeight: 600,
              fontSize: 13,
              height: 36,
              padding: isMobile ? '0 10px' : '0 16px',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>upload</span>
            {!isMobile && 'Upload video'}
          </button>
        )}

        {!isMobile && (
          <button className="icon-btn" style={{ width: 36, height: 36 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>notifications</span>
          </button>
        )}

        {!isMobile && (
          <div title={user.email} style={{ textAlign: 'right', lineHeight: 1.25, marginLeft: 6, maxWidth: 180 }}>
            <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user.name ?? user.email}
            </div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, fontWeight: 400, color: 'var(--text-muted)' }}>{user.role}</div>
          </div>
        )}
        <button className="icon-btn" onClick={signOut} title="Sign out" aria-label="Sign out" style={{ width: 36, height: 36 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>logout</span>
        </button>
      </div>
      {/* Both AI and manual uploads land on FightList — manual mode still needs
          detection/tracking/pose/corners/scoreboard/segmentation to run before
          the fight is ready to label, same live-progress UX as AI mode. */}
      {can('admin') && (
        <UploadDialog
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onSuccess={() => { setUploadOpen(false); navigate('/', { state: { uploaded: Date.now() } }); }}
        />
      )}
    </header>
  );
}
