import { useRef, useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useEvents } from '../hooks/useEvents';
import { useFights } from '../hooks/useFights';
import { useFighterFrames } from '../hooks/useFighterFrames';
import { useRounds } from '../hooks/useRounds';
import { useWindowWidth } from '../hooks/useWindowWidth';
import VideoPlayer from '../components/VideoPlayer';
import VideoControls from '../components/VideoControls';
import FrameInfo from '../components/FrameInfo';
import FighterOverlay, { type FighterOverlayHandle } from '../components/FighterOverlay';
import LiveFeed from '../components/player/LiveFeed';
import FightStatistics from '../components/player/FightStatistics';
import Momentum from '../components/player/Momentum';
import MatchupCard from '../components/player/MatchupCard';

export default function Player() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const fightId = id ? Number(id) : null;

  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<FighterOverlayHandle>(null);
  const rafRef = useRef<number | null>(null);
  const fpsRef = useRef<number>(30);
  const lastFrameRef = useRef<number>(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [showBoxes, setShowBoxes] = useState(true);
  const [showSkeletons, setShowSkeletons] = useState(false);

  const { fights } = useFights();
  const selectedFight = fights.find(f => f.id === fightId) ?? null;
  const { events, loading: eventsLoading } = useEvents(fightId);
  const { frameMap } = useFighterFrames(fightId);
  const { rounds } = useRounds(fightId);
  const width = useWindowWidth();
  const narrow = width < 1100;

  const fps = selectedFight?.fps ?? 30;
  fpsRef.current = fps;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (!isPlaying) {
      if (rafRef.current !== null) {
        video.cancelVideoFrameCallback(rafRef.current);
        rafRef.current = null;
      }
      return;
    }
    const tick = (_now: DOMHighResTimeStamp, metadata: VideoFrameCallbackMetadata) => {
      const frame = Math.floor(metadata.mediaTime * fpsRef.current) + 1;
      overlayRef.current?.draw(frame);
      if (frame !== lastFrameRef.current) {
        lastFrameRef.current = frame;
        setCurrentTime(metadata.mediaTime);
      }
      rafRef.current = video.requestVideoFrameCallback(tick);
    };
    rafRef.current = video.requestVideoFrameCallback(tick);
    return () => {
      if (rafRef.current !== null) {
        video.cancelVideoFrameCallback(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [isPlaying]);

  const currentFrame = Math.floor(currentTime * fps) + 1;
  const currentMs = Math.floor(currentTime * 1000);

  const videoSrc = selectedFight ? `/fights/${selectedFight.id}/video` : undefined;

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
    const newTime = Math.min(Math.max(video.currentTime + delta / fps, 0), video.duration);
    video.currentTime = newTime;
    setCurrentTime(newTime);
    overlayRef.current?.draw(Math.floor(newTime * fpsRef.current) + 1);
  };

  const handleSeek = (time: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = time;
    setCurrentTime(time);
    overlayRef.current?.draw(Math.floor(time * fpsRef.current) + 1);
  };

  const currentRound =
    rounds.find(r => currentFrame >= r.start_frame && currentFrame <= r.end_frame)
      ?.round_number ?? '-';

  // Round 1 end in seconds for pace chart playhead
  const r1Round = rounds.find(r => r.round_number === 1);
  const r1EndSeconds = r1Round ? r1Round.end_frame / fps : 0;

  return (
    <div style={{
      position: 'relative',
      zIndex: 1,
      maxWidth: 1500,
      margin: '0 auto',
      padding: narrow ? '16px 14px 48px' : '22px 30px 70px',
    }}>
      {/* Back nav */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <button
          onClick={() => navigate('/')}
          className="btn-glass"
          style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', fontSize: 12, fontWeight: 600, borderRadius: 8 }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_back</span>
          All Fights
        </button>
        {selectedFight && (
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {selectedFight.video_path.split('/').pop()?.replace(/\.[^/.]+$/, '')}
          </span>
        )}
      </div>

      {/* TOP GRID: video | live feed */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: narrow ? '1fr' : '1fr 410px',
        gap: 16,
        alignItems: 'stretch',
      }}>
        {/* Video column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Video stage */}
          <VideoPlayer
            ref={videoRef}
            src={videoSrc}
            isPlaying={isPlaying}
            onTimeUpdate={() => { const v = videoRef.current; if (v) setCurrentTime(v.currentTime); }}
            onLoadedMetadata={() => { const v = videoRef.current; if (v) setDuration(v.duration); }}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onTogglePlay={togglePlay}
            onStepForward={() => stepFrame(1)}
            onStepBackward={() => stepFrame(-1)}
          >
            {selectedFight && (
              <FighterOverlay
                ref={overlayRef}
                frameMap={frameMap}
                fightWidth={selectedFight.width}
                fightHeight={selectedFight.height}
                showBoxes={showBoxes}
                showSkeletons={showSkeletons}
              />
            )}
            {/* Round chip */}
            <div style={{ position: 'absolute', top: 14, left: 16, display: 'flex', gap: 8, alignItems: 'center', pointerEvents: 'none' }}>
              <span style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(8px)', color: '#fff', fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 6, letterSpacing: '0.06em' }}>
                {currentRound === '-' ? 'LOADING…' : `ROUND ${currentRound}`}
              </span>
            </div>
          </VideoPlayer>

          <VideoControls
            isPlaying={isPlaying}
            currentTime={currentTime}
            duration={duration}
            onTogglePlay={togglePlay}
            onSeek={handleSeek}
            onStepBackward={() => stepFrame(-1)}
            onStepForward={() => stepFrame(1)}
          />

          <FrameInfo currentFrame={currentFrame} currentMs={currentMs} fps={fps} />

          {/* Overlay controls */}
          <div style={{ display: 'flex', gap: 16, padding: '6px 2px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>
              <input
                type="checkbox"
                checked={showBoxes}
                onChange={e => setShowBoxes(e.target.checked)}
                style={{ accentColor: 'var(--accent)', width: 14, height: 14, cursor: 'pointer' }}
              />
              Fighter Boxes
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>
              <input
                type="checkbox"
                checked={showSkeletons}
                onChange={e => setShowSkeletons(e.target.checked)}
                style={{ accentColor: 'var(--accent)', width: 14, height: 14, cursor: 'pointer' }}
              />
              Skeletons
            </label>
          </div>
        </div>

        {/* Live feed column */}
        {narrow ? (
          <div style={{ height: 420 }}>
            <LiveFeed
              events={events}
              currentFrame={currentFrame}
              fps={fps}
              onSeek={handleSeek}
            />
          </div>
        ) : (
          <div style={{ position: 'relative' }}>
            <div style={{ position: 'absolute', inset: 0 }}>
              <LiveFeed
                events={events}
                currentFrame={currentFrame}
                fps={fps}
                onSeek={handleSeek}
              />
            </div>
          </div>
        )}
      </div>

      {/* FIGHT STATISTICS */}
      {!eventsLoading && <FightStatistics />}

      {/* MOMENTUM */}
      <Momentum time={currentTime} duration={duration} r1EndSeconds={r1EndSeconds} />

      {/* MATCHUP */}
      <MatchupCard />
    </div>
  );
}
