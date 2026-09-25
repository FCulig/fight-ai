import { useRef, useState, useEffect, useCallback } from 'react';
import type { Fight } from '../../types/Fight';
import { useFighterFrames } from '../../hooks/useFighterFrames';
import { useEvents } from '../../hooks/useEvents';
import FighterOverlay, { type FighterOverlayHandle } from '../FighterOverlay';

const CLIP_DURATION_SECS = 0.6;
const SPEED_KEY = 'td-clip-speed';
const SPEEDS = [0.25, 0.5, 1] as const;
type Speed = (typeof SPEEDS)[number];

function loadSpeed(): Speed {
  const stored = Number(localStorage.getItem(SPEED_KEY));
  return (SPEEDS as readonly number[]).includes(stored) ? (stored as Speed) : 0.5;
}

interface ClipPlayerProps {
  fight: Fight;
  frame: number; // the reviewed event's frame (1-based)
  corner: number | null;
}

/**
 * A short, looping window of the real fight video around one labelled
 * event's frame, with the real FighterOverlay boxes/skeletons drawn on top —
 * reuses the same frame-numbering contract and requestVideoFrameCallback
 * draw loop as Player.tsx, just scoped to a strict 0.6s window instead of
 * the whole fight.
 */
export default function ClipPlayer({ fight, frame, corner }: ClipPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<FighterOverlayHandle>(null);
  const rafRef = useRef<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [showBoxes, setShowBoxes] = useState(true);
  const [showSkeletons, setShowSkeletons] = useState(true);
  const [speed, setSpeed] = useState<Speed>(loadSpeed);
  const [currentTime, setCurrentTime] = useState(0);

  useEffect(() => { localStorage.setItem(SPEED_KEY, String(speed)); }, [speed]);

  const { events: swapEvents } = useEvents(fight.id, { source: 'label', kind: 'corner_swap' });
  const cornerSwapSpans = swapEvents.map((e) => ({ frame: e.frame, end_frame: e.end_frame }));

  const fps = fight.fps;
  // Whole-frame math so the clip is a strict CLIP_DURATION_SECS regardless of
  // fps rounding — a time-based half-window would drift by fractional frames.
  const windowFrames = Math.max(1, Math.round(CLIP_DURATION_SECS * fps));
  const eventFrameIdx = frame - 1; // 0-based
  const windowStartFrame = Math.max(0, eventFrameIdx - Math.floor(windowFrames / 2));
  const windowEndFrame = windowStartFrame + windowFrames;
  const windowStart = windowStartFrame / fps;
  const windowEnd = windowEndFrame / fps;

  // Only this clip's ~30-frame window, not the whole fight — a full fight's
  // keypoints run into the tens of MB (see frontend CLAUDE.md's "Fighter-frame
  // payload size"), which used to make every review's skeleton wait on that
  // whole download. +1s: windowStartFrame/windowEndFrame are 0-based indices,
  // fighter_frames.frame is 1-based.
  const { frameMap } = useFighterFrames(fight.id, {
    start_frame: windowStartFrame + 1,
    end_frame: windowEndFrame + 1,
  });

  // Jump to the event's window whenever the reviewed event changes.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const seek = () => {
      video.currentTime = windowStart;
      video.playbackRate = speed;
      setCurrentTime(windowStart);
      video.play().catch(() => {});
      setIsPlaying(true);
    };
    if (video.readyState >= 1) seek();
    else video.addEventListener('loadedmetadata', seek, { once: true });
    return () => video.removeEventListener('loadedmetadata', seek);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fight.id, frame]);

  useEffect(() => {
    const video = videoRef.current;
    if (video) video.playbackRate = speed;
  }, [speed]);

  // Loop playback within [windowStart, windowEnd] and draw the overlay per frame.
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !isPlaying) {
      if (rafRef.current !== null && video) {
        video.cancelVideoFrameCallback(rafRef.current);
        rafRef.current = null;
      }
      return;
    }
    const tick = (_now: DOMHighResTimeStamp, metadata: VideoFrameCallbackMetadata) => {
      const t = metadata.mediaTime;
      if (t >= windowEnd) {
        // Loop back to the start. Seeking is async — the video still shows
        // the old (near-windowEnd) frame until the browser actually presents
        // the post-seek one, so drawing "as if" we were already at
        // windowStart here would put the clip's first-frame skeleton on top
        // of the still-visible last frame: exactly the skeleton "jump" this
        // used to show right before every loop restart. Just seek and wait
        // for the next callback, whose `metadata.mediaTime` reports whatever
        // frame the seek actually landed on, so the overlay stays in sync
        // with what's on screen.
        video.currentTime = windowStart;
        rafRef.current = video.requestVideoFrameCallback(tick);
        return;
      }
      overlayRef.current?.draw(Math.floor(t * fps) + 1);
      setCurrentTime(t);
      rafRef.current = video.requestVideoFrameCallback(tick);
    };
    rafRef.current = video.requestVideoFrameCallback(tick);
    return () => {
      if (rafRef.current !== null) video.cancelVideoFrameCallback(rafRef.current);
      rafRef.current = null;
    };
  }, [isPlaying, windowStart, windowEnd, fps]);

  const togglePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (isPlaying) { video.pause(); setIsPlaying(false); } else { video.play().catch(() => {}); setIsPlaying(true); }
  }, [isPlaying]);

  const handleScrub = (t: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    setIsPlaying(false);
    video.currentTime = t;
    setCurrentTime(t);
    overlayRef.current?.draw(Math.floor(t * fps) + 1);
  };

  const stepFrame = useCallback((delta: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    setIsPlaying(false);
    const t = Math.min(Math.max(video.currentTime + delta / fps, windowStart), windowEnd);
    video.currentTime = t;
    setCurrentTime(t);
    overlayRef.current?.draw(Math.floor(t * fps) + 1);
  }, [fps, windowStart, windowEnd]);

  const clipFrame = Math.floor((currentTime - windowStart) * fps) + 1;
  const clipFrames = Math.max(1, Math.round((windowEnd - windowStart) * fps));

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap', marginBottom: 10 }}>
        <button type="button" className={'pill' + (showSkeletons ? ' active' : '')} onClick={() => setShowSkeletons((v) => !v)} style={{ padding: '4px 10px', fontSize: 11 }}>Skeleton</button>
        <button type="button" className={'pill' + (showBoxes ? ' active' : '')} onClick={() => setShowBoxes((v) => !v)} style={{ padding: '4px 10px', fontSize: 11 }}>Box</button>
      </div>

      <div style={{ position: 'relative', width: '100%', maxWidth: 720, margin: '0 auto', borderRadius: 12, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.07)', background: '#000' }}>
        <video
          ref={videoRef}
          src={`/fights/${fight.id}/video`}
          muted
          playsInline
          style={{ width: '100%', display: 'block' }}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
        />
        <FighterOverlay
          ref={overlayRef}
          frameMap={frameMap}
          fightWidth={fight.width}
          fightHeight={fight.height}
          showBoxes={showBoxes}
          showSkeletons={showSkeletons}
          highlightCorner={corner as 0 | 1 | null}
          hideUnhighlighted
          cornerSwapSpans={cornerSwapSpans}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 11, flexWrap: 'wrap', marginTop: 11 }}>
        <button type="button" onClick={() => stepFrame(-1)} title="Previous frame" style={{ width: 28, height: 28, borderRadius: 8, display: 'grid', placeItems: 'center', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-glass)', color: 'var(--text-secondary)', cursor: 'pointer', flexShrink: 0 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 15 }}>skip_previous</span>
        </button>
        <button type="button" className="lab-ibtn" onClick={togglePlay} title="Play / pause" style={{ width: 32, height: 32, borderRadius: 8, display: 'grid', placeItems: 'center', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-glass)', color: 'var(--text-secondary)', cursor: 'pointer', flexShrink: 0 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>{isPlaying ? 'pause' : 'play_arrow'}</span>
        </button>
        <button type="button" onClick={() => stepFrame(1)} title="Next frame" style={{ width: 28, height: 28, borderRadius: 8, display: 'grid', placeItems: 'center', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-glass)', color: 'var(--text-secondary)', cursor: 'pointer', flexShrink: 0 }}>
          <span className="material-symbols-outlined" style={{ fontSize: 15 }}>skip_next</span>
        </button>
        <input
          type="range"
          min={windowStart}
          max={windowEnd}
          step={1 / fps}
          value={currentTime}
          onChange={(e) => handleScrub(Number(e.target.value))}
          style={{ flex: 1, minWidth: 140, accentColor: 'var(--cyan-400)', height: 4 }}
          aria-label="Frame"
        />
        <span style={{ fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>
          {String(Math.min(clipFrame, clipFrames)).padStart(2, '0')} / {clipFrames}
        </span>
        <div style={{ display: 'flex', gap: 4, padding: 3, borderRadius: 9, background: 'rgba(0,0,0,0.28)', border: '1px solid var(--border-subtle)' }}>
          {SPEEDS.map((s) => (
            <button key={s} type="button" className={'pill' + (speed === s ? ' active' : '')} onClick={() => setSpeed(s)} title="Playback speed — remembered next time" style={{ padding: '4px 9px', fontSize: 11 }}>{s}×</button>
          ))}
        </div>
      </div>
      <div style={{ marginTop: 9, fontSize: 10.5, fontWeight: 600, color: 'var(--text-disabled)' }}>
        {fight.video_path.split('/').pop()} · {fps} fps
      </div>
    </div>
  );
}
