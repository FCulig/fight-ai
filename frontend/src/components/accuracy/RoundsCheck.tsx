import type { EvalReport } from '../../types/EvalRun';
import StatusBadge from './StatusBadge';

interface RoundsCheckProps {
  rounds: EvalReport['rounds'];
}

/** Section E7 — round count + per-round IoU, with "Seeded — not verified"
 * standing in for the IoU on any round whose label bounds are still
 * byte-identical to what they were auto-seeded from (circular otherwise). */
export default function RoundsCheck({ rounds }: RoundsCheckProps) {
  const countOk = rounds.gt_count === rounds.pred_count;
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
          truth {rounds.gt_count} · predicted {rounds.pred_count}
        </span>
        <StatusBadge status={countOk ? 'good' : 'critical'} size="sm">{countOk ? 'Count OK' : 'Count WRONG'}</StatusBadge>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {rounds.matched.map(([num, iou, dstart, dend, seeded]) => (
          <div key={num} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11.5, fontWeight: 500, color: 'var(--text-tertiary)' }}>
            <span style={{ fontWeight: 700, color: 'var(--text-primary)', minWidth: 56 }}>Round {num}</span>
            {seeded ? (
              <StatusBadge status="warning" size="sm" title="Still byte-identical to the pipeline's own segmentation — a labeller hasn't confirmed it. Scoring its IoU would be circular.">
                Seeded — not verified
              </StatusBadge>
            ) : (
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>IoU {(iou * 100).toFixed(1)}%</span>
            )}
            <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-muted)' }}>
              start {dstart >= 0 ? '+' : ''}{dstart.toFixed(2)}s · end {dend >= 0 ? '+' : ''}{dend.toFixed(2)}s
            </span>
          </div>
        ))}
      </div>
      {!countOk && (
        <p style={{ margin: '10px 0 0', fontSize: 10.5, fontWeight: 500, color: 'var(--text-muted)', lineHeight: 1.5 }}>
          Mean IoU stays high when one round is split into several — the count is what catches that.
        </p>
      )}
    </div>
  );
}
