import { useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
import type { FighterFrame } from '../types/FighterFrame';

// COCO-17 skeleton edges — matches pose_verification.py
const SKELETON_EDGES: [number, number][] = [
  [0, 1], [0, 2], [1, 3], [2, 4],
  [0, 5], [0, 6],
  [5, 7], [7, 9],
  [6, 8], [8, 10],
  [5, 6],
  [5, 11], [6, 12],
  [11, 12],
  [11, 13], [13, 15],
  [12, 14], [14, 16],
];

const COLOR_RED  = '#ef4444';
const COLOR_BLUE = '#3b82f6';

interface FighterOverlayProps {
  frameMap: Map<number, FighterFrame[]>;
  fightWidth: number;
  fightHeight: number;
  showBoxes: boolean;
  showSkeletons: boolean;
}

export interface FighterOverlayHandle {
  draw: (frame: number) => void;
}

const FighterOverlay = forwardRef<FighterOverlayHandle, FighterOverlayProps>(
  ({ frameMap, fightWidth, fightHeight, showBoxes, showSkeletons }, ref) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const frameMapRef = useRef(frameMap);
    const fightWidthRef = useRef(fightWidth);
    const fightHeightRef = useRef(fightHeight);
    const showBoxesRef = useRef(showBoxes);
    const showSkeletonsRef = useRef(showSkeletons);

    useEffect(() => { frameMapRef.current = frameMap; }, [frameMap]);
    useEffect(() => { fightWidthRef.current = fightWidth; }, [fightWidth]);
    useEffect(() => { fightHeightRef.current = fightHeight; }, [fightHeight]);
    useEffect(() => { showBoxesRef.current = showBoxes; }, [showBoxes]);
    useEffect(() => { showSkeletonsRef.current = showSkeletons; }, [showSkeletons]);

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

        const drawBoxes = showBoxesRef.current;
        const drawSkeletons = showSkeletonsRef.current;
        if (!drawBoxes && !drawSkeletons) return;

        const detections = frameMapRef.current.get(frame);
        if (!detections) return;

        const scaleX = canvas.width / fightWidthRef.current;
        const scaleY = canvas.height / fightHeightRef.current;

        for (const d of detections) {
          const color = d.fighter_id === 0 ? COLOR_RED : COLOR_BLUE;

          if (drawBoxes) {
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.strokeRect(
              d.x1 * scaleX,
              d.y1 * scaleY,
              (d.x2 - d.x1) * scaleX,
              (d.y2 - d.y1) * scaleY,
            );
          }

          if (drawSkeletons && d.keypoints && d.keypoints.length === 17) {
            ctx.strokeStyle = color;
            ctx.fillStyle = color;
            ctx.lineWidth = 1.5;

            // Draw skeleton edges
            for (const [a, b] of SKELETON_EDGES) {
              const pa = d.keypoints[a];
              const pb = d.keypoints[b];
              if (!pa || !pb) continue;
              const ax = pa[0] * scaleX;
              const ay = pa[1] * scaleY;
              const bx = pb[0] * scaleX;
              const by = pb[1] * scaleY;
              ctx.beginPath();
              ctx.moveTo(ax, ay);
              ctx.lineTo(bx, by);
              ctx.stroke();
            }

            // Draw joint dots
            for (const kp of d.keypoints) {
              if (!kp) continue;
              ctx.beginPath();
              ctx.arc(kp[0] * scaleX, kp[1] * scaleY, 3, 0, Math.PI * 2);
              ctx.fill();
            }
          }
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
