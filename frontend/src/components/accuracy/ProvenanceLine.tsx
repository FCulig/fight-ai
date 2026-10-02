import type { EvalRunSummary } from '../../types/EvalRun';

interface ProvenanceLineProps {
  run: EvalRunSummary;
}

/**
 * Every accuracy number on this page travels with this line — honesty rule
 * from the Training Lab design brief: no bare percentage without its n,
 * tolerance and pipeline version. Never omit this next to an F1/P/R figure.
 */
export default function ProvenanceLine({ run }: ProvenanceLineProps) {
  const labelled = (run.tp ?? 0) + (run.fn ?? 0);
  return (
    <div style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-muted)', display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
      <span>Pipeline <code style={{ color: 'var(--text-primary)', fontWeight: 600 }}>v{run.pipeline_version}</code> · fight #{run.scored_fight_id}</span>
      <span style={{ color: 'var(--text-disabled)' }}>·</span>
      <span>scored at <code style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{run.git_sha.slice(0, 7)}</code></span>
      <span style={{ color: 'var(--text-disabled)' }}>·</span>
      <span>constants <code style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{run.constants_sha256.slice(0, 6)}…</code></span>
      <span style={{ color: 'var(--text-disabled)' }}>·</span>
      <span>tolerance ±{run.tolerance_secs}s (±{run.tolerance_frames}f)</span>
      <span style={{ color: 'var(--text-disabled)' }}>·</span>
      <span>{labelled} labelled strikes</span>
    </div>
  );
}
