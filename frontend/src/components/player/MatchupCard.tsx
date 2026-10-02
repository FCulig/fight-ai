import { useWindowWidth } from '../../hooks/useWindowWidth';
import type { FighterProfile } from '../../mocks/fightMock';
import { EdgeRow } from './EdgeMeter';
import type { EdgeTape } from './EdgeMeter';
import FormList from './RecentForm';

interface MatchupCardProps {
  fighters: { red: FighterProfile; blue: FighterProfile };
}

export default function MatchupCard({ fighters }: MatchupCardProps) {
  const width = useWindowWidth();
  const narrow = width < 1100;
  const r = fighters.red, b = fighters.blue;

  const EDGE_TAPE: EdgeTape[] = [
    { label: 'Height', r: r.height, b: b.height },
    { label: 'Reach',  r: r.reach,  b: b.reach  },
    { label: 'Age',    r: r.age,    b: b.age,    lowerWins: true },
  ];

  return (
    <div className="glass" style={{ marginTop: 16, padding: '22px 24px' }}>
      {/* Tale of the tape header */}
      <div style={{ display: 'grid', gridTemplateColumns: narrow ? '1fr' : '1fr auto 1fr', gap: 0, alignItems: 'center' }}>
        <div style={{ textAlign: narrow ? 'center' : 'left' }}>
          <div className="font-display" style={{ fontSize: 40, lineHeight: 0.95, color: 'var(--text-primary)', borderLeft: narrow ? 'none' : `3px solid ${r.color}`, paddingLeft: narrow ? 0 : 12 }}>{r.name}</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 500, marginTop: 4 }}>
            {r.first} · {r.country} · {r.record}
          </div>
        </div>
        {!narrow && (
          <div style={{ padding: '0 34px', textAlign: 'center' }}>
            <div className="font-display" style={{ fontSize: 24, color: 'var(--text-disabled)' }}>vs</div>
          </div>
        )}
        <div style={{ textAlign: narrow ? 'center' : 'right', marginTop: narrow ? 12 : 0 }}>
          <div className="font-display" style={{ fontSize: 40, lineHeight: 0.95, color: 'var(--text-primary)', borderRight: narrow ? 'none' : `3px solid ${b.color}`, paddingRight: narrow ? 0 : 12 }}>{b.name}</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 500, marginTop: 4 }}>
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
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-disabled)', whiteSpace: 'nowrap' }}>
          Recent form · last 5
        </span>
        <hr className="divider" style={{ flex: 1 }} />
      </div>

      {/* Recent form lists */}
      <div style={{ display: 'grid', gridTemplateColumns: narrow ? 'minmax(0, 1fr)' : '1fr auto 1fr', alignItems: 'flex-start', gap: narrow ? 24 : 20 }}>
        <FormList name={r.name} color={r.color} form={r.form} align={narrow ? 'left' : 'left'} />
        {!narrow && <span style={{ width: 1 }} />}
        <FormList name={b.name} color={b.color} form={b.form} align={narrow ? 'left' : 'right'} />
      </div>
    </div>
  );
}
