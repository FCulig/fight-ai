import { useRef, useEffect } from 'react';
import type { FighterFrame } from '../types/FighterFrame';

interface FighterOverlayProps {
  currentFrame: number;
  frameMap: Map<number, FighterFrame[]>;
  fightWidth: number;
  fightHeight: number;
  showBoxes: boolean;
}

export default function FighterOverlay({
  currentFrame,
  frameMap,
  fightWidth,
  fightHeight,
  showBoxes,
}: FighterOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.clientWidth;
    canvas.height = canvas.clientHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!showBoxes) return;

    const detections = frameMap.get(currentFrame);
    if (!detections) return;

    const scaleX = canvas.width / fightWidth;
    const scaleY = canvas.height / fightHeight;

    for (const d of detections) {
      ctx.strokeStyle = d.fighter_id === 0 ? '#ef4444' : '#3b82f6';
      ctx.lineWidth = 2;
      ctx.strokeRect(
        d.x1 * scaleX,
        d.y1 * scaleY,
        (d.x2 - d.x1) * scaleX,
        (d.y2 - d.y1) * scaleY,
      );
    }
  }, [currentFrame, frameMap, fightWidth, fightHeight, showBoxes]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
    />
  );
}
