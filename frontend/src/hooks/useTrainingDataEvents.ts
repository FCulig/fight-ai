import { useState, useEffect, useCallback } from 'react';
import { fetchFights, fetchEvents, verifyEvent, reclassifyEvent } from '../services/api';
import type { Fight } from '../types/Fight';
import type { Event } from '../types/Event';
import { TRAINING_ACTIONS } from '../utils/trainingDataTaxonomy';
import { isFrameSwapped } from '../utils/cornerSwap';

export interface QAEvent extends Event {
  fight: Fight;
  /**
   * `corner`, flipped for display if this event's frame falls inside one of
   * its fight's confirmed `corner_swap` spans — same display-only correction
   * FighterOverlay/describeEvent apply elsewhere. `corner` itself stays the
   * raw label track-slot (see label-events-corner-is-box-not-person) and is
   * what still gets passed to ClipPlayer/FighterOverlay's `highlightCorner`,
   * since that matches against `fighter_frames.corner`, which lives in the
   * same unswapped slot space. `displayCorner` is for showing the reviewer
   * which corner actually threw the strike — text/colour only.
   */
  displayCorner: 0 | 1 | null;
}

/**
 * Every reviewable hand-labelled point event across every `training_data`
 * fight — Training Data QA is cross-fight, unlike Player/Annotate which
 * scope to one `fightId`. Scoped to `purpose === 'training_data'`
 * specifically, not just "not ai_labeled": `reference` fights are hand-
 * labelled too (they're what the Accuracy page scores predictions against),
 * but that ground truth is held out on purpose — it must never leak into
 * what QA reviews confirm/decline for training, so a `reference` fight's
 * events must never appear here even though they're real `source='label'`
 * rows exactly like a `training_data` fight's.
 */
export const useTrainingDataEvents = () => {
  const [events, setEvents] = useState<QAEvent[]>([]);
  const [fights, setFights] = useState<Fight[]>([]);
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
            ]).then(([evs, swaps]) => {
              const spans = swaps.map((s) => ({ frame: s.frame, end_frame: s.end_frame }));
              return evs
                .filter((e) => TRAINING_ACTIONS.has(e.action ?? ''))
                .map((e) => ({
                  ...e,
                  fight: f,
                  displayCorner: (e.corner != null && isFrameSwapped(e.frame, spans)
                    ? 1 - e.corner
                    : e.corner) as 0 | 1 | null,
                }));
            }),
          ),
        );
        setEvents(perFight.flat());
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unknown error'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const setVerdict = useCallback((eventId: number, fightId: number, isVerified: boolean | null) => {
    setEvents((prev) => prev.map((e) => (e.id === eventId ? { ...e, is_verified: isVerified } : e)));
    verifyEvent(fightId, eventId, isVerified).catch(() => {
      // Roll back to the server's actual state on failure.
      load();
    });
  }, [load]);

  // Retypes a mislabelled strike (EventReview's "Type" dropdown). Persists
  // immediately — same optimistic-update-then-rollback-on-failure shape as
  // setVerdict — and, since it's a real fight_events write, is exactly what
  // Player/Annotate read back the next time either opens this fight: nothing
  // else needs to be told the type changed (see describeEvent.ts).
  const reclassify = useCallback((
    eventId: number, fightId: number, action: string, target: string | null, success: boolean | null,
  ): Promise<void> => {
    setEvents((prev) => prev.map((e) => (e.id === eventId ? { ...e, action, target, success } : e)));
    return reclassifyEvent(fightId, eventId, { action, target, success }).then(
      () => undefined,
      (err) => {
        // Roll back to the server's actual state on failure.
        load();
        throw err;
      },
    );
  }, [load]);

  return { events, fights, loading, error, setVerdict, reclassify, refetch: load };
};
