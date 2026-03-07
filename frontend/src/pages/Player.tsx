import { useRef, useState } from "react";
import { useEvents } from "../hooks/useEvents";
import VideoPlayer from "../components/VideoPlayer";
import VideoControls from "../components/VideoControls";
import FrameInfo from "../components/FrameInfo";
import EventFeed from "../components/EventFeed";

const VIDEO_PATH = "./fight.mp4";
const FPS = 50;

export default function Player() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const { events, loading, error } = useEvents();

  const currentFrame = Math.floor(currentTime * FPS);
  const currentMs = Math.floor(currentTime * 1000);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    isPlaying ? video.pause() : video.play();
    setIsPlaying(!isPlaying);
  };

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (!video) return;
    setCurrentTime(video.currentTime);
  };

  const handleLoadedMetadata = () => {
    const video = videoRef.current;
    if (!video) return;
    setDuration(video.duration);
  };

  const handleSeek = (time: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = time;
    setCurrentTime(time);
  };

  return (
    <div style={{ padding: "40px 20px" }}>
      <div style={{ display: "flex", gap: "20px", maxWidth: "1400px", margin: "0 auto" }}>
        {/* Left side - Video and controls */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <VideoPlayer
            ref={videoRef}
            src={VIDEO_PATH}
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
          />

          <VideoControls
            isPlaying={isPlaying}
            currentTime={currentTime}
            duration={duration}
            onTogglePlay={togglePlay}
            onSeek={handleSeek}
          />

          <FrameInfo currentFrame={currentFrame} currentMs={currentMs} fps={FPS} />
        </div>

        {/* Right side - Event feed */}
        <div style={{ width: "320px", flexShrink: 0 }}>
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