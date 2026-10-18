import { MiniStat } from 'fightlytics';

// A row of stat tiles: digits in .font-num, label underneath.
export const StatRow = () => (
  <div style={{ display: 'flex', gap: 10, width: 460 }}>
    <MiniStat value={54} label="Strikes landed" />
    <MiniStat value="3" label="Takedowns" />
    <MiniStat value="62%" label="Head share" />
  </div>
);

export const TimingTiles = () => (
  <div style={{ display: 'flex', gap: 10, width: 460 }}>
    <MiniStat value="+2f" label="Timing bias" />
    <MiniStat value="4f" label="Timing jitter" />
    <MiniStat value="14.6" label="Minutes scored" />
  </div>
);
