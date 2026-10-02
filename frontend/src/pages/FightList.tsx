import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useFights } from '../hooks/useFights';
import { useFightStream } from '../hooks/useFightStream';
import { useWindowWidth } from '../hooks/useWindowWidth';
import { useAuth } from '../hooks/useAuth';
import { deleteFight } from '../services/api';
import ConfirmDialog from '../components/ConfirmDialog';

import type { Fight } from '../types/Fight';
import FightPurposeBadge from '../components/FightPurposeBadge';
import { STATE_PROGRESS, STATE_LABELS, TERMINAL_STATES, isFightViewable, isLabelingReady, isInvalid, needsRoundReview } from '../types/Fight';
import { fightLabel } from '../utils/fightLabel';

function invalidReason(fight: Fight): string {
  if (fight.reported_frames == null || fight.decoded_frames == null) return 'The source video failed to decode.';
  const missing = fight.reported_frames - fight.decoded_frames;
  const pct = fight.reported_frames > 0 ? Math.round((missing / fight.reported_frames) * 100) : 0;
  return `Container reports ${fight.reported_frames} frames, only ${fight.decoded_frames} decode `
    + `(${pct}% missing) — the file is an incomplete download.`;
}

const formatLength = (secs: number) => `${Math.floor(secs / 60)}:${String(Math.floor(secs % 60)).padStart(2, '0')}`;
const formatAdded = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

