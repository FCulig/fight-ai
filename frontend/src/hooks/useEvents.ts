import { useState, useEffect } from 'react';
import { fetchEvents, type FetchEventsParams } from '../services/api';
import type { Event } from '../types/Event';

export const useEvents = (fightId?: number | null, params?: FetchEventsParams) => {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // `params` is typically passed as an inline object literal, so it's a new
  // reference every render — serialize it for the effect's dependency so we
  // only refetch when its actual contents change, not its identity.
  const paramsKey = JSON.stringify(params ?? {});

  useEffect(() => {
    if (fightId == null) {
      setEvents([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setEvents([]);
    fetchEvents(fightId, params)
      .then(setEvents)
      .catch(err => setError(err instanceof Error ? err.message : 'An unknown error occurred'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fightId, paramsKey]);

  return { events, setEvents, loading, error };
};
