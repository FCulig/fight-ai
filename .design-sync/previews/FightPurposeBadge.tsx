import { FightPurposeBadge } from 'fightlytics';

const row = { display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' as const };

export const Purposes = () => (
  <div style={row}>
    <FightPurposeBadge purpose="ai_labeled" />
    <FightPurposeBadge purpose="training_data" />
    <FightPurposeBadge purpose="reference" />
  </div>
);

// `sm` sits in a fight-list card subtitle.
export const Small = () => (
  <div style={row}>
    <FightPurposeBadge purpose="ai_labeled" size="sm" />
    <FightPurposeBadge purpose="training_data" size="sm" />
    <FightPurposeBadge purpose="reference" size="sm" />
  </div>
);
