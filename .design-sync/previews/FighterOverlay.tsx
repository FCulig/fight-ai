import { FighterOverlay } from 'fightlytics';

// COCO-17 keypoints for a fighter standing at x, in a 1280×720 frame.
function pose(x: number, lean: number): [number, number][] {
  const p: [number, number][] = [
    [0, 0], [-6, -4], [6, -4], [-12, 0], [12, 0], [-34, 46], [34, 46], [-52, 110 + lean], [50, 104], [-30, 70], [44, 64],
    [-24, 190], [24, 190], [-40, 290], [38, 290], [-52, 390], [46, 390],
  ];
  return p.map(([dx, dy]) => [x + dx, 190 + dy]);
}

const frameMap = new Map([[1, [
  { fight_id: 1, frame: 1, corner: 0, x1: 360, y1: 160, x2: 500, y2: 600, confidence: 0.94, keypoints: pose(430, 0) },
  { fight_id: 1, frame: 1, corner: 1, x1: 760, y1: 150, x2: 910, y2: 600, confidence: 0.91, keypoints: pose(835, 10) },
]]]);

const stage = { position: 'relative' as const, width: 640, height: 360, background: '#16171a', borderRadius: 8, overflow: 'hidden' };

// Skeletons in corner colours over the video; the selected corner also gets its box.
export const SkeletonsRedSelected = () => (
  <div style={stage}>
    <FighterOverlay frameMap={frameMap} fightWidth={1280} fightHeight={720} showBoxes showSkeletons highlightCorner={0} />
  </div>
);

export const SkeletonsOnly = () => (
  <div style={stage}>
    <FighterOverlay frameMap={frameMap} fightWidth={1280} fightHeight={720} showBoxes={false} showSkeletons />
  </div>
);
