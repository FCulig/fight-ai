interface AccGaugeProps {
  pct: number;
  color: string;
  label: string;
}

export default function AccGauge({ pct, color, label }: AccGaugeProps) {
  const r = 26, c = 2 * Math.PI * r;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
      <div style={{ position: 'relative', width: 64, height: 64 }}>
        <svg width="64" height="64" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="32" cy="32" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
          <circle cx="32" cy="32" r={r} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
            strokeDasharray={`${pct / 100 * c} ${c}`} />
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
          <span style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary)' }}>{pct}%</span>
        </div>
      </div>
      <span style={{ fontSize: 10.5, color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' as const }}>{label}</span>
    </div>
  );
}
