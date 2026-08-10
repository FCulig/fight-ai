import VideoPlayer from '../VideoPlayer';
import FighterOverlay, { type FighterOverlayHandle } from '../FighterOverlay';
import type { FighterFrame } from '../../types/FighterFrame';
import type { Corner } from './taxonomy';

interface Toast {
  text: string;
  color: string;
  icon: string;
}

interface AnnotateStageProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  overlayRef: React.RefObject<FighterOverlayHandle | null>;
  src: string | undefined;
  isPlaying: boolean;
  onTimeUpdate: () => void;
  onLoadedMetadata: () => void;
  onPlay: () => void;
  onPause: () => void;
  onTogglePlay: () => void;
  onStepForward: () => void;
  onStepBackward: () => void;
  frameMap: Map<number, FighterFrame[]>;
  fightWidth: number;
  fightHeight: number;
  currentRound: number | string;
  selectedCorner: Corner | null;
  redName: string;
  blueName: string;
  toast: Toast | null;
}

export default function AnnotateStage({
  videoRef, overlayRef, src, isPlaying, onTimeUpdate, onLoadedMetadata, onPlay, onPause,
  onTogglePlay, onStepForward, onStepBackward, frameMap, fightWidth, fightHeight,
  currentRound, selectedCorner, redName, blueName, toast,
}: AnnotateStageProps) {
  const selectedName = selectedCorner === 'red' ? redName : selectedCorner === 'blue' ? blueName : null;
  const selectedColor = selectedCorner === 'red' ? 'var(--f-red)' : 'var(--f-blue)';
  const highlightCorner = selectedCorner === 'red' ? 0 : selectedCorner === 'blue' ? 1 : null;

  return (
    <VideoPlayer
      ref={videoRef}
      src={src}
      isPlaying={isPlaying}
      onTimeUpdate={onTimeUpdate}
      onLoadedMetadata={onLoadedMetadata}
      onPlay={onPlay}
      onPause={onPause}
      onTogglePlay={onTogglePlay}
      onStepForward={onStepForward}
      onStepBackward={onStepBackward}
    >
      <FighterOverlay
        ref={overlayRef}
        frameMap={frameMap}
        fightWidth={fightWidth}
        fightHeight={fightHeight}
        showBoxes
        showSkeletons={false}
        highlightCorner={highlightCorner}
      />

      <div style={{ position: 'absolute', top: 14, left: 16, display: 'flex', gap: 8, alignItems: 'center', pointerEvents: 'none' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, background: 'rgba(0,0,0,0.55)',
          backdropFilter: 'blur(8px)', color: '#fff', fontSize: 11, fontWeight: 800,
          letterSpacing: '0.08em', padding: '4px 9px', borderRadius: 6,
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 14, color: 'var(--accent)' }}>edit_note</span>
          ANNOTATING
        </span>
        <span style={{
          background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)', color: '#fff',
          fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 6, letterSpacing: '0.04em',
        }}>
          {currentRound === '-' ? 'LOADING…' : `ROUND ${currentRound}`}
        </span>
      </div>

      {selectedName && (
        <div style={{
          position: 'absolute', top: 14, right: 16, display: 'flex', alignItems: 'center', gap: 7,
          pointerEvents: 'none', background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)',
          padding: '5px 11px', borderRadius: 6, border: `1px solid ${selectedColor}`,
        }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: selectedColor }} />
          <span style={{ fontSize: 11.5, fontWeight: 800, color: '#fff', letterSpacing: '0.03em' }}>{selectedName}</span>
        </div>
      )}

      {toast && (
        <div style={{
          position: 'absolute', left: '50%', bottom: 22, transform: 'translateX(-50%)', pointerEvents: 'none',
          display: 'flex', alignItems: 'center', gap: 9, padding: '9px 16px', borderRadius: 10,
          background: 'rgba(8,11,15,0.86)', backdropFilter: 'blur(10px)', border: `1px solid ${toast.color}`,
          boxShadow: `0 0 24px -6px ${toast.color}`, animation: 'feed-in .2s ease-out',
        }}>
          <span className="material-symbols-outlined" style={{ fontSize: 18, color: toast.color }}>{toast.icon}</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{toast.text}</span>
        </div>
      )}
    </VideoPlayer>
  );
}
