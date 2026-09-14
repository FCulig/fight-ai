// Reconstructs the human-readable line for an Event at display time, instead
// of trusting a frozen `description` string. `description` is only ever
// stored (and required, via a DB CHECK) for `action='fight_end'` — every
// other point event is fully reconstructable from its structured columns:
//   - label rows (source='label'): action + target + corner, via the same
//     taxonomy.ts ToolItem.text() templates Annotate's palette used to build
//     the (now-unstored) description with in the first place.
//   - prediction rows (source='prediction'): action + fighter_id + success +
//     state (+ the `rounds` table, for round markers' round number).
// Reconstructing on every render — rather than writing a corrected string
// back — is what makes this correct even when a corner_swap span is added or
// edited after the strike was already logged.
import type { Event } from '../types/Event';
import { ACTION_TO_TOOL, type Target } from '../components/annotate/taxonomy';

export interface DescribeRound {
  round_number: number;
  start_frame: number;
  end_frame: number;
}

export interface DescribeContext {
  redName: string;
  blueName: string;
  /** Only needed for prediction round markers ("Round N started/ended"). */
  rounds?: DescribeRound[];
  /** fights.red_fighter_id — resolves a prediction row's fighter_id to red/blue. */
  redFighterId?: number | null;
  /**
   * This event's own frame falls inside a confirmed corner_swap span — see
   * FighterOverlay's cornerSwapSpans. Label rows only: predictions have no
   * swap correction available (no hand labels exist for an ai_labeled
   * fight), which is an accepted risk, not an oversight.
   */
  swapped?: boolean;
}

function nameForCorner(corner: number | null, ctx: DescribeContext): string | null {
  if (corner !== 0 && corner !== 1) return null;
  const resolved = ctx.swapped ? 1 - corner : corner;
  return resolved === 0 ? ctx.redName : ctx.blueName;
}

function nameForFighterId(fighterId: number | null, ctx: DescribeContext): string | null {
  if (fighterId == null) return null;
  return fighterId === ctx.redFighterId ? ctx.redName : ctx.blueName;
}

function describeLabel(e: Event, ctx: DescribeContext): string {
  if (e.action === 'fight_end') return e.description ?? 'Fight ended';
  if (!e.action) return e.description ?? '';
  const tool = ACTION_TO_TOOL[e.action];
  if (!tool) return e.description ?? e.action;
  const name = tool.needsFighter ? nameForCorner(e.corner, ctx) ?? '' : '';
  return tool.text(name, (e.target as Target | null) ?? undefined);
}

function outcomeSuffix(success: boolean | null): string {
  return success === true ? ' (landed)' : success === false ? ' (missed)' : ' (unconfirmed)';
}

const PUNCH_TEXT: Record<string, string> = { jab: 'jab', cross: 'cross', hook: 'hook', uppercut: 'uppercut' };
const KICK_TEXT: Record<string, string> = {
  head_kick: 'kicks to the head', middle_kick: 'kicks to the body', low_kick: 'kicks to the leg',
};
const OPEN_RANGE_PUNCH_RE = /^(jab|cross|hook|uppercut)_(head|body)$/;

function describePrediction(e: Event, ctx: DescribeContext): string {
  const { action } = e;
  if (!action) return e.state ? `Fight state → ${e.state}` : (e.description ?? '');

  if (action === 'round_start' || action === 'round_end') {
    const round = ctx.rounds?.find(r =>
      action === 'round_start' ? r.start_frame === e.frame : r.end_frame === e.frame,
    );
    const label = round ? `Round ${round.round_number}` : 'Round';
    return `${label} ${action === 'round_start' ? 'started' : 'ended'}`;
  }

  const name = nameForFighterId(e.fighter_id, ctx) ?? 'Fighter';
  if (action === 'takedown_initiated') return `${name} lands a takedown`;
  if (action === 'clinch_initiated') return `${name} initiates a clinch`;
  if (action === 'clinch_punch') return `${name} punches in the clinch`;
  if (action === 'clinch_knee') return `${name} knees in the clinch`;
  if (action === 'ground_punch') return `${name} lands ground and pound`;
  if (action === 'ground_knee') return `${name} knees from the ground`;
  if (action in KICK_TEXT) return `${name} ${KICK_TEXT[action]}${outcomeSuffix(e.success)}`;

  const m = OPEN_RANGE_PUNCH_RE.exec(action);
  if (m) {
    const [, type, target] = m;
    return `${name} ${PUNCH_TEXT[type]} to the ${target}${outcomeSuffix(e.success)}`;
  }

  return e.description ?? action;
}

export function describeEvent(e: Event, ctx: DescribeContext): string {
  if (e.kind !== 'point') return e.description ?? '';
  return e.source === 'label' ? describeLabel(e, ctx) : describePrediction(e, ctx);
}
