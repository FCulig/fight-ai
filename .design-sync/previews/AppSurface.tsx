import { AppSurface, MiniStat } from 'fightlytics';

// Every screen sits on the off-black page with ink text.
export const Page = () => (
  <AppSurface padding={28} style={{ width: 520 }}>
    <div className="eyebrow">Accuracy</div>
    <h2 className="font-display" style={{ fontSize: 34, margin: '6px 0 16px' }}>Pipeline accuracy.</h2>
    <div className="glass" style={{ padding: 18, display: 'flex', gap: 10 }}>
      <MiniStat value="71.4" label="Strike F1" />
      <MiniStat value="+2f" label="Timing bias" />
    </div>
  </AppSurface>
);
