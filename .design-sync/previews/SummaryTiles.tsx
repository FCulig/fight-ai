import { SummaryTiles } from 'fightlytics';

const stats = (o: object) => ({ sig: [54, 112], total: [61, 125], head: 31, body: 14, leg: 9, distance: 38, clinch: 11, ground: 5,
  td: [1, 3], ctrl: 74, kd: 1, sub: 0, acc: 48, ...o });

// The Player report's four hero tiles, computed from both fighters' stats.
export const WholeFight = () => (
  <div style={{ width: 990 }}>
    <SummaryTiles red={stats({})} blue={stats({ sig: [41, 97], total: [45, 104], head: 22, body: 12, leg: 7, td: [2, 5], ctrl: 131, kd: 0, acc: 42 })}
      redName="Adesanya" blueName="Pereira" scopeLabel="Whole fight" />
  </div>
);
