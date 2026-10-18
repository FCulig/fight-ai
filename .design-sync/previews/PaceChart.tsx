import { PaceChart } from 'fightlytics';

const red = [2, 4, 3, 6, 5, 7, 4, 3, 5, 8, 6, 5, 4, 6, 7, 9, 6, 5];
const blue = [3, 3, 5, 4, 6, 4, 5, 6, 4, 3, 5, 7, 6, 5, 4, 3, 5, 4];

// Strikes landed per bin, red vs blue, with the round split and the playhead.
export const Momentum = () => (
  <div style={{ width: 640 }}>
    <PaceChart time={410} duration={600} r1End={300} redPace={red} bluePace={blue} />
  </div>
);

export const Compact = () => (
  <div style={{ width: 420 }}>
    <PaceChart time={0} duration={600} r1End={300} height={90} redPace={red} bluePace={blue} />
  </div>
);
