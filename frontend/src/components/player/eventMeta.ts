export type EventCat = 'strike' | 'grapple' | 'state' | 'round' | 'event';

export function deriveEventCat(desc: string): EventCat {
  if (/\bround\b/i.test(desc)) return 'round';
  if (/punch|jab|cross|hook|uppercut|elbow|knee|strike|hit|landed|blocked|kick/i.test(desc)) return 'strike';
  if (/takedown|grapple|mount|guard|submission|sprawl/i.test(desc)) return 'grapple';
  if (/ground|clinch/i.test(desc)) return 'grapple';
  return 'state';
}

export function eventColor(cat: EventCat, sub?: string): string {
  if (cat === 'strike') return sub && /knockdown/i.test(sub) ? 'var(--f-red)' : 'var(--accent)';
  if (cat === 'grapple') return 'var(--orange-400)';
  if (cat === 'state')   return 'var(--slate-400)';
  if (cat === 'round')   return 'var(--green-500)';
  if (cat === 'event')   return 'var(--purple-600)';
  return 'var(--text-muted)';
}

export function eventIcon(cat: EventCat, sub?: string): string {
  if (cat === 'strike') return sub && /knockdown/i.test(sub) ? 'sports_mma' : 'bolt';
  if (cat === 'grapple') return 'sports_kabaddi';
  if (cat === 'state')   return 'change_circle';
  if (cat === 'round')   return 'timer';
  if (cat === 'event')   return 'crisis_alert';
  return 'radio_button_checked';
}
