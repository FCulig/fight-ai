import type { QAEvent } from '../hooks/useTrainingDataEvents';

export interface ClassStats {
  total: number;
  confirmed: number;
  declined: number;
  reviewed: number;
  pending: number;
}

export function classStats(events: QAEvent[]): ClassStats {
  let confirmed = 0;
  let declined = 0;
  events.forEach((e) => {
    if (e.is_verified === true) confirmed++;
    else if (e.is_verified === false) declined++;
  });
  return { total: events.length, confirmed, declined, reviewed: confirmed + declined, pending: events.length - confirmed - declined };
}

export type Verdict = 'confirmed' | 'declined' | 'pending';

export function verdictKey(isVerified: boolean | null): Verdict {
  if (isVerified === true) return 'confirmed';
  if (isVerified === false) return 'declined';
  return 'pending';
}
