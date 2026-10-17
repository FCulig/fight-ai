import type { Event } from '../types/Event';

export type FightStateName = 'STRIKING' | 'CLINCH' | 'GROUND';

const STATE_BY_ACTION: Record<string, FightStateName> = {
  state_striking: 'STRIKING',
  state_clinch: 'CLINCH',
  state_ground: 'GROUND',
};

export interface StateMark {
  frame: number;
  state: FightStateName;
}

/** A fight's hand-labelled state marks (W/F/G) in frame order. Each one runs
 * until the next, the same pairing as AnnotationTimeline's State lane. */
export function labelStateMarks(events: Event[]): StateMark[] {
  return events
    .filter(e => e.source === 'label' && e.kind === 'point' && e.action != null && STATE_BY_ACTION[e.action] != null)
    .map(e => ({ frame: e.frame, state: STATE_BY_ACTION[e.action as string] }))
    .sort((a, b) => a.frame - b.frame);
}

/** The labelled fight state at `frame`, or null before the first mark. */
export function labelStateAt(frame: number, marks: StateMark[]): FightStateName | null {
  let state: FightStateName | null = null;
  for (const m of marks) {
    if (m.frame > frame) break;
    state = m.state;
  }
  return state;
}
