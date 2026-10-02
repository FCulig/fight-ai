interface OffsetDotStripProps {
  /** Signed (predicted - truth) frame offsets for every matched strike. */
  offsets: number[];
}

/** Section E5 — a dot strip of signed timing offsets, -N to +N frames around
 * a zero line, with bias (systematic lag, subtract once) and jitter (genuine
 * spread) called out separately. */
export default function OffsetDotStrip({ offsets }: OffsetDotStripProps) {
  if (offsets.length === 0) {
    return <div style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-muted)' }}>No matched strikes to time yet.</div>;
  }

  const sorted = [...offsets].sort((a, b) => a - b);
  const median = (arr: number[]) => {
    const mid = Math.floor(arr.length / 2);
    return arr.length % 2 ? arr[mid] : (arr[mid - 1] + arr[mid]) / 2;
  };
  const bias = median(sorted);
  const jitter = median(offsets.map((o) => Math.abs(o)).sort((a, b) => a - b));
  const bound = Math.max(12, ...offsets.map((o) => Math.abs(o)));

  const W = 480, H = 46, padX = 16;
  const x = (o: number) => padX + ((o + bound) / (bound * 2)) * (W - padX * 2);

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="xMidYMid meet" style={{ display: 'block' }}>
        <line x1={x(0)} x2={x(0)} y1={4} y2={H - 4} stroke="rgba(255,255,255,0.14)" strokeWidth="1" />
        {offsets.map((o, i) => {
          // Deterministic jitter (not Math.random()) so dots don't reshuffle on re-render.
          const jitterY = (((i * 2654435761) % 1000) / 1000 - 0.5) * 14;
          return (
            <circle key={i} cx={x(o)} cy={H / 2 + jitterY} r={2.5} fill="var(--cyan-400)" fillOpacity={0.55}>
              <title>{o > 0 ? '+' : ''}{o}f</title>
            </circle>
          );
        })}
      </svg>
      <div style={{ marginTop: 6, fontSize: 11.5, fontWeight: 600, color: 'var(--text-secondary)' }}>
        bias {bias > 0 ? '+' : ''}{bias.toFixed(1)}f (systematic lag) · jitter {jitter.toFixed(1)}f (spread)
      </div>
      <div style={{ marginTop: 2, fontSize: 10.5, fontWeight: 500, color: 'var(--text-muted)' }}>
        Bias is a constant to subtract once, not a reason to widen the tolerance.
      </div>
    </div>
  );
}
