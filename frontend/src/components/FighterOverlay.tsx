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

// Matches the fighter-corner-btn selected-state fill (`color-mix(in srgb, ${color} 12%, transparent)`).
function withAlpha(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

interface FighterOverlayProps {
  frameMap: Map<number, FighterFrame[]>;
  fightWidth: number;
  fightHeight: number;
  showBoxes: boolean;
  showSkeletons: boolean;
  /** Corner (0 = red, 1 = blue) of the fighter the user has selected. No box is drawn until this is set. */
  highlightCorner?: 0 | 1 | null;
}

export interface FighterOverlayHandle {
  draw: (frame: number) => void;
}

const FighterOverlay = forwardRef<FighterOverlayHandle, FighterOverlayProps>(
  ({ frameMap, fightWidth, fightHeight, showBoxes, showSkeletons, highlightCorner = null }, ref) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const frameMapRef = useRef(frameMap);
    const fightWidthRef = useRef(fightWidth);
    const fightHeightRef = useRef(fightHeight);
    const showBoxesRef = useRef(showBoxes);
    const showSkeletonsRef = useRef(showSkeletons);
    const highlightCornerRef = useRef(highlightCorner);
    const lastFrameRef = useRef(1);

    useEffect(() => { frameMapRef.current = frameMap; }, [frameMap]);
    useEffect(() => { fightWidthRef.current = fightWidth; }, [fightWidth]);
    useEffect(() => { fightHeightRef.current = fightHeight; }, [fightHeight]);
    useEffect(() => { showBoxesRef.current = showBoxes; }, [showBoxes]);
    useEffect(() => { showSkeletonsRef.current = showSkeletons; }, [showSkeletons]);

    const render = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      if (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight) {
        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
      }
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const drawSkeletons = showSkeletonsRef.current;
      const drawBoxes = showBoxesRef.current;
      if (!drawBoxes && !drawSkeletons) return;

      const detections = frameMapRef.current.get(lastFrameRef.current);
      if (!detections) return;

      const scaleX = canvas.width / fightWidthRef.current;
      const scaleY = canvas.height / fightHeightRef.current;
      const highlight = highlightCornerRef.current;

      for (const d of detections) {
        const color = d.corner === 0 ? COLOR_RED : COLOR_BLUE;
        const isSelected = highlight !== null && highlight === d.corner;

        // The box stays hidden until this fighter's corner is selected. Static styling
        // mirrors the selected fighter-corner-btn (tinted fill + glow, no motion).
        if (drawBoxes && isSelected) {
          const x = d.x1 * scaleX;
          const y = d.y1 * scaleY;
          const w = (d.x2 - d.x1) * scaleX;
          const h = (d.y2 - d.y1) * scaleY;

          const radius = Math.min(12, w / 2, h / 2);

          ctx.save();
          ctx.beginPath();
          ctx.roundRect(x, y, w, h, radius);
          ctx.fillStyle = withAlpha(color, 0.12);
          ctx.fill();

          ctx.shadowColor = color;
          ctx.shadowBlur = 14;
          ctx.strokeStyle = color;
          ctx.lineWidth = 2;
          ctx.stroke();
          ctx.restore();
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
    };

    useImperativeHandle(ref, () => ({
      draw(frame: number) {
        lastFrameRef.current = frame;
        render();
      },
    }));

    useEffect(() => {
      highlightCornerRef.current = highlightCorner;
      render();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [highlightCorner]);

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
