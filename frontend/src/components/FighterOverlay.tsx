import { useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import type { FighterFrame } from '../types/FighterFrame';

interface FighterOverlayProps {
  frameMap: Map<number, FighterFrame[]>;
  fightWidth: number;
  fightHeight: number;
  showBoxes: boolean;
}

export interface FighterOverlayHandle {
  draw: (frame: number) => void;
}

const FighterOverlay = forwardRef<FighterOverlayHandle, FighterOverlayProps>(
  ({ frameMap, fightWidth, fightHeight, showBoxes }, ref) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const frameMapRef = useRef(frameMap);
    const fightWidthRef = useRef(fightWidth);
    const fightHeightRef = useRef(fightHeight);
    const showBoxesRef = useRef(showBoxes);

    useEffect(() => { frameMapRef.current = frameMap; }, [frameMap]);
    useEffect(() => { fightWidthRef.current = fightWidth; }, [fightWidth]);
    useEffect(() => { fightHeightRef.current = fightHeight; }, [fightHeight]);
    useEffect(() => { showBoxesRef.current = showBoxes; }, [showBoxes]);

    useImperativeHandle(ref, () => ({
      draw(frame: number) {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        if (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight) {
          canvas.width = canvas.clientWidth;
          canvas.height = canvas.clientHeight;
        }
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (!showBoxesRef.current) return;

        const detections = frameMapRef.current.get(frame);
        if (!detections) return;

        const scaleX = canvas.width / fightWidthRef.current;
        const scaleY = canvas.height / fightHeightRef.current;

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
      },
    }));

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
  },
);

FighterOverlay.displayName = 'FighterOverlay';
export default FighterOverlay;
