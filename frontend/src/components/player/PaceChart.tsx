interface PaceChartProps {
  time: number;
  duration: number;
  r1End: number;
  height?: number;
  redPace: number[];
  bluePace: number[];
}

export default function PaceChart({ time, duration, r1End, height = 150, redPace, bluePace }: PaceChartProps) {
  const W = 900, H = height, padB = 22, padT = 12;
  const n = redPace.length;
  if (n < 2) return null;

  const maxY = Math.max(4, ...redPace, ...bluePace);
  const x = (i: number) => (i / (n - 1)) * W;
  const y = (v: number) => H - padB - (v / maxY) * (H - padB - padT);
  const line = (arr: number[]) =>
    arr.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const area = (arr: number[]) => `${line(arr)} L${W},${H - padB} L0,${H - padB} Z`;
  const r1x = duration > 0 ? (r1End / duration) * W : W / 2;
  const nowx = duration > 0 ? Math.min((time / duration) * W, W) : 0;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={height} preserveAspectRatio="none" style={{ display: 'block', overflow: 'visible' }}>
      <defs>
        <linearGradient id="pg-red" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--f-red)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="var(--f-red)" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="pg-blue" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--f-blue)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="var(--f-blue)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <line x1={r1x} y1={padT - 4} x2={r1x} y2={H - padB} stroke="var(--green-500)" strokeOpacity="0.4" strokeDasharray="4 4" />
      <text x={6} y={padT + 4} fill="var(--text-disabled)" fontSize="10" fontWeight="700">R1</text>
      <text x={r1x + 6} y={padT + 4} fill="var(--text-disabled)" fontSize="10" fontWeight="700">R2</text>
      <path d={area(redPace)} fill="url(#pg-red)" />
      <path d={area(bluePace)} fill="url(#pg-blue)" />
      <path d={line(redPace)} fill="none" stroke="var(--f-red)" strokeWidth="2.5" />
      <path d={line(bluePace)} fill="none" stroke="var(--f-blue)" strokeWidth="2.5" />
      {duration > 0 && (
        <>
          <line x1={nowx} y1={padT - 4} x2={nowx} y2={H - padB} stroke="var(--accent)" strokeWidth="1.5" />
          <circle cx={nowx} cy={padT - 4} r="3" fill="var(--accent)" />
        </>
      )}
      <line x1="0" y1={H - padB} x2={W} y2={H - padB} stroke="rgba(255,255,255,0.08)" />
    </svg>
  );
}
