import { LiveFeed } from 'fightlytics';

const base = { fight_id: 1, source: 'label' as const, kind: 'point' as const, end_frame: null, description: null,
  fighter_id: null, success: null, state: null, value: null, labeler: 'dev', created_at: '2026-10-01T12:00:00Z', is_verified: null };

const events = [
  { ...base, id: 1, frame: 90, corner: null, action: 'state_striking', target: null },
  { ...base, id: 2, frame: 212, corner: 0, action: 'jab', target: 'head' },
  { ...base, id: 3, frame: 260, corner: 1, action: 'calf_kick', target: 'leg' },
  { ...base, id: 4, frame: 341, corner: 0, action: 'cross', target: 'body' },
  { ...base, id: 5, frame: 455, corner: 1, action: 'takedown_attempt', target: null },
  { ...base, id: 6, frame: 470, corner: 0, action: 'takedown_defended', target: null },
  { ...base, id: 7, frame: 610, corner: 1, action: 'left_hook', target: 'head' },
  { ...base, id: 8, frame: 702, corner: 0, action: 'knockdown', target: null, success: true },
];

const noop = () => {};

// Player's right column: events up to the playhead, newest at the bottom.
export const PlayByPlay = () => (
  <div style={{ height: 600, width: 380 }}>
    <LiveFeed events={events} currentFrame={720} fps={30} onSeek={noop} redName="Adesanya" blueName="Pereira" />
  </div>
);

export const BeforeFirstEvent = () => (
  <div style={{ height: 260, width: 380 }}>
    <LiveFeed events={events} currentFrame={30} fps={30} onSeek={noop} redName="Adesanya" blueName="Pereira" />
  </div>
);
