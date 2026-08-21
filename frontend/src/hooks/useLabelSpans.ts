import { useState, useEffect } from 'react';
import { fetchLabelSpans } from '../services/api';
import type { LabelSpan } from '../types/LabelSpan';

export const useLabelSpans = (fightId?: number | null) => {
  const [spans, setSpans] = useState<LabelSpan[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (fightId == null) {
      setSpans([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setSpans([]);
    fetchLabelSpans(fightId)
      .then(setSpans)
      .catch(err => setError(err instanceof Error ? err.message : 'An unknown error occurred'))
      .finally(() => setLoading(false));
  }, [fightId]);

  return { spans, setSpans, loading, error };
};
