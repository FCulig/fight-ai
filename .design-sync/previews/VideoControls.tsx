import { useState } from 'react';
import { VideoControls } from 'fightlytics';

function Demo({ playing, t }: { playing: boolean; t: number }) {
  const [time, setTime] = useState(t);
  const [isPlaying, setPlaying] = useState(playing);
  return (
    <div style={{ width: '100%' }}>
      <VideoControls isPlaying={isPlaying} currentTime={time} duration={677} onTogglePlay={() => setPlaying(p => !p)}
        onSeek={setTime} onStepBackward={() => setTime(x => Math.max(0, x - 1 / 30))} onStepForward={() => setTime(x => x + 1 / 30)} />
    </div>
  );
}

export const Paused = () => <Demo playing={false} t={0} />;
export const PlayingMidFight = () => <Demo playing t={241} />;
