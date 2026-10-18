import { SegBar } from 'fightlytics';

// From FightBreakdown: where one fighter's landed strikes went.
export const StrikeTargets = () => (
  <div style={{ width: 320 }}>
    <SegBar parts={[
      { val: 31, color: 'var(--text-primary)', label: 'Head' },
      { val: 14, color: 'rgba(242,241,238,0.55)', label: 'Body' },
      { val: 9, color: 'rgba(242,241,238,0.28)', label: 'Leg' },
    ]} />
  </div>
);

// Position split uses the validated fight-state trio.
export const StrikesByPosition = () => (
  <div style={{ width: 320 }}>
    <SegBar parts={[
      { val: 38, color: 'var(--state-striking)', label: 'Distance' },
      { val: 11, color: 'var(--state-clinch)', label: 'Clinch' },
      { val: 5, color: 'var(--state-ground)', label: 'Ground' },
    ]} />
  </div>
);
