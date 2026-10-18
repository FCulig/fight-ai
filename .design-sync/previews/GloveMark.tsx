import { GloveMark } from 'fightlytics';

export const Sizes = () => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
    <GloveMark size={24} /><GloveMark size={34} /><GloveMark size={56} /><GloveMark size={88} />
  </div>
);

// `mono` draws in currentColor with no fill.
export const Mono = () => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 20, color: 'var(--text-primary)' }}>
    <GloveMark size={34} mono /><span style={{ color: 'var(--text-muted)' }}><GloveMark size={34} mono /></span>
  </div>
);
