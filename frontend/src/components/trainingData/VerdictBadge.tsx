import { verdictKey, type Verdict } from '../../utils/trainingDataStats';

const VERDICT: Record<Verdict, { c: string; icon: string; t: string }> = {
  confirmed: { c: '#0ca30c', icon: 'check_circle', t: 'Confirmed' },
  declined: { c: '#ef4444', icon: 'cancel', t: 'Declined' },
  pending: { c: '#64748b', icon: 'schedule', t: 'Pending' },
};

interface VerdictBadgeProps {
  isVerified: boolean | null;
  sm?: boolean;
}

export default function VerdictBadge({ isVerified, sm }: VerdictBadgeProps) {
  const m = VERDICT[verdictKey(isVerified)];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap',
      padding: sm ? '2px 6px' : '3px 8px', borderRadius: 6,
      background: `color-mix(in srgb, ${m.c} 13%, transparent)`,
      border: `1px solid color-mix(in srgb, ${m.c} 26%, transparent)`,
      color: m.c, fontSize: sm ? 10 : 11, fontWeight: 700,
    }}>
      <span className="material-symbols-outlined" style={{ fontSize: sm ? 11 : 12 }}>{m.icon}</span>
      {m.t}
    </span>
  );
}
