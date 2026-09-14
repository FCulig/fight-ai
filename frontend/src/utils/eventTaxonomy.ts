// Shared action -> category/color/icon vocabulary, used by both the Player
// (predictions or labels, via LiveFeed) and Annotate (labels only). Driven
// entirely by the structured `action` column — never by regexing free text,
// since `description` is no longer populated for anything but `fight_end`.

export type EventCat = 'strike' | 'grapple' | 'state' | 'round' | 'event';

export function categoryForAction(action: string | null): EventCat {
  if (!action) return 'state';
  if (action === 'fight_end' || action === 'submission_attempt') return 'event';
  if (action.startsWith('takedown_') || action === 'clinch_initiated') return 'grapple';
  if (action.startsWith('state_')) return 'state';
  if (action.startsWith('round_')) return 'round';
  return 'strike';
}

export function colorForAction(action: string | null): string {
  if (!action) return 'var(--text-muted)';
  if (action === 'knockdown') return 'var(--f-red)';
  if (action === 'fight_end' || action === 'submission_attempt') return 'var(--purple-600)';
  if (action.startsWith('takedown_') || action === 'clinch_initiated') return 'var(--orange-400)';
  if (action.startsWith('state_')) return 'var(--slate-400)';
  if (action.startsWith('round_')) return 'var(--green-500)';
  return 'var(--accent)';
}

export function iconForAction(action: string | null): string {
  if (!action) return 'radio_button_checked';
  if (action === 'knockdown') return 'sports_mma';
  if (action === 'fight_end') return 'sports_score';
  if (action === 'submission_attempt') return 'crisis_alert';
  if (action.startsWith('takedown_') || action === 'clinch_initiated') return 'sports_kabaddi';
  if (action.startsWith('state_')) return 'change_circle';
  if (action.startsWith('round_')) return 'timer';
  return 'bolt';
}
