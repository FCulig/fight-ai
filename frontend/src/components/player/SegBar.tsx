interface Part {
  val: number;
  color: string;
  label: string;
}

interface SegBarProps {
  parts: Part[];
  total?: number;
}

export default function SegBar({ parts, total }: SegBarProps) {
  const t = total ?? (parts.reduce((s, p) => s + p.val, 0) || 1);
  return (
    <div>
      <div style={{ display: 'flex', gap: 2, height: 8, borderRadius: 2, overflow: 'hidden' }}>
        {parts.map((p, i) => (
          <div key={i} style={{ width: `${p.val / t * 100}%`, background: p.color, borderRadius: 2 }} title={p.label} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 14, marginTop: 8, flexWrap: 'wrap' as const }}>
        {parts.map((p, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--text-tertiary)', fontWeight: 500 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: p.color }} />
            {p.label}
            <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--mono)', fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>{p.val}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
