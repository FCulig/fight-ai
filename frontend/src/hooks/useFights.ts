import { useState, useEffect } from 'react';
import { fetchFights } from '../services/api';
import type { Fight } from '../types/Fight';

export const useFights = () => {
  const [fights, setFights] = useState<Fight[]>([]);
  const [selectedFightId, setSelectedFightId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFights()
      .then(data => {
        setFights(data);
        if (data.length > 0) setSelectedFightId(data[data.length - 1].id);
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Unknown error'))
      .finally(() => setLoading(false));
  }, []);

  const selectedFight = fights.find(f => f.id === selectedFightId) ?? null;

  return { fights, selectedFight, selectedFightId, setSelectedFightId, loading, error };
};
