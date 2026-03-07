interface VideoControlsProps {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
}

export default function VideoControls({
  isPlaying,
  currentTime,
  duration,
  onTogglePlay,
  onSeek,
}: VideoControlsProps) {
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
      <button onClick={onTogglePlay} style={{ padding: '6px 16px' }}>
        {isPlaying ? 'Pause' : 'Play'}
      </button>

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
