import { versionLabel } from '../../types/EvalRun';
import type { EvalRunSummary } from '../../types/EvalRun';
import StatusBadge from './StatusBadge';

interface ChangeTileProps {
  current: EvalRunSummary;
  previous: EvalRunSummary | null;
}

/**
 * F1 delta vs the preceding pipeline version for this fixture. Greys out
 * (rather than colouring green/red) whenever the two runs aren't honestly
 * comparable — different tolerance, or the matching constants changed —
 * per the design brief's honesty rule 8.
 */
export default function ChangeTile({ current, previous }: ChangeTileProps) {
  if (!previous) {
    return (
      <div className="inner-tile" style={{ padding: '13px 15px', flex: 1, minWidth: 160 }}>
        <div className="label" style={{ marginBottom: 9 }}>Change</div>
        <StatusBadge status="none" size="sm">First pipeline version — nothing to compare</StatusBadge>
      </div>
    );
  }

  const comparable = previous.tolerance_frames === current.tolerance_frames;
  const constantsChanged = previous.constants_sha256 !== current.constants_sha256;
  const delta = (current.f1 ?? 0) - (previous.f1 ?? 0);
  const deltaColor = !comparable
    ? 'var(--text-tertiary)'
    : delta > 0 ? '#0ca30c' : delta < 0 ? 'var(--red-500)' : 'var(--text-tertiary)';

  return (
    <div className="inner-tile" style={{ padding: '13px 15px', flex: 1, minWidth: 160 }}>
      <div className="label" style={{ marginBottom: 9 }}>Change</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{ fontSize: 20, fontWeight: 800, fontVariantNumeric: 'tabular-nums', color: deltaColor }}>
          {delta > 0 ? '+' : ''}{delta.toFixed(1)} pts
        </span>
        <span style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--text-muted)' }}>vs {versionLabel(previous)}</span>
      </div>
      {!comparable && (
        <div style={{ marginTop: 6, fontSize: 10, fontWeight: 600, color: '#fab219' }}>
          Tolerance changed (±{previous.tolerance_frames}f → ±{current.tolerance_frames}f) — not strictly comparable.
        </div>
      )}
      {comparable && constantsChanged && (
        <div style={{ marginTop: 6, fontSize: 10, fontWeight: 600, color: '#fab219' }}>
          Matching constants changed at this version — compare with care.
        </div>
      )}
    </div>
  );
}
