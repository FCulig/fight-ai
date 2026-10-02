import type { FormResult } from '../../mocks/fightMock';

interface FormChipProps {
  fight: FormResult;
}

function FormChip({ fight }: FormChipProps) {
  const win = fight.r === 'W';
  const c = win ? 'var(--green-500)' : 'var(--red-500)';
  return (
    <div title={`${win ? 'Win' : 'Loss'} vs ${fight.o} · ${fight.m}`}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, flex: '0 1 58px', minWidth: 0 }}>
      <span style={{ width: 30, height: 30, borderRadius: 6, display: 'grid', placeItems: 'center', fontFamily: 'var(--mono)', fontWeight: 600, fontSize: 13, color: c, background: `color-mix(in srgb, ${c} 15%, transparent)`, border: `1px solid color-mix(in srgb, ${c} 38%, transparent)` }}>
        {fight.r}
      </span>
      <span style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--text-secondary)', lineHeight: 1.12, textAlign: 'center', width: '100%', overflow: 'hidden', textOverflow: 'ellipsis', minHeight: 24, display: 'flex', alignItems: 'flex-start', justifyContent: 'center' }}>
        {fight.o}
      </span>
      <span style={{ fontSize: 10.5, fontWeight: 500, color: 'var(--text-muted)' }}>{fight.m}</span>
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 11, alignItems: right ? 'flex-end' : 'flex-start', minWidth: 0 }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 7, flexDirection: right ? 'row-reverse' : 'row' }}>
        <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
        <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-primary)' }}>{name}</span>
      </span>
      <div style={{ display: 'flex', gap: 6, flexDirection: right ? 'row-reverse' : 'row', minWidth: 0, maxWidth: '100%' }}>
        {form.map((fight, i) => <FormChip key={i} fight={fight} />)}
      </div>
    </div>
  );
}
