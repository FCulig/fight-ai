import type { FormResult } from '../../mocks/fightMock';

interface FormChipProps {
  fight: FormResult;
}

function FormChip({ fight }: FormChipProps) {
  const win = fight.r === 'W';
  const c = win ? 'var(--green-500)' : 'var(--f-red)';
  return (
    <div title={`${win ? 'Win' : 'Loss'} vs ${fight.o} · ${fight.m}`}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, width: 58 }}>
      <span style={{ width: 30, height: 30, borderRadius: 8, display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 13, color: c, background: `color-mix(in srgb, ${c} 15%, transparent)`, border: `1px solid color-mix(in srgb, ${c} 38%, transparent)` }}>
        {fight.r}
      </span>
      <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-secondary)', lineHeight: 1.12, textAlign: 'center', width: 58, minHeight: 24, display: 'flex', alignItems: 'flex-start', justifyContent: 'center' }}>
        {fight.o}
      </span>
      <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.04em', color: 'var(--text-muted)' }}>{fight.m}</span>
    </div>
  );
}

interface FormListProps {
  name: string;
  color: string;
  form: FormResult[];
  align: 'left' | 'right';
}

export default function FormList({ name, color, form, align }: FormListProps) {
  const right = align === 'right';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 11, alignItems: right ? 'flex-end' : 'flex-start' }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 7, flexDirection: right ? 'row-reverse' : 'row' }}>
        <span style={{ width: 9, height: 9, borderRadius: 2, background: color }} />
        <span style={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.02em', color: 'var(--text-primary)' }}>{name}</span>
      </span>
      <div style={{ display: 'flex', gap: 6, flexDirection: right ? 'row-reverse' : 'row' }}>
        {form.map((fight, i) => <FormChip key={i} fight={fight} />)}
      </div>
    </div>
  );
}
