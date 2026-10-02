import type { FightPurpose } from '../types/Fight';
import { PURPOSE_COLORS, PURPOSE_ICONS, PURPOSE_LABELS } from '../types/Fight';

interface FightPurposeBadgeProps {
  /** `Fight.purpose` — a raw string, so an unknown value degrades to a grey chip. */
  purpose: string;
  /** `sm` for the fight-list card subtitle, `md` for a page header. */
  size?: 'sm' | 'md';
}

const SIZES = {
  sm: { font: 11, icon: 13, pad: '1px 7px', radius: 5, gap: 4 },
  md: { font: 12, icon: 14, pad: '3px 9px', radius: 6, gap: 5 },
} as const;

export default function FightPurposeBadge({ purpose, size = 'md' }: FightPurposeBadgeProps) {
  const known = purpose in PURPOSE_LABELS ? (purpose as FightPurpose) : null;
  const color = known ? PURPOSE_COLORS[known] : 'var(--text-muted)';
  const label = known ? PURPOSE_LABELS[known] : purpose;
  const icon = known ? PURPOSE_ICONS[known] : 'help';
  const s = SIZES[size];

  return (
    <span
      title={`Purpose: ${label}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: s.gap,
        flexShrink: 0,
        fontSize: s.font,
        fontWeight: 500,
        whiteSpace: 'nowrap',
        padding: s.pad,
        borderRadius: s.radius,
        color,
        background: `color-mix(in srgb, ${color} 16%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 36%, transparent)`,
      }}
    >
      <span className="material-symbols-outlined" style={{ fontSize: s.icon }}>
        {icon}
      </span>
      {label}
    </span>
  );
}
