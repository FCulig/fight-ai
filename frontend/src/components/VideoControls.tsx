import { useRef } from 'react';
import { useWindowWidth } from '../hooks/useWindowWidth';

interface VideoControlsProps {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
  onStepBackward: () => void;
  onStepForward: () => void;
}

export default function VideoControls({
  isPlaying, currentTime, duration,
  onTogglePlay, onSeek, onStepBackward, onStepForward,
}: VideoControlsProps) {
  const holdTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const holdIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const width = useWindowWidth();
  const isMobile = width < 640;

  const startHold = (fn: () => void) => {
    fn();
    holdTimeoutRef.current = setTimeout(() => {
      holdIntervalRef.current = setInterval(fn, 80);
    }, 300);
  };

  const stopHold = () => {
    if (holdTimeoutRef.current) { clearTimeout(holdTimeoutRef.current); holdTimeoutRef.current = null; }
    if (holdIntervalRef.current) { clearInterval(holdIntervalRef.current); holdIntervalRef.current = null; }
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div style={{
      background: 'rgba(255,255,255,0.04)',
      backdropFilter: 'blur(20px) saturate(160%)',
      WebkitBackdropFilter: 'blur(20px) saturate(160%)',
      border: '1px solid rgba(255,255,255,0.07)',
      borderRadius: 14,
      padding: isMobile ? '12px' : '12px 16px',
    }}>
      {/* Seek bar */}
      <div style={{ marginBottom: 12 }}>
        <input
          type="range"
          min={0}
          max={duration || 1}
          step={0.02}
          value={currentTime}
          onChange={e => onSeek(Number(e.target.value))}
          style={{
            width: '100%',
            height: isMobile ? 5 : 3,
            appearance: 'none',
            background: `linear-gradient(to right, #00daf3 ${progress}%, rgba(255,255,255,0.1) ${progress}%)`,
            borderRadius: 3,
            outline: 'none',
            cursor: 'pointer',
          }}
        />
      </div>

      {/* Controls row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 8 : 8 }}>
        <button
          className="btn-glass"
          onMouseDown={() => startHold(onStepBackward)}
          onMouseUp={stopHold}
          onMouseLeave={stopHold}
          style={{
            borderRadius: 8,
            padding: isMobile ? '10px 12px' : '6px 8px',
            minWidth: isMobile ? 44 : 'auto',
            minHeight: isMobile ? 44 : 'auto',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: isMobile ? 20 : 18 }}>skip_previous</span>
        </button>

        <button
          className="btn-primary"
          onClick={onTogglePlay}
          style={{
            background: 'linear-gradient(135deg, #00daf3 0%, #0099b0 100%)',
            borderRadius: 10,
            color: '#001f24',
            fontWeight: 700,
            fontSize: isMobile ? 13 : 13,
            padding: isMobile ? '10px 20px' : '7px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            boxShadow: '0 0 16px rgba(0,218,243,0.25)',
            minHeight: isMobile ? 44 : 'auto',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: isMobile ? 20 : 18 }}>
            {isPlaying ? 'pause' : 'play_arrow'}
          </span>
          {isPlaying ? 'Pause' : 'Play'}
        </button>

        <button
          className="btn-glass"
          onMouseDown={() => startHold(onStepForward)}
          onMouseUp={stopHold}
          onMouseLeave={stopHold}
          style={{
            borderRadius: 8,
            padding: isMobile ? '10px 12px' : '6px 8px',
            minWidth: isMobile ? 44 : 'auto',
            minHeight: isMobile ? 44 : 'auto',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: isMobile ? 20 : 18 }}>skip_next</span>
        </button>

        <span style={{
          fontSize: isMobile ? 13 : 13,
          color: '#e2e8f0',
          fontVariantNumeric: 'tabular-nums',
          fontWeight: 600,
          marginLeft: 4,
        }}>
          {formatTime(currentTime)}
        </span>
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)' }}>/</span>
        <span style={{ fontSize: isMobile ? 12 : 13, color: '#475569', fontVariantNumeric: 'tabular-nums' }}>
          {formatTime(duration)}
        </span>
      </div>
    </div>
  );
}
