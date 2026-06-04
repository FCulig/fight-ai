export type Scope = 'fight' | 1 | 2;

interface ScopeToggleProps {
  scope: Scope;
  setScope: (s: Scope) => void;
}

const OPTS: [Scope, string][] = [['fight', 'Whole Fight'], [1, 'Round 1'], [2, 'Round 2']];

export default function ScopeToggle({ scope, setScope }: ScopeToggleProps) {
  return (
    <div style={{ display: 'inline-flex', gap: 4, background: 'var(--surface-inner)', padding: 4, borderRadius: 9, border: '1px solid var(--border-subtle)' }}>
      {OPTS.map(([k, l]) => (
        <button key={String(k)} onClick={() => setScope(k)} className={'pill' + (scope === k ? ' active' : '')} style={{ borderRadius: 6 }}>
          {l}
        </button>
      ))}
    </div>
  );
}
