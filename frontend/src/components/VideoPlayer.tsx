import { forwardRef } from 'react';

interface VideoPlayerProps {
  src: string;
  onTimeUpdate: () => void;
  onLoadedMetadata: () => void;
  onPlay: () => void;
  onPause: () => void;
}

const VideoPlayer = forwardRef<HTMLVideoElement, VideoPlayerProps>((
  { src, onTimeUpdate, onLoadedMetadata, onPlay, onPause },
  ref
) => {
  return (
    <video
      ref={ref}
      src={src}
      type="video/mp4"
      onTimeUpdate={onTimeUpdate}
      onLoadedMetadata={onLoadedMetadata}
      onPlay={onPlay}
      onPause={onPause}
      style={{ width: '100%', borderRadius: 8, background: '#000' }}
    />
  );
});

VideoPlayer.displayName = 'VideoPlayer';

export default VideoPlayer;
