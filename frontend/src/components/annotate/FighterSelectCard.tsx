import type { Corner } from './taxonomy';

interface FighterSelectCardProps {
  selected: Corner | null;
  onSelect: (corner: Corner) => void;
  redName: string;
  blueName: string;
  hint: boolean;
}

const CORNERS: { key: Corner; color: string; kbd: string }[] = [
  { key: 'red', color: 'var(--f-red)', kbd: 'R' },
  { key: 'blue', color: 'var(--f-blue)', kbd: 'B' },
];

export default function FighterSelectCard({ selected, onSelect, redName, blueName, hint }: FighterSelectCardProps) {
  const nameFor = (k: Corner) => (k === 'red' ? redName : blueName);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
      {CORNERS.map(c => {
        const sel = selected === c.key;
        return (
          <button
            key={c.key}
            className="fighter-corner-btn"
            onClick={() => onSelect(c.key)}
            style={{
              cursor: 'pointer', textAlign: 'left', padding: '12px 14px', borderRadius: 8,
              transition: 'none',
              border: `1.5px solid ${sel ? c.color : hint ? 'var(--text-primary)' : 'var(--border-glass)'}`,
              background: sel ? `color-mix(in srgb, ${c.color} 12%, transparent)` : 'var(--surface-inner)',
              animation: hint && !sel ? 'pulse-ring 1s ease-out 2' : 'none',
              fontFamily: 'inherit',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
              <span style={{ width: 10, height: 10, borderRadius: 2, background: c.color }} />
              <span className="font-display" style={{ fontSize: 22, color: 'var(--text-primary)', lineHeight: 1 }}>{nameFor(c.key)}</span>
              <span className="kbd" style={{ marginLeft: 'auto' }}>{c.kbd}</span>
            </div>
            <div style={{ marginTop: 5, fontSize: 11, fontWeight: 500, color: 'var(--text-muted)' }}>
              {c.key === 'red' ? 'Red corner' : 'Blue corner'}
            </div>
          </button>
        );
      })}
    </div>
  );
}
