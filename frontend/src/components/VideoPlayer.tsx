import { forwardRef, useState, useRef, useCallback } from 'react';

interface VideoPlayerProps {
  src: string;
  isPlaying: boolean;
  onTimeUpdate: () => void;
  onLoadedMetadata: () => void;
  onPlay: () => void;
  onPause: () => void;
  onTogglePlay: () => void;
  onStepForward: () => void;
  onStepBackward: () => void;
  children?: React.ReactNode;
}

const VideoPlayer = forwardRef<HTMLVideoElement, VideoPlayerProps>((
  { src, isPlaying, onTimeUpdate, onLoadedMetadata, onPlay, onPause, onTogglePlay, onStepForward, onStepBackward, children },
  ref
) => {
  const holdTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const holdIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isHoldingRef = useRef(false);

  const [ppOverlay, setPpOverlay] = useState<{ icon: string; key: number } | null>(null);
  const [seekDir, setSeekDir] = useState<'left' | 'right' | null>(null);
  const [seekFading, setSeekFading] = useState(false);

  const stopHold = useCallback(() => {
    if (holdTimeoutRef.current) {
      clearTimeout(holdTimeoutRef.current);
      holdTimeoutRef.current = null;
    }
    if (holdIntervalRef.current) {
      clearInterval(holdIntervalRef.current);
      holdIntervalRef.current = null;
    }
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const isRight = (e.clientX - rect.left) > rect.width / 2;
    const stepFn = isRight ? onStepForward : onStepBackward;

    holdTimeoutRef.current = setTimeout(() => {
      isHoldingRef.current = true;
      setSeekDir(isRight ? 'right' : 'left');
      setSeekFading(false);
      stepFn();
      holdIntervalRef.current = setInterval(stepFn, 80);
    }, 250);
  }, [onStepForward, onStepBackward]);

  const handleMouseUp = useCallback(() => {
    if (isHoldingRef.current) {
      stopHold();
      setSeekFading(true);
      isHoldingRef.current = false;
    } else {
      stopHold();
      setPpOverlay(prev => ({
        icon: isPlaying ? 'pause' : 'play_arrow',
        key: (prev?.key ?? 0) + 1,
      }));
      onTogglePlay();
    }
  }, [isPlaying, onTogglePlay, stopHold]);

  const handleMouseLeave = useCallback(() => {
    if (isHoldingRef.current) {
      stopHold();
      setSeekFading(true);
      isHoldingRef.current = false;
    } else {
      stopHold();
    }
  }, [stopHold]);

  const overlayBase: React.CSSProperties = {
    position: 'absolute',
    top: '50%',
    fontSize: 64,
    color: '#fff',
    pointerEvents: 'none',
    background: 'rgba(0,0,0,0.35)',
    borderRadius: '50%',
    padding: 14,
    lineHeight: 1,
  };

  return (
    <div
      style={{ position: 'relative', lineHeight: 0, cursor: 'pointer', borderRadius: 8, overflow: 'hidden' }}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
    >
      <video
        ref={ref}
        src={src}
        onTimeUpdate={onTimeUpdate}
        onLoadedMetadata={onLoadedMetadata}
        onPlay={onPlay}
        onPause={onPause}
        style={{ width: '100%', display: 'block', background: '#000' }}
      />

      {/* Play/pause overlay */}
      {ppOverlay && (
        <span
          key={ppOverlay.key}
          className="material-symbols-outlined"
          onAnimationEnd={() => setPpOverlay(null)}
          style={{
            ...overlayBase,
            left: '50%',
            fontSize: 72,
            animation: 'video-feedback 0.5s ease-out forwards',
          }}
        >
          {ppOverlay.icon}
        </span>
      )}

      {/* Seek overlay */}
      {seekDir && (
        <span
          className="material-symbols-outlined"
          onAnimationEnd={() => {
            if (seekFading) {
              setSeekDir(null);
              setSeekFading(false);
            }
          }}
          style={{
            ...overlayBase,
            left: seekDir === 'left' ? '25%' : '75%',
            animation: seekFading
              ? 'seek-fade 0.3s ease-out forwards'
              : 'seek-pulse 0.6s ease-in-out infinite',
          }}
        >
          {seekDir === 'left' ? 'fast_rewind' : 'fast_forward'}
        </span>
      )}

      {children}
    </div>
  );
});

VideoPlayer.displayName = 'VideoPlayer';

export default VideoPlayer;
