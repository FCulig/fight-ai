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
      <div style={{
        textAlign: 'center',
        background: 'rgba(255,255,255,0.04)',
        backdropFilter: 'blur(24px) saturate(160%)',
        WebkitBackdropFilter: 'blur(24px) saturate(160%)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: 20,
        padding: isMobile ? '36px 28px' : '48px 56px',
        boxShadow: '0 8px 40px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06)',
        width: '100%',
        maxWidth: 420,
      }}>
        <div style={{
          width: 64,
          height: 64,
          borderRadius: 16,
          background: 'rgba(0,218,243,0.08)',
          border: '1px solid rgba(0,218,243,0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 20px',
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 32, color: '#00daf3' }}>
            video_library
          </span>
        </div>
        <h2 style={{
          fontSize: isMobile ? 18 : 22,
          fontWeight: 800,
          margin: '0 0 10px',
          background: 'linear-gradient(90deg, #f1f5f9, rgba(255,255,255,0.5))',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          letterSpacing: '-0.02em',
        }}>
          Your Library
        </h2>
        <p style={{ fontSize: 14, color: '#475569', margin: 0, lineHeight: 1.6 }}>
          Your fight video library will appear here.<br />
          Upload a video to get started.
        </p>
        <button
          onClick={() => setUploadOpen(true)}
          style={{
            marginTop: 24,
            background: 'linear-gradient(135deg, #00daf3 0%, #0099b0 100%)',
            color: '#001f24',
            fontWeight: 700,
            fontSize: 13,
            padding: '9px 22px',
            borderRadius: 10,
            boxShadow: '0 0 20px rgba(0,218,243,0.25)',
          }}
        >
          Upload Video
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
