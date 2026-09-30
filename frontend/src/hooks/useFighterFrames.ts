import { useState, useEffect } from 'react';
import { fetchFighterFrames, type FetchFighterFramesParams } from '../services/api';
import type { FighterFrame } from '../types/FighterFrame';

/**
 * `range` narrows the fetch to a frame window instead of the whole fight —
 * pass it when the caller only ever draws a handful of frames (ClipPlayer's
 * ~0.6s clip); a full fight's keypoints run into the tens of MB (see
 * frontend/CLAUDE.md's `useFighterFrames` convention). Player/Annotate omit
 * it and keep fetching the whole fight, which they genuinely need for
 * free-scrub. Included in the effect's deps so a caller whose window moves
 * (ClipPlayer, as the reviewed event changes) refetches for the new range.
 */
export const useFighterFrames = (fightId: number | null, range?: FetchFighterFramesParams) => {
  const [frameMap, setFrameMap] = useState<Map<number, FighterFrame[]>>(new Map());
  const [loading, setLoading] = useState(false);
  const { start_frame, end_frame } = range ?? {};

  useEffect(() => {
    if (fightId == null) return;
    setLoading(true);
    fetchFighterFrames(fightId, { start_frame, end_frame })
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
  }, [fightId, start_frame, end_frame]);

  return { frameMap, loading };
};
