import { useState, useEffect } from 'react';
import { fetchRounds } from '../services/api';
import type { Round } from '../types/Round';

export const useRounds = (fightId: number | null) => {
  const [rounds, setRounds] = useState<Round[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (fightId == null) return;
    setLoading(true);
    fetchRounds(fightId)
      .then(setRounds)
      .finally(() => setLoading(false));
  }, [fightId]);

  return { rounds, loading };
};
