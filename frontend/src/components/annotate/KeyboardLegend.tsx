import { TOOL_GROUPS, PLAYBACK_KEYS, EDIT_KEYS, SPAN_KEYS } from './taxonomy';

function KeyRow({ k, label }: { k: string[]; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '5px 0' }}>
      <span style={{ display: 'flex', gap: 4, minWidth: 78 }}>
        {k.map((x, i) => <span key={i} className="kbd">{x}</span>)}
      </span>
      <span style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 600 }}>{label}</span>
    </div>
  );
}

export default function KeyboardLegend() {
  return (
    <div className="glass" style={{ padding: '18px 22px', borderRadius: 14, marginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 14 }}>
        <span className="material-symbols-outlined" style={{ fontSize: 18, color: 'var(--accent)' }}>keyboard</span>
        <span className="font-display" style={{ fontSize: 20, letterSpacing: '0.03em', color: 'var(--text-primary)' }}>KEYBOARD SHORTCUTS</span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>Select a fighter (R / B), then press an event key</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1.4fr', gap: '4px 28px' }}>
        <div>
          <div className="label" style={{ fontSize: 9, marginBottom: 6 }}>Playback</div>
          {PLAYBACK_KEYS.map((r, i) => <KeyRow key={i} k={r.k} label={r.label} />)}
        </div>
        <div>
          <div className="label" style={{ fontSize: 9, marginBottom: 6 }}>Selection & edit</div>
          {EDIT_KEYS.map((r, i) => <KeyRow key={i} k={r.k} label={r.label} />)}
          <div className="label" style={{ fontSize: 9, margin: '10px 0 6px' }}>Spans</div>
          {SPAN_KEYS.map((r, i) => <KeyRow key={i} k={r.k} label={r.label} />)}
        </div>
        <div>
          <div className="label" style={{ fontSize: 9, marginBottom: 6 }}>Log event</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 18px' }}>
            {TOOL_GROUPS.flatMap(g => g.items).map(it => (
              <div key={it.key} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0' }}>
                <span className="kbd">{it.key.toUpperCase()}</span>
                <span style={{ fontSize: 11.5, color: 'var(--text-tertiary)', fontWeight: 600 }}>{it.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
