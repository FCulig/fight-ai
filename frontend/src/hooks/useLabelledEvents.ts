import { useCallback, useEffect, useState } from 'react';
import { fetchFights, fetchEvents, fetchRounds } from '../services/api';
import type { Fight } from '../types/Fight';
import type { Event } from '../types/Event';
import { isFrameSwapped } from '../utils/cornerSwap';

export interface LabelEvent extends Event {
  fight: Fight;
  /** `corner`, swap-corrected the same way useTrainingDataEvents/describeEvent
   * do — the real fighter the strike came from, not the raw track slot. */
  displayCorner: 0 | 1 | null;
}

/**
 * Every hand-labelled point event (not just the reviewable training classes —
 * see useTrainingDataEvents for that narrower cross-fight view) across every
 * `purpose='training_data'` fight, plus each fight's rounds (for labelled
 * minutes). Backs Training Lab's Section A (overview) and Section B
 * (annotated events) on the /accuracy page — built entirely from the same
 * `/fights/` + `/fights/{id}/events/` + `/fights/{id}/rounds/` endpoints
 * Player/Annotate/Training Data QA already use, no new backend surface.
 */
export const useLabelledEvents = () => {
  const [events, setEvents] = useState<LabelEvent[]>([]);
  const [fights, setFights] = useState<Fight[]>([]);
  const [roundMinutes, setRoundMinutes] = useState<Map<number, number>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchFights()
      .then(async (allFights) => {
        const labelled = allFights.filter(
          (f) => f.purpose === 'training_data'
            && (f.state === 'labeling_in_progress' || f.state === 'labeling_complete'),
        );
        setFights(labelled);
        const perFight = await Promise.all(
          labelled.map((f) =>
            Promise.all([
              fetchEvents(f.id, { source: 'label', kind: 'point' }),
              fetchEvents(f.id, { source: 'label', kind: 'corner_swap' }),
              fetchRounds(f.id),
            ]).then(([evs, swaps, rounds]) => {
              const spans = swaps.map((s) => ({ frame: s.frame, end_frame: s.end_frame }));
              const minutes = rounds.reduce((sum, r) => sum + (r.end_frame - r.start_frame + 1), 0) / f.fps / 60;
              const tagged = evs.map((e) => ({
                ...e,
                fight: f,
                displayCorner: (e.corner != null && isFrameSwapped(e.frame, spans)
                  ? 1 - e.corner
                  : e.corner) as 0 | 1 | null,
              }));
              return { fightId: f.id, minutes, tagged };
            }),
          ),
        );
        setEvents(perFight.flatMap((p) => p.tagged));
        setRoundMinutes(new Map(perFight.map((p) => [p.fightId, p.minutes])));
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unknown error'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  return { events, fights, roundMinutes, loading, error, refetch: load };
};
