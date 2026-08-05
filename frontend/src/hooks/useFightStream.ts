import { useEffect, useRef } from 'react';
import type { Fight } from '../types/Fight';

export function useFightStream(
  fights: Fight[],
  setFights: React.Dispatch<React.SetStateAction<Fight[]>>,
  enabled: boolean,
) {
  const setFightsRef = useRef(setFights);
  setFightsRef.current = setFights;

  useEffect(() => {
    if (!enabled) return;

    const es = new EventSource('/fights/stream');

    es.addEventListener('snapshot', (e: MessageEvent) => {
      const items: { id: number; state: string }[] = JSON.parse(e.data);
      setFightsRef.current(prev =>
        prev.map(f => {
          const update = items.find(u => u.id === f.id);
          return update ? { ...f, state: update.state } : f;
        }),
      );
    });

    es.onmessage = (e: MessageEvent) => {
      const update: { id: number; state: string } = JSON.parse(e.data);
      setFightsRef.current(prev =>
        prev.map(f => (f.id === update.id ? { ...f, state: update.state } : f)),
      );
    };

    return () => es.close();
  }, [enabled]);
}
