import { versionLabel } from '../../types/EvalRun';
import type { FixtureSummary } from '../../types/EvalRun';
import StatusBadge from './StatusBadge';

interface FixtureTableProps {
  fixtures: FixtureSummary[];
  selectedId: number | null;
  onSelect: (referenceFightId: number) => void;
}

const HEADERS = ['Fixture', 'Pipeline', 'Labelled', 'Predicted', 'TP / FP / FN', 'P', 'R', 'F1', 'Bias · jitter', 'Scored at'];

const videoStem = (path: string) => path.split('/').pop()?.replace(/\.[^.]+$/, '') ?? path;

/** Section E2 — one row per fixture (a labelled `purpose='reference'` fight),
 * showing its newest pipeline version's latest scoring. Click a row to drill
 * into E1/E8 for it. */
export default function FixtureTable({ fixtures, selectedId, onSelect }: FixtureTableProps) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="lab-table" style={{ width: '100%', borderCollapse: 'collapse', minWidth: 640 }}>
        <thead>
          <tr>
            {HEADERS.map((h, i) => (
              <th key={h} style={{
                textAlign: i === 0 ? 'left' : 'right', padding: '7px 10px', fontSize: 11, fontWeight: 800,
                color: 'var(--text-muted)',
                borderBottom: '1px solid rgba(255,255,255,0.08)', whiteSpace: 'nowrap',
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fixtures.map((fx) => {
            const r = fx.latest_run;
            const labelled = r ? (r.tp ?? 0) + (r.fn ?? 0) : null;
            const predicted = r ? (r.tp ?? 0) + (r.fp ?? 0) : null;
            return (
              <tr
                key={fx.reference_fight_id}
                onClick={() => onSelect(fx.reference_fight_id)}
                style={{
                  cursor: 'pointer',
                  background: selectedId === fx.reference_fight_id ? 'color-mix(in srgb, var(--accent) 5%, transparent)' : 'transparent',
                }}
              >
                <td style={{ padding: '9px 10px', fontSize: 12.5, fontWeight: 700, color: 'var(--text-primary)', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  #{fx.reference_fight_id} · {videoStem(fx.video_path)}
                </td>
                {!fx.is_measurable ? (
                  <td colSpan={HEADERS.length - 1} style={{ padding: '9px 10px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <StatusBadge status="none" size="sm">Not scorable — no evaluation fixture yet</StatusBadge>
                  </td>
                ) : (
                  <>
                    <Cell>{r && versionLabel(r)}</Cell>
                    <Cell>{labelled}</Cell>
                    <Cell>{predicted}</Cell>
                    <Cell>{r?.tp} / {r?.fp} / {r?.fn}</Cell>
                    <Cell>{r?.precision}%</Cell>
                    <Cell>{r?.recall}%</Cell>
                    <Cell><b style={{ fontWeight: 800, color: 'var(--text-primary)' }}>{r?.f1}%</b></Cell>
                    <Cell>{r?.offset_bias_frames ?? '—'} · {r?.offset_jitter_frames ?? '—'}</Cell>
                    <Cell>{r?.git_sha.slice(0, 7)}</Cell>
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Cell({ children }: { children: React.ReactNode }) {
  return (
    <td style={{
      padding: '9px 10px', textAlign: 'right', fontSize: 11.5, fontWeight: 600,
      color: 'var(--text-tertiary)', fontVariantNumeric: 'tabular-nums',
      borderBottom: '1px solid rgba(255,255,255,0.04)', whiteSpace: 'nowrap',
    }}>
      {children}
    </td>
  );
}
