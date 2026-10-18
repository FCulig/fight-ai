import { VerdictBadge } from 'fightlytics';

const row = { display: 'flex', gap: 8, alignItems: 'center' };

// Training Data QA's verdict on a label: is_verified true / false / null.
export const Verdicts = () => (
  <div style={row}>
    <VerdictBadge isVerified={true} />
    <VerdictBadge isVerified={false} />
    <VerdictBadge isVerified={null} />
  </div>
);

export const Small = () => (
  <div style={row}>
    <VerdictBadge isVerified={true} sm />
    <VerdictBadge isVerified={false} sm />
    <VerdictBadge isVerified={null} sm />
  </div>
);
