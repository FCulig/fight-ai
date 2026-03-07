// src/pages/Player.tsx
import { useRef, useState } from "react";

const VIDEO_PATH = "./fight.mp4";
const FPS = 50;

export default function Player() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

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

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = Number(e.target.value);
    setCurrentTime(Number(e.target.value));
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div style={{ maxWidth: 900, margin: "40px auto", padding: "0 20px" }}>
      <video
        ref={videoRef}
        src={VIDEO_PATH}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        style={{ width: "100%", borderRadius: 8, background: "#000" }}
      />

      {/* Controls */}
      <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 12 }}>
        <button onClick={togglePlay} style={{ padding: "6px 16px" }}>
          {isPlaying ? "Pause" : "Play"}
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

      {/* Frame info */}
      <div style={{ 
        marginTop: 8, 
        display: "flex", 
        gap: 20, 
        fontSize: 12, 
        color: "#888",
        fontFamily: "monospace"
      }}>
        <span>Frame: <strong>{currentFrame}</strong></span>
        <span>Time: <strong>{currentMs}ms</strong></span>
        <span>FPS: <strong>{FPS}</strong></span>
      </div>
    </div>
  );
}