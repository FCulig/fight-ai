import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import type { Fighter } from '../types/Fighter';
import type { Fight } from '../types/Fight';
import { uploadFight } from '../services/api';
import CornerSelect from './CornerSelect';
import ModeCard from './ModeCard';

interface UploadDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (fight: Fight, mode: 'ai' | 'manual') => void;
}

export default function UploadDialog({ open, onClose, onSuccess }: UploadDialogProps) {
  const [mode, setMode] = useState<'manual' | 'ai'>('ai');
  const [file, setFile] = useState<File | null>(null);
  const [drag, setDrag] = useState(false);
  const [redF, setRedF] = useState<Fighter | null>(null);
  const [blueF, setBlueF] = useState<Fighter | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setMode('ai');
      setFile(null);
      setDrag(false);
      setRedF(null);
      setBlueF(null);
      setUploading(false);
      setError(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open || uploading) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, uploading, onClose]);

  if (!open) return null;

  const takeFile = (f: File | null) => {
    if (f) { setFile(f); setError(null); }
  };

  const sizeMB = file ? (file.size / 1048576).toFixed(1) + ' MB' : '';
  const ready = !!file && !!redF && !!blueF;

  const handleSubmit = async () => {
    if (!ready || uploading) return;
    setUploading(true);
    setError(null);
    try {
      const fight = await uploadFight(file, redF.id, blueF.id, mode);
      onSuccess(fight, mode);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setUploading(false);
    }
  };

  const helperText = uploading
    ? 'Uploading…'
    : !file
      ? 'Add a video to continue'
      : !redF || !blueF
        ? 'Assign both corner fighters'
        : mode === 'manual'
          ? 'Fighters will be detected, then it\'s ready for you to label'
          : 'AI will process after upload';

  return createPortal(
    <div
      onClick={uploading ? undefined : onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000, display: 'grid', placeItems: 'center', padding: 24,
        background: 'rgba(3,5,7,0.66)', backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
        animation: 'fade-up .2s ease-out',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: 'min(640px, 100%)', maxHeight: '90vh', overflowY: 'auto', borderRadius: 18, padding: 0,
          background: 'rgba(11,15,20,0.97)',
          border: '1px solid rgba(255,255,255,0.07)',
          backdropFilter: 'blur(20px) saturate(160%)', WebkitBackdropFilter: 'blur(20px) saturate(160%)',
          boxShadow: '0 40px 120px -30px rgba(0,0,0,0.85)',
          animation: 'fade-up .25s ease-out',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, padding: '24px 26px 18px' }}>
          <div>
            <div className="font-display" style={{ fontSize: 30, letterSpacing: '0.03em', color: '#f1f5f9', lineHeight: 1 }}>UPLOAD VIDEO</div>
            <div style={{ fontSize: 13, color: '#64748b', fontWeight: 600, marginTop: 6 }}>Add a fight and choose how events get broken down.</div>
          </div>
          {!uploading && (
            <button
              onClick={onClose}
              style={{
                width: 34, height: 34, flexShrink: 0, borderRadius: 10, display: 'grid', placeItems: 'center',
                background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
                color: '#94a3b8', cursor: 'pointer',
              }}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
            </button>
          )}
        </div>

        {/* Dropzone */}
        <div style={{ padding: '0 26px' }}>
          <input
            ref={inputRef}
            type="file"
            accept="video/*"
            style={{ display: 'none' }}
            onChange={e => takeFile(e.target.files?.[0] ?? null)}
          />
          <div
            onClick={() => !uploading && inputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); if (!uploading) setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={e => { e.preventDefault(); setDrag(false); if (!uploading) takeFile(e.dataTransfer.files?.[0] ?? null); }}
            style={{
              cursor: uploading ? 'default' : 'pointer', borderRadius: 14,
              padding: file ? '16px 18px' : '26px 18px',
              border: `1.5px dashed ${drag ? '#00daf3' : 'rgba(255,255,255,0.07)'}`,
              background: drag ? 'rgba(0,218,243,0.08)' : 'rgba(0,0,0,0.30)',
              display: 'flex', alignItems: 'center', gap: 16,
              transition: 'border-color .14s, background .14s',
              opacity: uploading ? 0.5 : 1,
            }}
          >
            <span style={{
              width: 46, height: 46, flexShrink: 0, borderRadius: 12, display: 'grid', placeItems: 'center',
              background: file ? 'color-mix(in srgb, #a3c900 16%, transparent)' : 'rgba(255,255,255,0.05)',
              color: file ? '#a3c900' : '#94a3b8',
            }}>
              <span className="material-symbols-outlined" style={{ fontSize: 24 }}>{file ? 'check_circle' : 'movie'}</span>
            </span>
            {file ? (
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: '#f1f5f9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{file.name}</div>
                <div style={{ fontSize: 11.5, color: '#64748b', fontWeight: 600, marginTop: 2 }}>{sizeMB} · click to replace</div>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: '#cbd5e1' }}>Drag a video here, or <span style={{ color: '#00daf3' }}>browse</span></div>
                <div style={{ fontSize: 11.5, color: '#64748b', fontWeight: 600, marginTop: 2 }}>MP4, MOV or MKV · up to 4 GB</div>
              </div>
            )}
          </div>
        </div>

        {/* Corner assignment */}
        <div style={{ padding: '20px 26px 0' }}>
          <div style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'rgba(255,255,255,0.28)', marginBottom: 12 }}>
            Assign fighters to corners
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 13, alignItems: 'start' }}>
            <CornerSelect
              corner="Red corner"
              dotColor="#ff4d4d"
              value={redF}
              exclude={blueF?.id ?? null}
              onChange={setRedF}
              disabled={uploading}
            />
            <CornerSelect
              corner="Blue corner"
              dotColor="#3aa0ff"
              value={blueF}
              exclude={redF?.id ?? null}
              onChange={setBlueF}
              disabled={uploading}
            />
          </div>
        </div>

        {/* Annotation mode */}
        <div style={{ padding: '20px 26px 0' }}>
          <div style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'rgba(255,255,255,0.28)', marginBottom: 12 }}>
            How should events be annotated?
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 13 }}>
            <ModeCard
              active={mode === 'manual'}
              onClick={() => !uploading && setMode('manual')}
              icon="draw"
              title="Self-annotate"
              desc="You tag every strike, takedown and position change yourself on the timeline."
              points={[
                { icon: 'tune', text: 'Full editorial control' },
                { icon: 'schedule', text: 'Hands-on, slower' },
              ]}
            />
            <ModeCard
              active={mode === 'ai'}
              onClick={() => !uploading && setMode('ai')}
              icon="auto_awesome"
              title="AI annotation"
              desc="Our model detects and labels every event automatically — ready to review in minutes."
              points={[
                { icon: 'bolt', text: 'Fastest · fully automatic' },
                { icon: 'edit', text: 'Editable afterwards' },
              ]}
            />
          </div>
        </div>

        {/* Footer */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14,
          padding: '22px 26px 24px', marginTop: 20, borderTop: '1px solid rgba(255,255,255,0.05)',
        }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <span style={{ fontSize: 11.5, color: '#475569', fontWeight: 600 }}>{helperText}</span>
            {error && (
              <div style={{ fontSize: 11.5, color: '#ef4444', fontWeight: 600, marginTop: 4 }}>{error}</div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            {!uploading && (
              <button
                onClick={onClose}
                style={{
                  background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 8, color: '#94a3b8', padding: '8px 14px', fontWeight: 600,
                  fontSize: 12.5, cursor: 'pointer', fontFamily: 'inherit',
                }}
              >Cancel</button>
            )}
            <button
              onClick={handleSubmit}
              disabled={!ready || uploading}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                background: 'linear-gradient(135deg, #00daf3, #0099b0)', color: '#001f24',
                fontWeight: 700, fontSize: 13, border: 'none', borderRadius: 10,
                padding: '9px 16px', cursor: !ready || uploading ? 'not-allowed' : 'pointer',
                boxShadow: ready && !uploading ? '0 0 20px rgba(0,218,243,0.25)' : 'none',
                opacity: !ready || uploading ? 0.4 : 1,
                fontFamily: 'inherit',
              }}
            >
              {uploading ? (
                <>
                  <span className="material-symbols-outlined" style={{ fontSize: 18, animation: 'spin 1s linear infinite' }}>progress_activity</span>
                  Uploading…
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined" style={{ fontSize: 18 }}>{mode === 'manual' ? 'draw' : 'auto_awesome'}</span>
                  {mode === 'manual' ? 'Upload video' : 'Upload & analyze'}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