export default function FightList() {
  const navigate = useNavigate();
  const location = useLocation();
  const { fights, setFights, loading, error, refetch } = useFights();
  const { can } = useAuth();
  const width = useWindowWidth();
  const isMobile = width < 640;
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Fight | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const uploadedAt = (location.state as { uploaded?: number } | null)?.uploaded;
  useEffect(() => {
    if (uploadedAt) refetch();
  }, [uploadedAt, refetch]);

  const hasInProgress = fights.some(f => !TERMINAL_STATES.has(f.state));
  useFightStream(setFights, hasInProgress);

  const handleDelete = async () => {
    if (!pendingDelete) return;
    const fightId = pendingDelete.id;
    setDeletingId(fightId);
    setDeleteError(null);
    try {
      await deleteFight(fightId);
      setFights(prev => prev.filter(f => f.id !== fightId));
      setPendingDelete(null);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete fight');
    } finally {
      setDeletingId(null);
    }
  };

  // Fights still moving through the pipeline come first, then anything that
  // needs attention, then the rest in the order the API returned them.
  const rank = (f: Fight) => (f.state === 'failed' || isInvalid(f.state) ? 1 : isFightViewable(f.state) || isLabelingReady(f.state) ? 2 : 0);
  const ordered = fights.map((fight, i) => ({ fight, i })).sort((a, b) => rank(a.fight) - rank(b.fight) || a.i - b.i);

  const columns = '24px minmax(0, 2.3fr) 124px minmax(0, 1.25fr) 64px 132px 96px 30px';
  const cell: React.CSSProperties = { fontSize: 12.5, color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' };
  const mono: React.CSSProperties = { ...cell, fontFamily: 'var(--mono)', fontSize: 12, fontVariantNumeric: 'tabular-nums' };

  return (
    <div style={{
      maxWidth: 1180,
      width: '100%',
      margin: '0 auto',
      padding: isMobile ? '20px 16px' : '40px 30px',
    }}>
      <div className="anim-fade-up anim-delay-1" style={{ marginBottom: 24 }}>
        <span className="eyebrow">Analysis</span>
        <h1 className="font-display" style={{
          fontSize: isMobile ? 30 : 'clamp(32px, 4vw, 48px)',
          lineHeight: 1,
          margin: '10px 0 0',
          color: 'var(--text-primary)',
        }}>
          Fights.
        </h1>
        <p style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)', margin: '10px 0 0' }}>
          Select a fight to open the analysis player.
        </p>
      </div>

      {loading && (
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Loading…</p>
      )}

      {error && (
        <p style={{ color: 'var(--red-500)', fontSize: 14 }}>{error}</p>
      )}

      {!loading && !error && fights.length === 0 && (
        <div className="glass" style={{ padding: isMobile ? '36px 24px' : '48px 40px', textAlign: 'center' }}>
          <span className="material-symbols-outlined" style={{ fontSize: 40, color: 'var(--text-disabled)', display: 'block', marginBottom: 14 }}>
            sports_mma
          </span>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, margin: 0 }}>
            No fights yet. Upload a video to get started.
          </p>
        </div>
      )}

      {fights.length > 0 && (
        <div className="glass anim-fade-up anim-delay-2" style={{ overflow: 'hidden' }}>
          {!isMobile && (
            <div style={{ display: 'grid', gridTemplateColumns: columns, gap: 14, alignItems: 'center', padding: '11px 18px', borderBottom: '1px solid var(--border-glass)' }}>
              <span />
              {['Fight', 'Purpose', 'Status', 'Length', 'Video', 'Added'].map(h => <span key={h} className="label">{h}</span>)}
              <span />
            </div>
          )}

          {ordered.map(({ fight }, row) => {
            const viewable = isFightViewable(fight.state);
            const labelingReady = isLabelingReady(fight.state);
            const ready = viewable || labelingReady;
            const failed = fight.state === 'failed';
            const invalid = isInvalid(fight.state);
            const errored = failed || invalid;
            const progress = STATE_PROGRESS[fight.state] ?? 0;
            const stateLabel = labelingReady ? 'Ready to label' : STATE_LABELS[fight.state] ?? fight.state;
            // Viewers can't annotate: Player shows them the "being labelled" state instead.
            const target = labelingReady && can('labeller') ? `/fights/${fight.id}/annotate` : `/fights/${fight.id}`;
            const deleting = deletingId === fight.id;
            const length = fight.decoded_frames != null && fight.fps > 0 ? formatLength(fight.decoded_frames / fight.fps) : null;
            const video = `${fight.fps} fps · ${fight.width}×${fight.height}`;

            const icon = (
              <span className="material-symbols-outlined" style={{
                fontSize: 20,
                color: ready ? 'var(--text-secondary)' : errored ? 'var(--red-500)' : 'var(--text-muted)',
                animation: (!ready && !errored) ? 'spin 1.5s linear infinite' : undefined,
              }}>
                {labelingReady ? 'edit_note' : viewable ? 'play_circle' : errored ? 'error' : 'progress_activity'}
              </span>
            );
            const title = (
              <div style={{ minWidth: 0 }}>
                <p style={{
                  margin: 0, fontSize: 14, fontWeight: 600,
                  color: ready ? 'var(--text-primary)' : errored ? 'var(--red-500)' : 'var(--text-tertiary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {fightLabel(fight)}
                </p>
                {ready && needsRoundReview(fight) && (
                  <p style={{ margin: '3px 0 0', fontSize: 12, color: 'var(--warn)', display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span className="material-symbols-outlined" style={{ fontSize: 15 }}>rule</span>
                    Rounds unverified — check before labelling
                  </p>
                )}
                {invalid && (
                  <p style={{ margin: '3px 0 0', fontSize: 12, color: 'var(--red-500)', lineHeight: 1.5, whiteSpace: 'normal' }}>
                    {invalidReason(fight)}
                  </p>
                )}
              </div>
            );
            const status = (
              <div style={{ minWidth: 0 }}>
                <span style={{ ...cell, display: 'block', color: errored ? 'var(--red-500)' : ready ? 'var(--text-muted)' : 'var(--text-secondary)' }}>{stateLabel}</span>
                {!ready && !errored && (
                  <div style={{ height: 3, marginTop: 6, borderRadius: 2, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${progress}%`, borderRadius: 2, background: 'var(--text-primary)', transition: 'width 0.5s ease' }} />
                  </div>
                )}
              </div>
            );
            const action = errored && can('admin') ? (
              <button
                onClick={ev => { ev.stopPropagation(); setDeleteError(null); setPendingDelete(fight); }}
                disabled={deleting}
                title="Delete and re-upload"
                aria-label="Delete and re-upload"
                style={{
                  width: 30, height: 30, flexShrink: 0, display: 'grid', placeItems: 'center',
                  borderRadius: 6, border: '1px solid var(--f-red-dim)',
                  background: 'rgba(239,68,68,0.08)', color: 'var(--red-500)',
                  cursor: deleting ? 'not-allowed' : 'pointer', opacity: deleting ? 0.5 : 1, fontFamily: 'inherit',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                  {deleting ? 'progress_activity' : 'delete'}
                </span>
              </button>
            ) : ready ? (
              <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--text-disabled)', justifySelf: 'end' }}>chevron_right</span>
            ) : <span />;

            return (
              <div
                key={fight.id}
                className={`fight-card${ready ? ' is-ready' : ''}`}
                onClick={ready ? () => navigate(target) : undefined}
                style={{
                  display: 'grid',
                  gridTemplateColumns: isMobile ? '24px minmax(0, 1fr) 30px' : columns,
                  gap: isMobile ? 12 : 14,
                  alignItems: 'center',
                  padding: isMobile ? '13px 14px' : '13px 18px',
                  borderTop: row > 0 ? '1px solid var(--border-subtle)' : 'none',
                  cursor: ready ? 'pointer' : 'default',
                  opacity: ready || errored ? 1 : 0.7,
                }}
              >
                {icon}
                {isMobile ? (
                  <div style={{ minWidth: 0 }}>
                    {title}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, marginTop: 5 }}>
                      <FightPurposeBadge purpose={fight.purpose} size="sm" />
                      <span style={cell}>{ready ? [length, video].filter(Boolean).join(' · ') : stateLabel}</span>
                    </div>
                    {!ready && !errored && (
                      <div style={{ height: 3, marginTop: 7, borderRadius: 2, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${progress}%`, borderRadius: 2, background: 'var(--text-primary)', transition: 'width 0.5s ease' }} />
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    {title}
                    <div><FightPurposeBadge purpose={fight.purpose} size="sm" /></div>
                    {status}
                    <span style={mono}>{length ?? '—'}</span>
                    <span style={mono}>{video}</span>
                    <span style={cell}>{formatAdded(fight.created_at)}</span>
                  </>
                )}
                {action}
              </div>
            );
          })}
        </div>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete fight?"
        message={
          <>
            <strong style={{ color: 'var(--text-primary)' }}>
              {pendingDelete ? fightLabel(pendingDelete) : ''}
            </strong> will be permanently deleted — the source video file, all pipeline predictions,
            hand labels, rounds, and tracked fighter frames. This cannot be undone.
          </>
        }
        confirmLabel="Delete fight"
        confirmIcon="delete_forever"
        danger
        busy={deletingId !== null}
        error={deleteError}
        onCancel={() => setPendingDelete(null)}
        onConfirm={handleDelete}
      />
    </div>
  );
}
