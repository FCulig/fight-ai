interface MiniStatProps {
  value: string | number;
  label: string;
}

export default function MiniStat({ value, label }: MiniStatProps) {
  return (
    <div className="inner-tile" style={{ padding: '12px 14px', flex: 1 }}>
      <div className="font-num" style={{ fontSize: 22, lineHeight: 1, color: 'var(--text-primary)' }}>
        {value}
      </div>
      <div className="label" style={{ marginTop: 6 }}>{label}</div>
    </div>
  );
}
