import { useEffect } from 'react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  /** Body copy — spell out what the action destroys, not just that it is permanent. */
  message: React.ReactNode;
  confirmLabel: string;
  confirmIcon?: string;
  /** Renders the confirm button in red. Leave off for neutral confirmations. */
  danger?: boolean;
  /** In-flight: buttons disable, confirm spins, escape/click-outside stop dismissing. */
  busy?: boolean;
  error?: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  confirmIcon = 'check',
  danger = false,
  busy = false,
  error = null,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open || busy) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;

  const accent = danger ? 'var(--red-500)' : 'var(--text-primary)';

  return (
    <div
      onClick={busy ? undefined : onCancel}
      style={{
        position: 'fixed', inset: 0, zIndex: 200, display: 'grid', placeItems: 'center',
        background: 'rgba(11,11,12,0.72)', backdropFilter: 'blur(6px)', animation: 'feed-in .18s ease-out',
      }}
    >
      <div onClick={e => e.stopPropagation()} className="glass" style={{ width: 420, maxWidth: '92vw', padding: '22px 24px 24px', borderRadius: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 22, color: accent }}>
            {danger ? 'delete_forever' : 'help'}
          </span>
          <span className="font-display" style={{ fontSize: 23, color: 'var(--text-primary)' }}>
            {title}
          </span>
          <button onClick={onCancel} disabled={busy} className="icon-btn" style={{ marginLeft: 'auto', width: 32, height: 32, opacity: busy ? 0.35 : 1 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
          </button>
        </div>

        <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 22 }}>
          {message}
        </div>

        {error && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, padding: '9px 12px',
            borderRadius: 6, border: '1px solid rgba(239,68,68,0.25)', background: 'rgba(239,68,68,0.08)',
            color: 'var(--red-500)', fontSize: 12.5, fontWeight: 500,
          }}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>error</span>
            {error}
          </div>
        )}

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={onCancel}
            disabled={busy}
            style={{
              flex: 1, padding: '11px', borderRadius: 6, cursor: busy ? 'not-allowed' : 'pointer',
              fontWeight: 600, fontSize: 13, border: '1px solid var(--border-strong)',
              background: 'transparent', color: 'var(--text-primary)',
              opacity: busy ? 0.5 : 1, fontFamily: 'inherit',
            }}
          >Cancel</button>
          <button
            onClick={onConfirm}
            disabled={busy}
            style={{
              flex: 1.4, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
              padding: '11px', borderRadius: 6, cursor: busy ? 'not-allowed' : 'pointer',
              fontWeight: 600, fontSize: 13, border: 'none',
              color: danger ? '#fff' : 'var(--bg-base)',
              background: accent,
              opacity: busy ? 0.6 : 1, fontFamily: 'inherit',
            }}
          >
            <span
              className="material-symbols-outlined"
              style={{ fontSize: 18, animation: busy ? 'spin 1.5s linear infinite' : undefined }}
            >
              {busy ? 'progress_activity' : confirmIcon}
            </span>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
