import { ACTION_TO_TOOL, successForAction, TOOL_GROUPS, type Target } from '../components/annotate/taxonomy';

/**
 * The subset of Annotate's palette that is actually a training class with a
 * reviewable clip: `needsFighter` point events minus takedown_attempt/
 * takedown_defended/submission_attempt/knockdown (captured but never
 * exported — see ai/eval/README.md's reference table) and every
 * `state_*` mark (a change point, not a per-event clip). Grouping mirrors
 * `TOOL_GROUPS` so this reads the same as the Annotate palette.
 */
export interface TrainingClass {
  action: string;
  name: string;
  group: string;
}

const NOT_A_CLASS = new Set([
  'takedown_attempt',
  'takedown_defended',
  'submission_attempt',
  'knockdown',
]);

export const TRAINING_CLASSES: TrainingClass[] = TOOL_GROUPS.flatMap((g) =>
  g.items
    .filter((it) => it.needsFighter && !NOT_A_CLASS.has(it.action))
    .map((it) => ({ action: it.action, name: it.name, group: g.group })),
);

export const TRAINING_ACTIONS = new Set(TRAINING_CLASSES.map((c) => c.action));

export const CLASS_BY_ACTION: Record<string, TrainingClass> =
  Object.fromEntries(TRAINING_CLASSES.map((c) => [c.action, c]));

/**
 * What `target`/`success` should become when a Training Data QA reviewer
 * retypes an event to `newAction` (EventReview's "Type" dropdown) — mirrors
 * what Annotate's own palette derives the moment a tool is first pressed
 * (`logTool()` in Annotate.tsx): a `fixedTarget` class always takes its own
 * fixed target, a `hasTarget` class keeps whatever head/body target the
 * event already had (defaulting to head), everything else has no target.
 * `success` is always `successForAction(newAction)`, same as a fresh label —
 * this is what keeps e.g. a retyped `takedown_landed` from silently ending
 * up with `success=null`, which nothing else in the app ever produces.
 */
export function reclassifyPayload(
  newAction: string,
  currentTarget: string | null,
): { action: string; target: Target | null; success: boolean | null } {
  const tool = ACTION_TO_TOOL[newAction];
  const target: Target | null = tool?.fixedTarget
    ? tool.fixedTarget
    : tool?.hasTarget
      ? (currentTarget === 'body' ? 'body' : 'head')
      : null;
  return { action: newAction, target, success: successForAction(newAction) };
}
