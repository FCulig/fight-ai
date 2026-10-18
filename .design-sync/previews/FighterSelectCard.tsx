import { useState } from 'react';
import { FighterSelectCard } from 'fightlytics';

function Demo({ initial, hint = false }: { initial: 'red' | 'blue' | null; hint?: boolean }) {
  const [sel, setSel] = useState(initial);
  return (
    <div style={{ width: 380 }}>
      <FighterSelectCard selected={sel} onSelect={c => setSel(s => (s === c ? null : c))} redName="Adesanya" blueName="Pereira" hint={hint} />
    </div>
  );
}

export const RedSelected = () => <Demo initial="red" />;
export const NoneSelected = () => <Demo initial={null} />;
export const BlueSelected = () => <Demo initial="blue" />;
