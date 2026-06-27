export interface FighterFrame {
  fight_id: number;
  frame: number;
  corner: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  confidence: number | null;
  keypoints: [number, number][] | null;
}
