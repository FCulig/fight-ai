import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useFights } from '../hooks/useFights';
import { useFightStream } from '../hooks/useFightStream';
import { useWindowWidth } from '../hooks/useWindowWidth';

import type { Fight } from '../types/Fight';
import { STATE_PROGRESS, STATE_LABELS } from '../types/Fight';

function fightLabel(fight: Fight): string {
  if (fight.red_fighter_name && fight.blue_fighter_name) {
    return `${fight.red_fighter_name} vs ${fight.blue_fighter_name}`;
  }
  return fight.video_path.split('/').pop()?.replace(/\.[^/.]+$/, '') ?? fight.video_path;
}

export default function FightList() {
  const navigate = useNavigate();
  const location = useLocation();
  const { fights, setFights, loading, error, refetch } = useFights();
  const width = useWindowWidth();
  const isMobile = width < 640;

  const uploadedAt = (location.state as { uploaded?: number } | null)?.uploaded;
  useEffect(() => {
    if (uploadedAt) refetch();
  }, [uploadedAt, refetch]);

  const hasInProgress = fights.some(f => f.state !== 'completed' && f.state !== 'failed');
  useFightStream(fights, setFights, hasInProgress);

  const glassCard: React.CSSProperties = {
    background: 'rgba(255,255,255,0.04)',
    backdropFilter: 'blur(20px) saturate(160%)',
    WebkitBackdropFilter: 'blur(20px) saturate(160%)',
    border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: 16,
  };

  return (
    <div style={{
      maxWidth: 900,
      width: '100%',
      margin: '0 auto',
      padding: isMobile ? '20px 16px' : '40px 24px',
    }}>
      <div className="anim-fade-up anim-delay-1" style={{ marginBottom: 28 }}>
        <h1 style={{
          fontSize: isMobile ? 22 : 28,
          fontWeight: 800,
          margin: '0 0 6px',
          background: 'linear-gradient(90deg, #f1f5f9, rgba(255,255,255,0.5))',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          letterSpacing: '-0.02em',
        }}>
          Fights
        </h1>
        <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.35)', margin: 0 }}>
          Select a fight to open the analysis player.
        </p>
      </div>

      {loading && (
        <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: 14 }}>Loading…</p>
      )}

      {error && (
        <p style={{ color: '#ef4444', fontSize: 14 }}>{error}</p>
      )}

      {!loading && !error && fights.length === 0 && (
        <div style={{ ...glassCard, padding: isMobile ? '36px 24px' : '48px 40px', textAlign: 'center' }}>
          <span className="material-symbols-outlined" style={{ fontSize: 40, color: 'rgba(255,255,255,0.2)', display: 'block', marginBottom: 14 }}>
            sports_mma
          </span>
          <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: 14, margin: 0 }}>
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
          const completed = fight.state === 'completed';
          const failed = fight.state === 'failed';
          const progress = STATE_PROGRESS[fight.state] ?? 0;
          const stateLabel = STATE_LABELS[fight.state] ?? fight.state;

          return (
            <button
              key={fight.id}
              className={`anim-fade-up anim-delay-${Math.min(i + 2, 5)}`}
              onClick={completed ? () => navigate(`/fights/${fight.id}`) : undefined}
              disabled={!completed}
              style={{
                ...glassCard,
                padding: '18px 20px',
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                cursor: completed ? 'pointer' : 'default',
                textAlign: 'left',
                width: '100%',
                transition: 'border-color 0.15s, background 0.15s',
                opacity: completed ? 1 : 0.6,
              }}
              onMouseEnter={e => {
                if (!completed) return;
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(0,218,243,0.35)';
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(0,218,243,0.06)';
              }}
              onMouseLeave={e => {
                if (!completed) return;
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.07)';
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)';
              }}
            >
              <div style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: completed ? 'rgba(0,218,243,0.08)' : failed ? 'rgba(239,68,68,0.08)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${completed ? 'rgba(0,218,243,0.15)' : failed ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.07)'}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                <span className="material-symbols-outlined" style={{
                  fontSize: 22,
                  color: completed ? '#00daf3' : failed ? '#ef4444' : '#64748b',
                  animation: (!completed && !failed) ? 'spin 1.5s linear infinite' : undefined,
                }}>
                  {completed ? 'play_circle' : failed ? 'error' : 'progress_activity'}
                </span>
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{
                  margin: '0 0 3px',
                  fontSize: 14,
                  fontWeight: 700,
                  color: completed ? '#f1f5f9' : failed ? '#ef4444' : '#94a3b8',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {fightLabel(fight)}
                </p>
                {completed ? (
                  <p style={{ margin: 0, fontSize: 12, color: 'rgba(255,255,255,0.35)' }}>
                    {fight.fps} fps · {fight.width}×{fight.height}
                  </p>
                ) : (
                  <div>
                    <p style={{ margin: '0 0 5px', fontSize: 12, color: failed ? '#ef4444' : 'rgba(255,255,255,0.5)' }}>
                      {stateLabel}
                    </p>
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
                          background: 'linear-gradient(90deg, #00daf3, #06b6d4)',
                          transition: 'width 0.5s ease',
                        }} />
                      </div>
                    )}
                  </div>
                )}
              </div>

              {completed && (
                <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'rgba(255,255,255,0.2)', flexShrink: 0 }}>
                  chevron_right
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
