import { useWindowWidth } from '../../hooks/useWindowWidth';
import { fighters } from '../../mocks/fightMock';
import { EdgeRow } from './EdgeMeter';
import type { EdgeTape } from './EdgeMeter';
import FormList from './RecentForm';

const EDGE_TAPE: EdgeTape[] = [
  { label: 'Height', r: fighters.red.height, b: fighters.blue.height },
  { label: 'Reach',  r: fighters.red.reach,  b: fighters.blue.reach  },
  { label: 'Age',    r: fighters.red.age,    b: fighters.blue.age,    lowerWins: true },
];

export default function MatchupCard() {
  const width = useWindowWidth();
  const narrow = width < 1100;
  const r = fighters.red, b = fighters.blue;

  return (
    <div className="glass" style={{ marginTop: 16, padding: '22px 24px' }}>
      {/* Tale of the tape header */}
      <div style={{ display: 'grid', gridTemplateColumns: narrow ? '1fr' : '1fr auto 1fr', gap: 0, alignItems: 'center' }}>
        <div style={{ textAlign: narrow ? 'center' : 'left' }}>
          <div className="font-display" style={{ fontSize: 46, lineHeight: 0.9, color: r.color }}>{r.name}</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 600, marginTop: 4 }}>
            {r.first} · {r.country} · {r.record}
          </div>
        </div>
        {!narrow && (
          <div style={{ padding: '0 34px', textAlign: 'center' }}>
            <div className="font-display" style={{ fontSize: 30, color: 'var(--text-disabled)' }}>VS</div>
          </div>
        )}
        <div style={{ textAlign: narrow ? 'center' : 'right', marginTop: narrow ? 12 : 0 }}>
          <div className="font-display" style={{ fontSize: 46, lineHeight: 0.9, color: b.color }}>{b.name}</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 600, marginTop: 4 }}>
            {b.first} · {b.country} · {b.record}
          </div>
        </div>
      </div>

      {/* Edge meters */}
      <div style={{ maxWidth: 600, margin: '24px auto 0' }}>
        {EDGE_TAPE.map((t, i) => <EdgeRow key={i} t={t} />)}
      </div>

      {/* Recent form divider */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '24px auto 16px', maxWidth: 560 }}>
        <hr className="divider" style={{ flex: 1 }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-disabled)', whiteSpace: 'nowrap' }}>
          Recent Form · Last 5
        </span>
        <hr className="divider" style={{ flex: 1 }} />
      </div>

      {/* Recent form lists */}
      <div style={{ display: 'grid', gridTemplateColumns: narrow ? '1fr' : '1fr auto 1fr', alignItems: 'flex-start', gap: narrow ? 24 : 20 }}>
        <FormList name={r.name} color={r.color} form={r.form} align={narrow ? 'left' : 'left'} />
        {!narrow && <span style={{ width: 1 }} />}
        <FormList name={b.name} color={b.color} form={b.form} align={narrow ? 'left' : 'right'} />
      </div>
    </div>
  );
}
