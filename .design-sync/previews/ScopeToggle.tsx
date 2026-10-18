import { useState } from 'react';
import { ScopeToggle } from 'fightlytics';

const rounds = [1, 2, 3].map(n => ({ id: n, fight_id: 1, round_number: n, start_frame: (n - 1) * 9000 + 1, end_frame: n * 9000 }));

function Demo({ initial }: { initial: 'fight' | 'live' | number }) {
  const [scope, setScope] = useState(initial);
  return <ScopeToggle scope={scope} setScope={setScope} rounds={rounds} />;
}

export const WholeFight = () => <Demo initial="fight" />;
export const Live = () => <Demo initial="live" />;
export const RoundSelected = () => <Demo initial={2} />;
