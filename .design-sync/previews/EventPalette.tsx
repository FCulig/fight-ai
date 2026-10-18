import { EventPalette } from 'fightlytics';

const noop = () => {};

// Annotate's right column. With a fighter selected every tool is live.
export const FighterSelected = () => (
  <div style={{ width: 420 }}><EventPalette selected onLog={noop} onFightEnd={noop} /></div>
);

// Fighter-specific tools dim until R/B picks a corner; fight-state tools stay live.
export const NoFighter = () => (
  <div style={{ width: 420 }}><EventPalette selected={false} onLog={noop} onFightEnd={noop} /></div>
);
