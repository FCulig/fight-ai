import { useRef, useState } from 'react';
import { useEvents } from '../hooks/useEvents';
import { useWindowWidth } from '../hooks/useWindowWidth';
import VideoPlayer from '../components/VideoPlayer';
import VideoControls from '../components/VideoControls';
import FrameInfo from '../components/FrameInfo';
import EventFeed from '../components/EventFeed';

const VIDEO_PATH = '/fight.mp4';
const FPS = 50;
const ROUND_DURATION = 300;

function isStrikeEvent(desc: string) {
  return /punch|kick|jab|cross|hook|uppercut|elbow|knee|strike|hit|landed|blocked/i.test(desc);
}

function isGroundEvent(desc: string) {
  return /takedown|ground|grapple|clinch|mount|guard|submission|sprawl/i.test(desc);
}

export default function Player() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const { events, loading, error } = useEvents();
  const width = useWindowWidth();
  const isMobile = width < 768;

  const currentFrame = Math.floor(currentTime * FPS);
  const currentMs = Math.floor(currentTime * 1000);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    isPlaying ? video.pause() : video.play();
    setIsPlaying(!isPlaying);
  };

  const stepFrame = (delta: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    setIsPlaying(false);
    const newTime = Math.min(Math.max(video.currentTime + delta / FPS, 0), video.duration);
    video.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const handleSeek = (time: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = time;
    setCurrentTime(time);
  };

  const handleExportFrame = () => {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d')?.drawImage(video, 0, 0);
    const link = document.createElement('a');
    link.download = `frame-${currentFrame}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  };

  const visibleEvents = events.filter(e => e.frame <= currentFrame);
  const strikeEvents = visibleEvents.filter(e => isStrikeEvent(e.description));
  const groundEvents = visibleEvents.filter(e => isGroundEvent(e.description));
  const totalStrikes = events.filter(e => isStrikeEvent(e.description)).length;
  const grappleSeconds = groundEvents.length * 4;
  const currentRound = Math.floor(currentTime / ROUND_DURATION) + 1;

  const fmtGrapple = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
  };

  const glassCard: React.CSSProperties = {
    background: 'rgba(255,255,255,0.04)',
    backdropFilter: 'blur(20px) saturate(160%)',
    WebkitBackdropFilter: 'blur(20px) saturate(160%)',
    border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: 16,
    padding: isMobile ? '14px 16px' : '18px 20px',
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: isMobile ? 'column' : 'row',
      gap: isMobile ? 12 : 16,
      padding: isMobile ? '12px' : '20px 24px',
      maxWidth: 1440,
      width: '100%',
      margin: '0 auto',
      alignItems: 'flex-start',
    }}>
      {/* ── Video column ───────────────────────────── */}
      <div
        className="anim-fade-up anim-delay-1"
        style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        <VideoPlayer
          ref={videoRef}
          src={VIDEO_PATH}
          isPlaying={isPlaying}
          onTimeUpdate={() => { const v = videoRef.current; if (v) setCurrentTime(v.currentTime); }}
          onLoadedMetadata={() => { const v = videoRef.current; if (v) setDuration(v.duration); }}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onTogglePlay={togglePlay}
          onStepForward={() => stepFrame(1)}
          onStepBackward={() => stepFrame(-1)}
        />
        <VideoControls
          isPlaying={isPlaying}
          currentTime={currentTime}
          duration={duration}
          onTogglePlay={togglePlay}
          onSeek={handleSeek}
          onStepBackward={() => stepFrame(-1)}
          onStepForward={() => stepFrame(1)}
        />
        <FrameInfo currentFrame={currentFrame} currentMs={currentMs} fps={FPS} />
      </div>

      {/* ── Sidebar ─────────────────────────────────── */}
      <div style={{
        width: isMobile ? '100%' : 300,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}>
        {/* Stats card */}
        <div className="anim-fade-up anim-delay-2" style={glassCard}>
          <p style={{
            fontSize: 10,
            fontWeight: 700,
            color: 'rgba(255,255,255,0.28)',
            textTransform: 'uppercase',
            letterSpacing: '0.12em',
            margin: '0 0 2px',
          }}>
            Active Round
          </p>
          <p
            className="font-display"
            style={{
              fontSize: isMobile ? 52 : 64,
              margin: '0 0 16px',
              lineHeight: 1,
              background: 'linear-gradient(160deg, #f1f5f9 40%, rgba(255,255,255,0.3))',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Round {currentRound}
          </p>

          {/* Stat tiles */}
          <div style={{ display: 'flex', gap: 10 }}>
            <div style={{
              flex: 1,
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.05)',
              borderRadius: 12,
              padding: '12px 14px',
            }}>
              <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.28)', margin: '0 0 4px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Sig. Strikes
              </p>
              <p style={{ margin: 0, fontVariantNumeric: 'tabular-nums', lineHeight: 1, display: 'flex', alignItems: 'baseline', gap: 2 }}>
                <span
                  className="font-display"
                  style={{
                    fontSize: 36,
                    background: 'linear-gradient(135deg, #00daf3, #0099b0)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    backgroundClip: 'text',
                  }}
                >
                  {strikeEvents.length}
                </span>
                <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.18)', fontWeight: 600 }}>
                  /{totalStrikes}
                </span>
              </p>
            </div>

            <div style={{
              flex: 1,
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.05)',
              borderRadius: 12,
              padding: '12px 14px',
            }}>
              <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.28)', margin: '0 0 4px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Grapple
              </p>
              <p
                className="font-display"
                style={{
                  margin: 0,
                  fontSize: 36,
                  fontVariantNumeric: 'tabular-nums',
                  lineHeight: 1,
                  background: 'linear-gradient(135deg, #ff7043, #e64a19)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                {fmtGrapple(grappleSeconds)}
              </p>
            </div>
          </div>

          <button
            onClick={handleExportFrame}
            className="btn-glass"
            style={{
              marginTop: 12,
              width: '100%',
              padding: isMobile ? '12px 14px' : '9px 14px',
              borderRadius: 9,
              fontSize: 12,
              fontWeight: 600,
              gap: 6,
              minHeight: isMobile ? 44 : 'auto',
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>download</span>
            Export Frame
          </button>
        </div>

        {/* Event feed */}
        <div className="anim-fade-up anim-delay-3">
          <EventFeed
            events={events}
            currentFrame={currentFrame}
            loading={loading}
            error={error}
          />
        </div>
      </div>
    </div>
  );
}
