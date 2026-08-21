import { useState, useEffect } from 'react';
import { fetchLabelEvents } from '../services/api';
import type { LabelEvent } from '../types/LabelEvent';

export const useLabelEvents = (fightId?: number | null) => {
  const [events, setEvents] = useState<LabelEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (fightId == null) {
      setEvents([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setEvents([]);
    fetchLabelEvents(fightId)
      .then(setEvents)
      .catch(err => setError(err instanceof Error ? err.message : 'An unknown error occurred'))
      .finally(() => setLoading(false));
  }, [fightId]);

  return { events, loading, error };
};
