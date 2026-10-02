export type Status = 'good' | 'warning' | 'critical' | 'unverified' | 'none' | 'circular';

/**
 * Icon + text always paired, never colour alone — good/critical collapse for
 * red-green colourblindness, and critical's red is close to the red corner.
 * `good`/`warning` use their own hex rather than the app's `--green-500`/
 * `--red-500` tokens: those are already claimed by other meanings
 * (training_data purpose, round spans) — see memory "frontend-palette-collisions".
 */
const STATUS: Record<Status, { color: string; icon: string }> = {
  good: { color: '#0ca30c', icon: 'check_circle' },
  warning: { color: 'var(--warn)', icon: 'warning' },
  critical: { color: 'var(--red-500)', icon: 'error' },
  unverified: { color: 'var(--text-muted)', icon: 'help' },
  none: { color: 'var(--text-muted)', icon: 'remove' },
  circular: { color: '#b39dfb', icon: 'sync_problem' },
};

interface StatusBadgeProps {
  status: Status;
  children: React.ReactNode;
  size?: 'sm' | 'md';
  title?: string;
}

export default function StatusBadge({ status, children, size = 'md', title }: StatusBadgeProps) {
  const s = STATUS[status];
  const sm = size === 'sm';
  return (
    <span
      title={title}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: sm ? 4 : 5,
        flexShrink: 0,
        whiteSpace: 'nowrap',
        padding: sm ? '2px 6px 2px 5px' : '3px 8px 3px 6px',
        borderRadius: 6,
        background: `color-mix(in srgb, ${s.color} 13%, transparent)`,
        border: `1px solid color-mix(in srgb, ${s.color} 26%, transparent)`,
        color: s.color,
        fontSize: sm ? 11 : 12,
        fontWeight: 500,
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: sm ? 12 : 13 }}>{s.icon}</span>
      {children}
    </span>
  );
}
