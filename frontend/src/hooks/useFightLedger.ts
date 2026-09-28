import { useCallback, useEffect, useState } from 'react';
import { fetchFights, fetchEvents, fetchRounds } from '../services/api';
import type { Fight } from '../types/Fight';
import type { Event } from '../types/Event';
import type { Round } from '../types/Round';

export interface LedgerFight {
  fight: Fight;
  rounds: Round[];
  pointEvents: Event[]; // source='label', kind='point' — strikes + state marks + grappling/outcome
  swapEvents: Event[]; // kind='corner_swap'
  excludedEvents: Event[]; // kind='excluded'
  roundEvents: Event[]; // kind='round'
  minutes: number;
}

/**
 * Every fight — not scoped to `purpose='training_data'` like
 * useLabelledEvents/useTrainingDataEvents — with its rounds and every
 * source='label' event, for Training Lab's Section D (fights ledger).
 * Fetched eagerly for all fights rather than lazily per row: at today's scale
 * (a handful of fights) that's ~4 cheap requests per fight, and it keeps the
 * ledger's collapsed-row summary (strike/state/swap counts) available
 * without a spinner per expand. Revisit if the fight count grows into the
 * hundreds — see the fighter-frame payload-size note in this folder's
 * sibling hooks for the shape that problem takes.
 */
export const useFightLedger = () => {
  const [ledger, setLedger] = useState<LedgerFight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchFights()
      .then(async (fights) => {
        const rows = await Promise.all(
          fights.map(async (fight): Promise<LedgerFight> => {
            const [rounds, pointEvents, swapEvents, excludedEvents, roundEvents] = await Promise.all([
              fetchRounds(fight.id),
              fetchEvents(fight.id, { source: 'label', kind: 'point' }),
              fetchEvents(fight.id, { source: 'label', kind: 'corner_swap' }),
              fetchEvents(fight.id, { source: 'label', kind: 'excluded' }),
              fetchEvents(fight.id, { source: 'label', kind: 'round' }),
            ]);
            const minutes = rounds.reduce((sum, r) => sum + (r.end_frame - r.start_frame + 1), 0) / fight.fps / 60;
            return { fight, rounds, pointEvents, swapEvents, excludedEvents, roundEvents, minutes };
          }),
        );
        rows.sort((a, b) => a.fight.id - b.fight.id);
        setLedger(rows);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unknown error'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  return { ledger, loading, error, refetch: load };
};
