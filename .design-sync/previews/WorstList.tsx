import { WorstList } from 'fightlytics';

const missed = [
  { frame: 1842, fighter: 'red' as const, family: 'jab', target: 'head', landed: true },
  { frame: 2210, fighter: 'blue' as const, family: 'kick', target: 'leg', landed: true },
  { frame: 3977, fighter: 'red' as const, family: 'hook', target: 'body', landed: null },
  { frame: 5120, fighter: 'blue' as const, family: 'cross', target: 'head', landed: true },
];
const spurious = [
  { frame: 940, fighter: 'blue' as const, family: 'jab', target: 'head', landed: null, action: 'jab_head' },
  { frame: 4410, fighter: 'red' as const, family: 'knee', target: 'body', landed: null, action: 'knee_body' },
];

// The Accuracy page's review queue: misses and false positives side by side.
export const ReviewQueue = () => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, width: 620 }}>
    <WorstList title="Worst misses" fps={30} items={missed} emptyLabel="No missed strikes." />
    <WorstList title="Worst false positives" fps={30} items={spurious} emptyLabel="No false positives." />
  </div>
);

export const Empty = () => (
  <div style={{ width: 300 }}><WorstList title="Worst misses" fps={30} items={[]} emptyLabel="No missed strikes." /></div>
);
