/**
 * Single source of truth for the manual-annotation palette: each ToolItem
 * drives the palette button, its keyboard shortcut, and the keyboard legend
 * simultaneously. Round boundaries aren't here — real Round rows already
 * exist from AI segmentation (see ai/fight_processing/write_frames_and_rounds).
 * Only "fight end" stays manual since no stage detects a fight's conclusion.
 */

export type Corner = 'red' | 'blue';
export type EventCat = 'strike' | 'grapple' | 'state' | 'round' | 'event';
export type Target = 'head' | 'body' | 'leg';

export interface ToolItem {
  key: string;
  num?: string;
  action: string;
  name: string;
  text: (fighterName: string, target?: Target) => string;
  needsFighter: boolean;
  /** Shift-modified: plain key = head, Shift+key = body. Read via e.code + e.shiftKey. */
  hasTarget?: boolean;
  /** Kicks already encode target in the action name — no modifier needed. */
  fixedTarget?: Target;
}

export interface ToolGroup {
  group: string;
  note?: string;
  items: ToolItem[];
}

// Shared by every hand strike + elbow so the description always reflects the
// real target instead of a value baked in per-action (right_hook used to be
// hardcoded "to the body" regardless of where it actually landed).
//
// jab/cross are lead/rear-relative (boxing terms), not absolute-handed —
// a southpaw's jab is thrown with their right hand. Hooks/uppercuts stay
// absolute left/right: that's what you can directly see (which arm moved)
// without first judging stance, and it's lossless either way since both
// hands collapse to the same family (`hook`/`uppercut`) at export time.
const HAND_STRIKE_NAMES: Record<string, string> = {
  jab: 'jab',
  cross: 'cross',
  left_hook: 'left hook',
  right_hook: 'right hook',
  left_uppercut: 'left uppercut',
  right_uppercut: 'right uppercut',
  elbow: 'elbow',
};

function handStrikeText(action: string, fighterName: string, target: Target = 'head'): string {
  return `${fighterName} ${HAND_STRIKE_NAMES[action]} to the ${target}`;
}

export const TOOL_GROUPS: ToolGroup[] = [
  {
    group: 'Strikes',
    note: 'Jab/cross = lead/rear hand (works for southpaws) · hooks/uppercuts = literal left/right · Shift = body',
    items: [
      { key: '1', num: '1', action: 'jab', name: 'Jab', needsFighter: true, hasTarget: true, text: (f, t) => handStrikeText('jab', f, t) },
      { key: '2', num: '2', action: 'cross', name: 'Cross', needsFighter: true, hasTarget: true, text: (f, t) => handStrikeText('cross', f, t) },
      { key: '3', num: '3', action: 'left_hook', name: 'Left hook', needsFighter: true, hasTarget: true, text: (f, t) => handStrikeText('left_hook', f, t) },
      { key: '4', num: '4', action: 'right_hook', name: 'Right hook', needsFighter: true, hasTarget: true, text: (f, t) => handStrikeText('right_hook', f, t) },
      { key: '5', num: '5', action: 'left_uppercut', name: 'Left uppercut', needsFighter: true, hasTarget: true, text: (f, t) => handStrikeText('left_uppercut', f, t) },
      { key: '6', num: '6', action: 'right_uppercut', name: 'Right uppercut', needsFighter: true, hasTarget: true, text: (f, t) => handStrikeText('right_uppercut', f, t) },
      { key: 'c', action: 'calf_kick', name: 'Calf kick', needsFighter: true, fixedTarget: 'leg', text: f => `${f} calf kick` },
      { key: 'l', action: 'low_kick', name: 'Low kick', needsFighter: true, fixedTarget: 'leg', text: f => `${f} low kick` },
      { key: 'm', action: 'middle_kick', name: 'Middle kick', needsFighter: true, fixedTarget: 'body', text: f => `${f} middle kick to the body` },
      { key: 'h', action: 'high_kick', name: 'High kick', needsFighter: true, fixedTarget: 'head', text: f => `${f} high kick to the head` },
      { key: 'e', action: 'elbow', name: 'Elbow', needsFighter: true, hasTarget: true, text: (f, t) => handStrikeText('elbow', f, t) },
      { key: 'n', action: 'clinch_knee', name: 'Clinch knee', needsFighter: true, text: f => `${f} knee in the clinch` },
    ],
  },
  {
    group: 'Ground & pound',
    note: 'No target/hand breakdown — same reason MMA stats don’t: a scramble isn’t a clean jab/hook, so this is punch/knee volume only',
    items: [
      { key: 'u', action: 'clinch_punch', name: 'Clinch punch', needsFighter: true, text: f => `${f} punches in the clinch` },
      { key: 'v', action: 'ground_punch', name: 'Ground and pound', needsFighter: true, text: f => `${f} lands ground and pound` },
      { key: 'j', action: 'ground_knee', name: 'Ground knee', needsFighter: true, text: f => `${f} knees from the ground` },
    ],
  },
  {
    group: 'Grappling',
    items: [
      { key: 't', action: 'takedown_attempt', name: 'Takedown attempt', needsFighter: true, text: f => `${f} shoots for a takedown` },
      { key: 'y', action: 'takedown_landed', name: 'Takedown landed', needsFighter: true, text: f => `${f} lands a takedown` },
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
      { key: 'f', action: 'state_clinch', name: 'Clinch', needsFighter: false, text: () => 'Fight state → CLINCH' },
      { key: 'g', action: 'state_ground', name: 'Ground', needsFighter: false, text: () => 'Fight state → GROUND' },
    ],
  },
];

export const KEYMAP: Record<string, ToolItem> = {};
TOOL_GROUPS.forEach(g => g.items.forEach(it => { KEYMAP[it.key] = it; }));

// Landed-vs-missed is deferred (MVP target is "count strikes thrown"), so every
// strike logs success=null — outcome unknown, not a claim that it landed.
// `knockdown` and `takedown_landed` are the exceptions: neither is a default
// outcome of pressing the key (unlike a strike, which the palette has no
// landed/missed toggle for), so a logged one genuinely happened.
const SUCCESS_TRUE_ACTIONS = new Set(['knockdown', 'takedown_landed']);

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
  { k: ['Esc'], label: 'Deselect fighter / clip' },
  { k: ['Z'], label: 'Undo last event (this session)' },
  { k: ['Click', 'Delete'], label: 'Select a timeline clip, then delete it (Delete = undo if nothing selected)' },
];

// Span kinds (round/corner_swap/excluded) are start/end toggles: press once to
// open a span at the playhead, press again to close it.
export const SPAN_KEYS: { k: string[]; label: string }[] = [
  { k: ['O'], label: 'Toggle corner-swap span' },
  { k: ['P'], label: 'Toggle excluded span' },
];

/** Frame (1-based) → "m:ss" clock, matching the currentFrame = floor(t*fps)+1 contract. */
export function formatFrameClock(frame: number, fps: number): string {
  const seconds = Math.max(0, (frame - 1) / fps);
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}
