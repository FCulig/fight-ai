import { useRef } from 'react';

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
  isPlaying,
  currentTime,
  duration,
  onTogglePlay,
  onSeek,
  onStepBackward,
  onStepForward,
}: VideoControlsProps) {
  const holdTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const holdIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startHold = (fn: () => void) => {
    fn();
    holdTimeoutRef.current = setTimeout(() => {
      holdIntervalRef.current = setInterval(fn, 80);
    }, 400);
  };

  const stopHold = () => {
    if (holdTimeoutRef.current !== null) {
      clearTimeout(holdTimeoutRef.current);
      holdTimeoutRef.current = null;
    }
    if (holdIntervalRef.current !== null) {
      clearInterval(holdIntervalRef.current);
      holdIntervalRef.current = null;
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    onSeek(Number(e.target.value));
  };

  return (
    <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 12 }}>
      <button
        onMouseDown={() => startHold(onStepBackward)}
        onMouseUp={stopHold}
        onMouseLeave={stopHold}
        style={{ padding: '6px 10px' }}
      >{'<'}</button>
      <button onClick={onTogglePlay} style={{ padding: '6px 16px' }}>
        {isPlaying ? 'Pause' : 'Play'}
      </button>
      <button
        onMouseDown={() => startHold(onStepForward)}
        onMouseUp={stopHold}
        onMouseLeave={stopHold}
        style={{ padding: '6px 10px' }}
      >{'>'}</button>

      <span style={{ fontSize: 13 }}>{formatTime(currentTime)}</span>

      <input
        type="range"
        min={0}
        max={duration}
        step={0.1}
        value={currentTime}
        onChange={handleSeek}
        style={{ flex: 1 }}
      />

      <span style={{ fontSize: 13 }}>{formatTime(duration)}</span>
    </div>
  );
}
