import { useState, useEffect } from 'react';
import { fetchEvents, fetchFightEvents } from '../services/api';
import type { Event } from '../types/Event';

export const useEvents = (fightId?: number | null) => {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setEvents([]);
    const load = fightId != null ? fetchFightEvents(fightId) : fetchEvents();
    load
      .then(setEvents)
      .catch(err => setError(err instanceof Error ? err.message : 'An unknown error occurred'))
      .finally(() => setLoading(false));
  }, [fightId]);

  return { events, loading, error };
};
