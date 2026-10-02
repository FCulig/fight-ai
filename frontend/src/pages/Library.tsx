import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWindowWidth } from '../hooks/useWindowWidth';
import UploadDialog from '../components/UploadDialog';

export default function Library() {
  const width = useWindowWidth();
  const isMobile = width < 640;
  const [uploadOpen, setUploadOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <div style={{
      display: 'flex',
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 'calc(100vh - 58px)',
      padding: isMobile ? 16 : 24,
    }}>
      <div className="glass" style={{
        textAlign: 'center',
        padding: isMobile ? '36px 28px' : '48px 56px',
        width: '100%',
        maxWidth: 420,
      }}>
        <div style={{
          width: 56,
          height: 56,
          borderRadius: 8,
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid var(--border-glass)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 20px',
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 28, color: 'var(--text-secondary)' }}>
            video_library
          </span>
        </div>
        <h2 className="font-display" style={{
          fontSize: isMobile ? 24 : 28,
          lineHeight: 1,
          margin: '0 0 10px',
          color: 'var(--text-primary)',
        }}>
          Your library
        </h2>
        <p style={{ fontSize: 14, color: 'var(--text-muted)', margin: 0, lineHeight: 1.6 }}>
          Your fight video library will appear here.<br />
          Upload a video to get started.
        </p>
        <button
          className="btn-primary"
          onClick={() => setUploadOpen(true)}
          style={{
            marginTop: 24,
            fontWeight: 600,
            fontSize: 13,
            padding: '9px 22px',
          }}
        >
          Upload video
        </button>
        <UploadDialog
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onSuccess={() => { setUploadOpen(false); navigate('/', { state: { uploaded: Date.now() } }); }}
        />
      </div>
    </div>
  );
}
