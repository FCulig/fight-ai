import type { EvalReport } from '../../types/EvalRun';
import StatusBadge from './StatusBadge';

interface ClassificationBreakdownProps {
  strikes: EvalReport['strikes'];
}

const pct = (n: number, d: number) => (d > 0 ? `${((n / d) * 100).toFixed(1)}%` : null);

function Tile({ label, value, sub, status }: { label: string; value: React.ReactNode; sub: string; status?: 'none' }) {
  return (
    <div className="inner-tile" style={{ padding: '13px 15px', flex: 1, minWidth: 150 }}>
      <div className="label" style={{ marginBottom: 8 }}>{label}</div>
      {status ? (
        <StatusBadge status={status} size="sm">{value}</StatusBadge>
      ) : (
        <span className="font-num" style={{ fontSize: 24, lineHeight: 1, color: 'var(--text-primary)' }}>{value}</span>
      )}
      <div style={{ marginTop: 6, fontSize: 11.5, fontWeight: 400, color: 'var(--text-muted)' }}>{sub}</div>
    </div>
  );
}

/** Section E3 — classification accuracy over matched strikes only. */
export default function ClassificationBreakdown({ strikes }: ClassificationBreakdownProps) {
  const familyPct = pct(strikes.family_correct, strikes.family_total);
  const targetPct = pct(strikes.target_correct, strikes.target_total);
  const cornerPct = pct(strikes.fighter_correct, strikes.fighter_total);

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
        <Tile label="Strike family" value={familyPct ?? 'Not measurable'} sub={`${strikes.family_total} specific matches`} status={familyPct ? undefined : 'none'} />
        <Tile label="Target zone" value={targetPct ?? 'Not measurable'} sub={`${strikes.target_total} specific matches`} status={targetPct ? undefined : 'none'} />
        <Tile label="Landed vs missed" value="Not measurable" sub="labels deliberately record no outcome" status="none" />
        <Tile label="Grappling matches" value={strikes.nonspecific_matches} sub="non-specific — detection only" />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <StatusBadge status="circular" title="The labeller reads the corner off the pipeline's own overlay, so a tracker swap is copied into the label and cancels out.">Circular</StatusBadge>
        <span style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-tertiary)' }}>
          Corner read-back {cornerPct ?? '—'} ({strikes.fighter_total} matches) — not attribution accuracy.
          Use corner-swap spans instead.
        </span>
      </div>
    </div>
  );
}
