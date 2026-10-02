import { versionLabel } from '../../types/EvalRun';
import type { EvalRunSummary } from '../../types/EvalRun';

interface VersionTrendChartProps {
  /** One run per pipeline version, oldest first. */
  versions: EvalRunSummary[];
  /** `id` of the version whose full report is shown below the chart. */
  selectedId: number;
  /** Click a point or its label to drill into that version's full report. */
  onSelect: (id: number) => void;
}

const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

/**
 * Section E8 — F1/P/R across pipeline versions for one fixture, one point per
 * scored ai_labeled fight (including v1, the first pipeline version — every
 * version stays comparable here even once later versions exist). A hollow
 * marker means the matching constants changed at that version (compare with
 * care); a dashed vertical rule marks a version scored at a different
 * tolerance from the one before it (not directly comparable — honesty rule
 * 8). Click any point or version label to load its full drill-down below.
 */
export default function VersionTrendChart({ versions: runs, selectedId, onSelect }: VersionTrendChartProps) {
  const W = 640, H = 160, padL = 28, padR = 20, padT = 14, padB = 34;
  const n = runs.length;
  if (n < 1) return null;

  const x = (i: number) => n === 1 ? W / 2 : padL + (i / (n - 1)) * (W - padL - padR);
  const y = (v: number) => H - padB - (v / 100) * (H - padB - padT);
  const line = (key: 'f1' | 'precision' | 'recall') =>
    runs.map((r, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(r[key] ?? 0).toFixed(1)}`).join(' ');

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="xMidYMid meet" style={{ display: 'block', overflow: 'visible' }}>
        {[0, 25, 50, 75, 100].map((g) => (
          <line key={g} x1={padL} x2={W - padR} y1={y(g)} y2={y(g)} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
        ))}
        {runs.map((r, i) => (
          i > 0 && r.tolerance_frames !== runs[i - 1].tolerance_frames && (
            <line key={`tol-${r.id}`} x1={x(i)} x2={x(i)} y1={padT} y2={H - padB}
              stroke="color-mix(in srgb, var(--warn) 50%, transparent)" strokeWidth="1" strokeDasharray="3 3" />
          )
        ))}
        <path d={line('precision')} fill="none" stroke="color-mix(in srgb, var(--accent) 30%, transparent)" strokeWidth="1.5" strokeDasharray="3 3" />
        <path d={line('recall')} fill="none" stroke="rgba(179,157,251,0.5)" strokeWidth="1.5" strokeDasharray="3 3" />
        <path d={line('f1')} fill="none" stroke="var(--cyan-400)" strokeWidth="2" />
        {runs.map((r, i) => {
          const constantsChanged = i > 0 && r.constants_sha256 !== runs[i - 1].constants_sha256;
          const isSelected = r.id === selectedId;
          return (
            <g key={r.id} onClick={() => onSelect(r.id)} style={{ cursor: 'pointer' }}>
              {isSelected && (
                <circle cx={x(i)} cy={y(r.f1 ?? 0)} r={9} fill="none"
                  stroke="var(--cyan-400)" strokeWidth={1.5} opacity={0.4} />
              )}
              <circle cx={x(i)} cy={y(r.f1 ?? 0)} r={isSelected ? 5.5 : 3.5}
                fill={constantsChanged ? 'var(--surface-glass)' : 'var(--cyan-400)'}
                stroke="var(--cyan-400)" strokeWidth={isSelected ? 2.5 : 1.5}>
                <title>{versionLabel(r)} · F1 {r.f1}% · P {r.precision}% · R {r.recall}% · scored at {r.git_sha.slice(0, 7)} on {shortDate(r.generated_at)}{constantsChanged ? ' · constants changed' : ''}</title>
              </circle>
              {/* Larger invisible hit target — the dot alone is a small click target. */}
              <circle cx={x(i)} cy={y(r.f1 ?? 0)} r={12} fill="transparent" />
            </g>
          );
        })}
      </svg>
      <div style={{ position: 'relative', height: 34, marginTop: 2 }}>
        {runs.map((r, i) => (
          <button
            key={r.id}
            type="button"
            onClick={() => onSelect(r.id)}
            style={{
              position: 'absolute', top: 0, left: `${(x(i) / W) * 100}%`, transform: 'translateX(-50%)',
              textAlign: 'center', whiteSpace: 'nowrap', background: 'none', border: 'none',
              padding: '2px 4px', cursor: 'pointer',
            }}
          >
            <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, fontWeight: r.id === selectedId ? 600 : 400, color: r.id === selectedId ? 'var(--text-primary)' : 'var(--text-muted)' }}>
              v{r.pipeline_version}
            </div>
            <div style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-disabled)' }}>fight #{r.scored_fight_id}</div>
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', marginTop: 10 }}>
        <Legend c="var(--cyan-400)" name="F1" />
        <Legend c="color-mix(in srgb, var(--accent) 30%, transparent)" name="Precision" />
        <Legend c="rgba(179,157,251,0.5)" name="Recall" />
        <span style={{ fontSize: 10.5, fontWeight: 500, color: 'var(--text-muted)' }}>
          Hollow point = matching constants changed at that version. Click a point to view its report below.
        </span>
      </div>
    </div>
  );
}

function Legend({ c, name }: { c: string; name: string }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5, fontWeight: 500, color: 'var(--text-secondary)' }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: c, flexShrink: 0 }} />{name}
    </span>
  );
}
