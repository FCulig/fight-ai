import type { Round } from '../../types/Round';

export type Scope = 'fight' | 'live' | number; // number = round_number from backend

interface ScopeToggleProps {
  scope: Scope;
  setScope: (s: Scope) => void;
  rounds: Round[];
}

export default function ScopeToggle({ scope, setScope, rounds }: ScopeToggleProps) {
  const sortedRounds = [...rounds].sort((a, b) => a.round_number - b.round_number);

  return (
    <div style={{ display: 'inline-flex', gap: 4, background: 'var(--surface-inner)', padding: 4, borderRadius: 9, border: '1px solid var(--border-subtle)' }}>
      <button key="fight" onClick={() => setScope('fight')} className={'pill' + (scope === 'fight' ? ' active' : '')} style={{ borderRadius: 6 }}>
        Whole Fight
      </button>

      <button key="live" onClick={() => setScope('live')} className={'pill' + (scope === 'live' ? ' active' : '')} style={{ borderRadius: 6, display: 'flex', alignItems: 'center', gap: 5 }}>
        {scope === 'live' && (
          <span style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: 'var(--accent)',
            display: 'inline-block',
            animation: 'scope-pulse 1.2s ease-in-out infinite',
            flexShrink: 0,
          }} />
        )}
        {scope !== 'live' && (
          <span style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: 'var(--text-muted)',
            display: 'inline-block',
            flexShrink: 0,
            opacity: 0.5,
          }} />
        )}
        Live
      </button>

      {sortedRounds.map(r => (
        <button
          key={r.round_number}
          onClick={() => setScope(r.round_number)}
          className={'pill' + (scope === r.round_number ? ' active' : '')}
          style={{ borderRadius: 6 }}
        >
          Round {r.round_number}
        </button>
      ))}
    </div>
  );
}
