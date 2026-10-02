import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import type { Fighter } from '../types/Fighter';
import type { Fight, FightPurpose } from '../types/Fight';
import { PURPOSE_LABELS } from '../types/Fight';
import { uploadFight } from '../services/api';
import CornerSelect from './CornerSelect';
import ModeCard from './ModeCard';

/**
 * The two purposes a self-annotated video can have. They must stay disjoint —
 * a fight that trains the model can't also be the yardstick it's measured by.
 */
const PURPOSE_CHOICES: { value: 'training_data' | 'reference'; desc: string }[] = [
  {
    value: 'training_data',
    desc: 'Labels feed model training. Never scored against the pipeline.',
  },
  {
    value: 'reference',
    desc: 'Held out of training. Used to measure pipeline accuracy.',
  },
];

interface UploadDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (fight: Fight, purpose: FightPurpose) => void;
}

export default function UploadDialog({ open, onClose, onSuccess }: UploadDialogProps) {
  const [mode, setMode] = useState<'manual' | 'ai'>('ai');
  // Deliberately starts null: the training/eval split must never be decided
  // by inattention, so Upload stays disabled until one is picked.
  const [manualPurpose, setManualPurpose] = useState<'training_data' | 'reference' | null>(null);
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
      setManualPurpose(null);
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
  const purpose: FightPurpose | null = mode === 'ai' ? 'ai_labeled' : manualPurpose;
  const ready = !!file && !!redF && !!blueF && !!purpose;

  const handleSubmit = async () => {
    if (!ready || uploading) return;
    setUploading(true);
    setError(null);
    try {
      const fight = await uploadFight(file, redF.id, blueF.id, purpose);
      onSuccess(fight, purpose);
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
        : mode === 'manual' && !manualPurpose
          ? 'Choose what this footage is for'
          : mode === 'manual'
            ? 'Fighters will be detected, then it\'s ready for you to label'
            : 'AI will process after upload';

  return createPortal(
    <div
      onClick={uploading ? undefined : onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000, display: 'grid', placeItems: 'center', padding: 24,
        background: 'rgba(11,11,12,0.72)', backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)',
        animation: 'fade-up .2s ease-out',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: 'min(640px, 100%)', maxHeight: '90vh', overflowY: 'auto', borderRadius: 12, padding: 0,
          background: 'var(--surface-glass)',
          border: '1px solid var(--border-glass)',
          boxShadow: '0 40px 120px -30px rgba(0,0,0,0.85)',
          animation: 'fade-up .25s ease-out',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, padding: '24px 26px 18px' }}>
          <div>
            <div className="font-display" style={{ fontSize: 28, color: 'var(--text-primary)', lineHeight: 1 }}>Upload video</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 500, marginTop: 6 }}>Add a fight and choose how events get broken down.</div>
          </div>
          {!uploading && (
            <button
              onClick={onClose}
              className="icon-btn"
              style={{ width: 34, height: 34 }}
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
              cursor: uploading ? 'default' : 'pointer', borderRadius: 8,
              padding: file ? '16px 18px' : '26px 18px',
              border: `1.5px dashed ${drag ? 'var(--text-primary)' : 'var(--border-strong)'}`,
              background: drag ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.30)',
              display: 'flex', alignItems: 'center', gap: 16,
              transition: 'border-color .14s, background .14s',
              opacity: uploading ? 0.5 : 1,
            }}
          >
            <span style={{
              width: 46, height: 46, flexShrink: 0, borderRadius: 8, display: 'grid', placeItems: 'center',
              background: file ? 'color-mix(in srgb, var(--green-500) 16%, transparent)' : 'rgba(255,255,255,0.05)',
              color: file ? 'var(--green-500)' : 'var(--text-tertiary)',
            }}>
              <span className="material-symbols-outlined" style={{ fontSize: 24 }}>{file ? 'check_circle' : 'movie'}</span>
            </span>
            {file ? (
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{file.name}</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-muted)', fontWeight: 500, marginTop: 2 }}>{sizeMB} · click to replace</div>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-secondary)' }}>Drag a video here, or <span style={{ color: 'var(--text-primary)', textDecoration: 'underline', textUnderlineOffset: 3 }}>browse</span></div>
                <div style={{ fontSize: 11.5, color: 'var(--text-muted)', fontWeight: 500, marginTop: 2 }}>MP4, MOV or MKV · up to 4 GB</div>
              </div>
            )}
          </div>
        </div>

        {/* Corner assignment */}
        <div style={{ padding: '20px 26px 0' }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 12 }}>
            Assign fighters to corners
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 13, alignItems: 'start' }}>
            <CornerSelect
              corner="Red corner"
              dotColor="var(--f-red)"
              value={redF}
              exclude={blueF?.id ?? null}
              onChange={setRedF}
              disabled={uploading}
            />
            <CornerSelect
              corner="Blue corner"
              dotColor="var(--f-blue)"
              value={blueF}
              exclude={redF?.id ?? null}
              onChange={setBlueF}
              disabled={uploading}
            />
          </div>
        </div>

        {/* Annotation mode */}
        <div style={{ padding: '20px 26px 0' }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 12 }}>
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

        {/* Purpose — manual track only. AI uploads are always 'ai_labeled'. */}
        {mode === 'manual' && (
          <div style={{ padding: '20px 26px 0' }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 12 }}>
              What is this footage for?
            </div>
            <div style={{ display: 'grid', gap: 9 }}>
              {PURPOSE_CHOICES.map(choice => {
                const active = manualPurpose === choice.value;
                return (
                  <label
                    key={choice.value}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: 11,
                      padding: '11px 13px', borderRadius: 6,
                      cursor: uploading ? 'default' : 'pointer',
                      background: active ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.30)',
                      border: `1px solid ${active ? 'var(--text-primary)' : 'var(--border-glass)'}`,
                      transition: 'border-color .14s, background .14s',
                      opacity: uploading ? 0.5 : 1,
                    }}
                  >
                    <input
                      type="radio"
                      name="fight-purpose"
                      value={choice.value}
                      checked={active}
                      disabled={uploading}
                      onChange={() => setManualPurpose(choice.value)}
                      style={{ accentColor: 'var(--text-primary)', width: 15, height: 15, marginTop: 1, flexShrink: 0, cursor: 'inherit' }}
                    />
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: active ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                        {PURPOSE_LABELS[choice.value]}
                      </div>
                      <div style={{ fontSize: 11.5, color: 'var(--text-muted)', fontWeight: 500, marginTop: 3, lineHeight: 1.45 }}>
                        {choice.desc}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>
        )}

        {/* Footer */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14,
          padding: '22px 26px 24px', marginTop: 20, borderTop: '1px solid rgba(255,255,255,0.05)',
        }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <span style={{ fontSize: 11.5, color: 'var(--text-disabled)', fontWeight: 500 }}>{helperText}</span>
            {error && (
              <div style={{ fontSize: 11.5, color: 'var(--red-500)', fontWeight: 500, marginTop: 4 }}>{error}</div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            {!uploading && (
              <button
                onClick={onClose}
                className="btn-glass"
                style={{ padding: '8px 14px', fontWeight: 500, fontSize: 12.5 }}
              >Cancel</button>
            )}
            <button
              onClick={handleSubmit}
              disabled={!ready || uploading}
              className="btn-primary"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                fontWeight: 600, fontSize: 13,
                padding: '9px 16px', cursor: !ready || uploading ? 'not-allowed' : 'pointer',
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
