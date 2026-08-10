/**
 * Single source of truth for the manual-annotation palette: each ToolItem
 * drives the palette button, its keyboard shortcut, and the keyboard legend
 * simultaneously. Round boundaries aren't here — real Round rows already
 * exist from AI segmentation (see ai/fight_processing/write_frames_and_rounds).
 * Only "fight end" stays manual since no stage detects a fight's conclusion.
 */

export type Corner = 'red' | 'blue';
export type EventCat = 'strike' | 'grapple' | 'state' | 'round' | 'event';

export interface ToolItem {
  key: string;
  num?: string;
  action: string;
  name: string;
  text: (fighterName: string) => string;
  needsFighter: boolean;
}

export interface ToolGroup {
  group: string;
  note?: string;
  items: ToolItem[];
}

export const TOOL_GROUPS: ToolGroup[] = [
  {
    group: 'Strikes',
    note: 'Hand strikes use boxing numbers',
    items: [
      { key: '1', num: '1', action: 'jab', name: 'Jab', needsFighter: true, text: f => `${f} jab to the head` },
      { key: '2', num: '2', action: 'straight_right', name: 'Straight right', needsFighter: true, text: f => `${f} straight right to the head` },
      { key: '3', num: '3', action: 'left_hook', name: 'Left hook', needsFighter: true, text: f => `${f} left hook to the head` },
      { key: '4', num: '4', action: 'right_hook', name: 'Right hook', needsFighter: true, text: f => `${f} right hook to the body` },
      { key: '5', num: '5', action: 'left_uppercut', name: 'Left uppercut', needsFighter: true, text: f => `${f} left uppercut on the inside` },
      { key: '6', num: '6', action: 'right_uppercut', name: 'Right uppercut', needsFighter: true, text: f => `${f} right uppercut on the inside` },
      { key: 'c', action: 'calf_kick', name: 'Calf kick', needsFighter: true, text: f => `${f} calf kick` },
      { key: 'l', action: 'low_kick', name: 'Low kick', needsFighter: true, text: f => `${f} low kick` },
      { key: 'm', action: 'middle_kick', name: 'Middle kick', needsFighter: true, text: f => `${f} middle kick to the body` },
      { key: 'h', action: 'high_kick', name: 'High kick', needsFighter: true, text: f => `${f} high kick to the head` },
      { key: 'e', action: 'elbow', name: 'Elbow', needsFighter: true, text: f => `${f} elbow` },
      { key: 'n', action: 'knee', name: 'Knee', needsFighter: true, text: f => `${f} knee in the clinch` },
    ],
  },
  {
    group: 'Grappling',
    items: [
      { key: 't', action: 'takedown_attempt', name: 'Takedown attempt', needsFighter: true, text: f => `${f} shoots for a takedown` },
      { key: 'd', action: 'takedown_defended', name: 'Takedown defended', needsFighter: true, text: f => `${f} defends the takedown` },
      { key: 's', action: 'submission_attempt', name: 'Submission', needsFighter: true, text: f => `${f} threatens a submission` },
    ],
  },
  {
    group: 'Outcome',
    items: [
      { key: 'x', action: 'knockdown', name: 'Knockdown', needsFighter: true, text: f => `${f} scores a KNOCKDOWN` },
    ],
  },
  {
    group: 'Fight state',
    items: [
      { key: 'w', action: 'state_striking', name: 'Striking', needsFighter: false, text: () => 'Fight state → STRIKING' },
      { key: 'g', action: 'state_grappling', name: 'Grappling', needsFighter: false, text: () => 'Fight state → GRAPPLING' },
    ],
  },
];

export const KEYMAP: Record<string, ToolItem> = {};
TOOL_GROUPS.forEach(g => g.items.forEach(it => { KEYMAP[it.key] = it; }));

// The palette has no landed/blocked toggle — every strike it logs is "landed".
// Grapple/outcome-adjacent actions (attempts, submissions) have no confirmed
// landed/missed outcome, so success stays null/unknown for those.
const SUCCESS_TRUE_ACTIONS = new Set([
  'jab', 'straight_right', 'left_hook', 'right_hook', 'left_uppercut', 'right_uppercut',
  'calf_kick', 'low_kick', 'middle_kick', 'high_kick', 'elbow', 'knee', 'knockdown',
]);

export function successForAction(action: string): boolean | null {
  return SUCCESS_TRUE_ACTIONS.has(action) ? true : null;
}

export function categoryForAction(action: string | null): EventCat {
  if (!action) return 'state';
  if (action === 'fight_end' || action === 'submission_attempt') return 'event';
  if (action.startsWith('takedown_')) return 'grapple';
  if (action.startsWith('state_')) return 'state';
  if (action.startsWith('round_')) return 'round';
  return 'strike';
}

export function colorForAction(action: string | null): string {
  if (!action) return 'var(--text-muted)';
  if (action === 'knockdown') return 'var(--f-red)';
  if (action === 'fight_end' || action === 'submission_attempt') return 'var(--purple-600)';
  if (action.startsWith('takedown_')) return 'var(--orange-400)';
  if (action.startsWith('state_')) return 'var(--slate-400)';
  if (action.startsWith('round_')) return 'var(--green-500)';
  return 'var(--accent)';
}

export function iconForAction(action: string | null): string {
  if (!action) return 'radio_button_checked';
  if (action === 'knockdown') return 'sports_mma';
  if (action === 'fight_end') return 'sports_score';
  if (action === 'submission_attempt') return 'crisis_alert';
  if (action.startsWith('takedown_')) return 'sports_kabaddi';
  if (action.startsWith('state_')) return 'change_circle';
  if (action.startsWith('round_')) return 'timer';
  return 'bolt';
}

export const FILTERS: { key: string; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'strike', label: 'Strikes' },
  { key: 'state', label: 'Fight State' },
  { key: 'grapple', label: 'Grapple' },
];

export function matchFilter(cat: EventCat, filter: string): boolean {
  if (filter === 'all') return true;
  if (filter === 'grapple') return cat === 'grapple' || cat === 'event';
  if (filter === 'state') return cat === 'state' || cat === 'round';
  return cat === filter;
}

export const PLAYBACK_KEYS: { k: string[]; label: string }[] = [
  { k: ['Space'], label: 'Play / pause' },
  { k: ['←', '→'], label: 'Seek ±1 s' },
  { k: ['⇧', '←/→'], label: 'Seek ±5 s' },
  { k: [',', '.'], label: 'Step ±1 frame' },
];

export const EDIT_KEYS: { k: string[]; label: string }[] = [
  { k: ['R'], label: 'Select red corner' },
  { k: ['B'], label: 'Select blue corner' },
  { k: ['Esc'], label: 'Deselect fighter' },
  { k: ['Z'], label: 'Undo last event' },
];

/** Frame (1-based) → "m:ss" clock, matching the currentFrame = floor(t*fps)+1 contract. */
export function formatFrameClock(frame: number, fps: number): string {
  const seconds = Math.max(0, (frame - 1) / fps);
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}
