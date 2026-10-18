import { AccGauge } from 'fightlytics';

// Orange is the AI's colour: model scores use --accent; human counts use ink.
export const ModelScore = () => <AccGauge pct={78} color="var(--accent)" label="Strike F1" />;

export const Pair = () => (
  <div style={{ display: 'flex', gap: 28 }}>
    <AccGauge pct={64} color="var(--text-primary)" label="Head accuracy" />
    <AccGauge pct={41} color="var(--text-primary)" label="Body accuracy" />
  </div>
);
