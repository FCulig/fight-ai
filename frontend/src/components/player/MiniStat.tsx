interface MiniStatProps {
  value: string | number;
  label: string;
}

export default function MiniStat({ value, label }: MiniStatProps) {
  return (
    <div className="inner-tile" style={{ padding: '12px 14px', flex: 1 }}>
      <div className="font-display" style={{ fontSize: 26, lineHeight: 1, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
      <div className="label" style={{ marginTop: 5, fontSize: 9.5 }}>{label}</div>
    </div>
  );
}
