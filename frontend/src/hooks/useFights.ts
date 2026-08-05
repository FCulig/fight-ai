import { useState, useEffect, useCallback } from 'react';
import { fetchFights } from '../services/api';
import type { Fight } from '../types/Fight';

export const useFights = () => {
  const [fights, setFights] = useState<Fight[]>([]);
  const [selectedFightId, setSelectedFightId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchFights()
      .then(data => {
        setFights(data);
        setSelectedFightId(prev => {
          if (prev !== null && data.some(f => f.id === prev)) return prev;
          return data.length > 0 ? data[data.length - 1].id : null;
        });
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Unknown error'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const selectedFight = fights.find(f => f.id === selectedFightId) ?? null;

  return { fights, setFights, selectedFight, selectedFightId, setSelectedFightId, loading, error, refetch: load };
};
