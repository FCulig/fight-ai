import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useFights } from '../hooks/useFights';
import { useFightStream } from '../hooks/useFightStream';
import { useWindowWidth } from '../hooks/useWindowWidth';
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

export default function FightList() {
  const navigate = useNavigate();
  const location = useLocation();
  const { fights, setFights, loading, error, refetch } = useFights();
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

  return (
    <div style={{
      maxWidth: 900,
      width: '100%',
      margin: '0 auto',
      padding: isMobile ? '20px 16px' : '40px 24px',
    }}>
      <div className="anim-fade-up anim-delay-1" style={{ marginBottom: 28 }}>
        <span className="eyebrow">Analysis</span>
        <h1 className="font-display" style={{
          fontSize: isMobile ? 30 : 'clamp(32px, 4vw, 48px)',
          lineHeight: 1,
          margin: '10px 0 0',
          color: 'var(--text-primary)',
        }}>
          Fights.
        </h1>
        <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-muted)', margin: '10px 0 0' }}>
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

      <div style={{
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: 14,
      }}>
        {fights.map((fight, i) => {
          const viewable = isFightViewable(fight.state);
          const labelingReady = isLabelingReady(fight.state);
          const ready = viewable || labelingReady;
          const failed = fight.state === 'failed';
          const invalid = isInvalid(fight.state);
          const errored = failed || invalid;
          const progress = STATE_PROGRESS[fight.state] ?? 0;
          const stateLabel = STATE_LABELS[fight.state] ?? fight.state;
          const target = labelingReady ? `/fights/${fight.id}/annotate` : `/fights/${fight.id}`;
          const deleting = deletingId === fight.id;

          return (
            <div
              key={fight.id}
              className={`glass fight-card anim-fade-up anim-delay-${Math.min(i + 2, 5)}${ready ? ' is-ready' : ''}`}
              onClick={ready ? () => navigate(target) : undefined}
              style={{
                padding: '18px 20px',
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                cursor: ready ? 'pointer' : 'default',
                textAlign: 'left',
                width: '100%',
                opacity: ready || errored ? 1 : 0.6,
              }}
            >
              <div style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: ready ? 'color-mix(in srgb, var(--accent) 8%, transparent)' : errored ? 'var(--f-red-dim)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${ready ? 'color-mix(in srgb, var(--accent) 15%, transparent)' : errored ? 'color-mix(in srgb, var(--red-500) 15%, transparent)' : 'var(--border-glass)'}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                <span className="material-symbols-outlined" style={{
                  fontSize: 22,
                  color: ready ? 'var(--accent)' : errored ? 'var(--red-500)' : 'var(--text-muted)',
                  animation: (!ready && !errored) ? 'spin 1.5s linear infinite' : undefined,
                }}>
                  {labelingReady ? 'edit_note' : viewable ? 'play_circle' : errored ? 'error' : 'progress_activity'}
                </span>
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{
                  margin: '0 0 3px',
                  fontSize: 14,
                  fontWeight: 700,
                  color: ready ? 'var(--text-primary)' : errored ? 'var(--red-500)' : 'var(--text-tertiary)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {fightLabel(fight)}
                </p>
                {ready ? (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
                      <FightPurposeBadge purpose={fight.purpose} size="sm" />
                      <p style={{
                        margin: 0,
                        fontSize: 12,
                        color: 'var(--text-muted)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}>
                        {labelingReady ? 'Ready to label · ' : ''}{fight.fps} fps · {fight.width}×{fight.height}
                      </p>
                    </div>
                    {needsRoundReview(fight) && (
                      <p style={{
                        margin: '4px 0 0',
                        fontSize: 12,
                        color: '#f59e0b',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 5,
                      }}>
                        <span className="material-symbols-outlined" style={{ fontSize: 15 }}>
                          rule
                        </span>
                        Rounds unverified — check before labelling
                      </p>
                    )}
                  </>
                ) : invalid ? (
                  <>
                    <div style={{ marginBottom: 4 }}>
                      <FightPurposeBadge purpose={fight.purpose} size="sm" />
                    </div>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--red-500)', lineHeight: 1.5 }}>
                      {invalidReason(fight)}
                    </p>
                  </>
                ) : (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0, margin: '0 0 5px' }}>
                      <FightPurposeBadge purpose={fight.purpose} size="sm" />
                      <p style={{ margin: 0, fontSize: 12, color: failed ? 'var(--red-500)' : 'var(--text-tertiary)' }}>
                        {stateLabel}
                      </p>
                    </div>
                    {!failed && (
                      <div style={{
                        height: 4,
                        borderRadius: 2,
                        background: 'rgba(255,255,255,0.08)',
                        overflow: 'hidden',
                      }}>
                        <div style={{
                          height: '100%',
                          width: `${progress}%`,
                          borderRadius: 2,
                          background: 'linear-gradient(90deg, var(--accent-deep), var(--accent))',
                          transition: 'width 0.5s ease',
                        }} />
                      </div>
                    )}
                  </div>
                )}
              </div>

              {ready && (
                <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--text-disabled)', flexShrink: 0 }}>
                  chevron_right
                </span>
              )}

              {errored && (
                <button
                  onClick={ev => { ev.stopPropagation(); setDeleteError(null); setPendingDelete(fight); }}
                  disabled={deleting}
                  title="Delete and re-upload"
                  style={{
                    flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 6,
                    padding: '7px 12px', borderRadius: 999, border: '1px solid var(--f-red-dim)',
                    background: 'rgba(239,68,68,0.08)', color: 'var(--red-500)', fontSize: 12, fontWeight: 700,
                    cursor: deleting ? 'not-allowed' : 'pointer', opacity: deleting ? 0.5 : 1, fontFamily: 'inherit',
                  }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 15 }}>
                    {deleting ? 'progress_activity' : 'delete'}
                  </span>
                  Delete
                </button>
              )}
            </div>
          );
        })}
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="DELETE FIGHT?"
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
