import { StatusBadge } from 'fightlytics';

const row = { display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' as const };

// Icon + text always together: colour is never the only signal.
export const Statuses = () => (
  <div style={row}>
    <StatusBadge status="good">Within tolerance</StatusBadge>
    <StatusBadge status="warning">Few decisive frames</StatusBadge>
    <StatusBadge status="critical">Rounds missing</StatusBadge>
    <StatusBadge status="unverified">Not checked</StatusBadge>
    <StatusBadge status="circular">Seeded from pipeline</StatusBadge>
    <StatusBadge status="none">No data</StatusBadge>
  </div>
);

export const Small = () => (
  <div style={row}>
    <StatusBadge status="good" size="sm">Pass</StatusBadge>
    <StatusBadge status="warning" size="sm">Check</StatusBadge>
    <StatusBadge status="critical" size="sm">Fail</StatusBadge>
  </div>
);
