import { TOOL_GROUPS, colorForAction, iconForAction, type ToolItem } from './taxonomy';

interface EventPaletteProps {
  selected: boolean;
  onLog: (item: ToolItem) => void;
  onFightEnd: () => void;
}

export default function EventPalette({ selected, onLog, onFightEnd }: EventPaletteProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {TOOL_GROUPS.map(g => (
        <div key={g.group}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 9 }}>
            <div className="label" style={{ fontSize: 9.5 }}>{g.group}</div>
            {g.note && <div style={{ fontSize: 10, color: 'var(--text-disabled)', fontWeight: 600 }}>{g.note}</div>}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 8 }}>
            {g.items.map(it => {
              const c = colorForAction(it.action);
              const blocked = it.needsFighter && !selected;
              return (
                <button
                  key={it.key}
                  onClick={e => { e.currentTarget.blur(); onLog(it); }}
                  title={blocked ? 'Select a fighter first' : it.name}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 9, padding: '9px 11px', borderRadius: 10,
                    cursor: 'pointer', textAlign: 'left', border: '1px solid var(--border-subtle)',
                    background: 'var(--surface-inner)', borderLeft: `3px solid ${c}`,
                    opacity: blocked ? 0.42 : 1, transition: 'transform .1s,opacity .12s',
                    fontFamily: 'inherit',
                  }}
                >
                  {it.num ? (
                    <span className="punch-num" style={{ color: c, borderColor: `color-mix(in srgb, ${c} 45%, transparent)`, background: `color-mix(in srgb, ${c} 14%, transparent)` }}>{it.num}</span>
                  ) : (
                    <span className="kbd">{it.key.toUpperCase()}</span>
                  )}
                  <span className="material-symbols-outlined" style={{ fontSize: 18, color: c }}>{iconForAction(it.action)}</span>
                  <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-secondary)', lineHeight: 1.1 }}>{it.name}</span>
                </button>
              );
            })}
          </div>
        </div>
      ))}

      <div>
        <div className="label" style={{ fontSize: 9.5, marginBottom: 9 }}>Fight result</div>
        <button
          onClick={onFightEnd}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            padding: '11px 8px', borderRadius: 10, cursor: 'pointer', fontWeight: 700, fontSize: 12.5,
            border: '1px solid color-mix(in srgb, var(--purple-600) 40%, transparent)',
            background: 'color-mix(in srgb, var(--purple-600) 10%, transparent)',
            color: 'var(--text-primary)', fontFamily: 'inherit',
          }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--purple-600)' }}>sports_score</span>
          End of fight
        </button>
      </div>
    </div>
  );
}
