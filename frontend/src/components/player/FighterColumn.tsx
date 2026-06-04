import AccGauge from './AccGauge';
import MiniStat from './MiniStat';
import SegBar from './SegBar';
import { fighters, ctrlFmt } from '../../mocks/fightMock';
import type { FighterStats } from '../../mocks/fightMock';

interface FighterColumnProps {
  corner: 'red' | 'blue';
  s: FighterStats;
}

export default function FighterColumn({ corner, s }: FighterColumnProps) {
  const f = fighters[corner];
  return (
    <div className="glass" style={{ padding: '22px 24px', borderTop: `2px solid ${f.color}`, boxShadow: `0 -1px 24px -10px ${f.color}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
        <span style={{ width: 14, height: 14, borderRadius: 4, background: f.color, boxShadow: `0 0 14px ${f.color}`, flexShrink: 0 }} />
        <div>
          <div className="font-display" style={{ fontSize: 38, lineHeight: 0.9, color: 'var(--text-primary)' }}>{f.name}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, marginTop: 2 }}>"{f.nick}" · {f.record} · {f.corner}</div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-end', marginBottom: 18 }}>
        <div>
          <div className="font-display" style={{ fontSize: 56, lineHeight: 0.85, color: f.color, fontVariantNumeric: 'tabular-nums' }}>
            {s.sig[0]}
          </div>
          <div className="label" style={{ marginTop: 4 }}>Sig. strikes · of {s.sig[1]}</div>
        </div>
        <div style={{ marginLeft: 'auto' }}>
          <AccGauge pct={s.acc} color={f.color} label="Accuracy" />
        </div>
      </div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
        <MiniStat value={`${s.td[0]}/${s.td[1]}`} label="Takedowns" />
        <MiniStat value={ctrlFmt(s.ctrl)} label="Control" />
        <MiniStat value={s.kd} label="Knockdowns" />
        <MiniStat value={s.sub} label="Sub Att" />
      </div>
      <div style={{ marginBottom: 16 }}>
        <div className="label" style={{ marginBottom: 9 }}>Strikes by target</div>
        <SegBar parts={[
          { val: s.head,     color: 'var(--accent)',      label: 'Head'     },
          { val: s.body,     color: 'var(--orange-400)',  label: 'Body'     },
          { val: s.leg,      color: 'var(--green-500)',   label: 'Leg'      },
        ]} />
      </div>
      <div>
        <div className="label" style={{ marginBottom: 9 }}>Strikes by position</div>
        <SegBar parts={[
          { val: s.distance, color: 'var(--cyan-400)',    label: 'Distance' },
          { val: s.clinch,   color: 'var(--purple-600)', label: 'Clinch'   },
          { val: s.ground,   color: 'var(--orange-400)', label: 'Ground'   },
        ]} />
      </div>
    </div>
  );
}
