import { useState, useEffect } from 'react';
import { fetchFighterFrames } from '../services/api';
import type { FighterFrame } from '../types/FighterFrame';

export const useFighterFrames = (fightId: number | null) => {
  const [frameMap, setFrameMap] = useState<Map<number, FighterFrame[]>>(new Map());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (fightId == null) return;
    setLoading(true);
    fetchFighterFrames(fightId)
      .then(frames => {
        const map = new Map<number, FighterFrame[]>();
        for (const f of frames) {
          const bucket = map.get(f.frame);
          if (bucket) bucket.push(f);
          else map.set(f.frame, [f]);
        }
        setFrameMap(map);
      })
      .finally(() => setLoading(false));
  }, [fightId]);

  return { frameMap, loading };
};
