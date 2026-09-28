import type { Event } from '../../types/Event';
import type { Round } from '../../types/Round';
import type { Fight } from '../../types/Fight';

const STATE_C: Record<string, string> = {
  STRIKING: 'var(--state-striking)', CLINCH: 'var(--state-clinch)', GROUND: 'var(--state-ground)',
};

interface CoverageStripProps {
  fight: Fight;
  rounds: Round[];
  pointEvents: Event[];
  swapEvents: Event[];
  excludedEvents: Event[];
  roundEvents: Event[];
}

const LANE_H = 14;

function Lane({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '76px 1fr', gap: 10, alignItems: 'center', marginBottom: 5 }}>
      <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-disabled)', textAlign: 'right' }}>{label}</span>
      <div style={{ position: 'relative', height: LANE_H, borderRadius: 3, background: 'rgba(255,255,255,0.03)', overflow: 'hidden' }}>{children}</div>
    </div>
  );
}

/**
 * A compact, non-interactive strip of a fight's labelled rounds, fight-state
 * segments, corner-swap/excluded spans and strike density — the fights
 * ledger's expanded-row visual. Reads the same fight_events rows
 * AnnotationTimeline draws (round/corner_swap/excluded spans, state_* point
 * marks), just flattened into a fixed read-only band instead of a scrubbable
 * multi-track timeline — this page has no video to seek.
 */
export default function CoverageStrip({ fight, rounds, pointEvents, swapEvents, excludedEvents, roundEvents }: CoverageStripProps) {
  const lastRoundFrame = rounds.length > 0 ? Math.max(...rounds.map((r) => r.end_frame)) : 0;
  const lastEventFrame = pointEvents.length > 0 ? Math.max(...pointEvents.map((e) => e.frame)) : 0;
  const duration = Math.max(lastRoundFrame, lastEventFrame, 1);
  const pct = (frame: number) => Math.min(100, (frame / duration) * 100);
  const durSecs = duration / fight.fps;
  const durLabel = `${Math.floor(durSecs / 60)}:${String(Math.floor(durSecs % 60)).padStart(2, '0')}`;

  const stateMarks = pointEvents
    .filter((e) => e.action?.startsWith('state_'))
    .map((e) => ({ frame: e.frame, state: e.action === 'state_clinch' ? 'CLINCH' : e.action === 'state_ground' ? 'GROUND' : 'STRIKING' }))
    .sort((a, b) => a.frame - b.frame);
  const stateSegs = stateMarks.map((m, i) => ({
    start: m.frame, end: i + 1 < stateMarks.length ? stateMarks[i + 1].frame : duration, state: m.state,
  }));

  const strikes = pointEvents.filter((e) => !e.action?.startsWith('state_'));
  const BUCKETS = 24;
  const density = new Array(BUCKETS).fill(0);
  strikes.forEach((e) => {
    const b = Math.min(BUCKETS - 1, Math.floor((e.frame / duration) * BUCKETS));
    density[b]++;
  });
  const densityMax = Math.max(...density, 1);

  const isSeeded = (r: Round) => roundEvents.some(
    (re) => re.value === String(r.round_number) && re.frame === r.start_frame && re.end_frame === r.end_frame,
  );

  return (
    <div>
      <Lane label="Rounds">
        {rounds.map((r) => {
          const seeded = isSeeded(r);
          return (
            <div
              key={r.id}
              title={`Round ${r.round_number}${seeded ? ' · seeded, unverified' : ' · adjusted by hand'}`}
              style={{
                position: 'absolute', top: 1, bottom: 1, left: `${pct(r.start_frame)}%`, width: `${pct(r.end_frame) - pct(r.start_frame)}%`,
                background: seeded ? 'rgba(245,245,244,0.14)' : 'rgba(245,245,244,0.42)',
                border: seeded ? '1px dashed rgba(245,245,244,0.7)' : 'none', borderRadius: 3,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <span style={{ fontSize: 10, fontWeight: 800, color: '#0e0f12' }}>R{r.round_number}</span>
            </div>
          );
        })}
      </Lane>
      <Lane label="State">
        {stateSegs.map((s, i) => (
          <div
            key={i}
            title={`${s.state} · frame ${s.start}`}
            style={{ position: 'absolute', top: 0, bottom: 0, left: `${pct(s.start)}%`, width: `${pct(s.end) - pct(s.start)}%`, background: STATE_C[s.state] }}
          />
        ))}
      </Lane>
      <Lane label="Swaps / excluded">
        {swapEvents.map((s) => (
          <div
            key={'sw' + s.id}
            title={s.end_frame == null ? 'Corner swap — still open' : 'Corner swap'}
            style={{ position: 'absolute', top: 0, bottom: 0, left: `${pct(s.frame)}%`, width: `${Math.max(pct((s.end_frame ?? duration)) - pct(s.frame), 0.6)}%`, background: 'var(--purple-600)', borderRadius: 2 }}
          />
        ))}
        {excludedEvents.map((e) => (
          <div
            key={'ex' + e.id}
            title={`Excluded — ${e.value ?? 'unspecified'}`}
            style={{
              position: 'absolute', top: 0, bottom: 0, left: `${pct(e.frame)}%`, width: `${Math.max(pct((e.end_frame ?? duration)) - pct(e.frame), 0.6)}%`,
              background: 'rgba(154,152,146,0.35)', borderRadius: 2,
              backgroundImage: 'repeating-linear-gradient(45deg,rgba(255,255,255,0.16) 0 2px,transparent 2px 4px)',
            }}
          />
        ))}
      </Lane>
      <Lane label="Density">
        {density.map((d, i) => (
          <div
            key={i}
            title={`${d} strikes in this ${(durSecs / BUCKETS).toFixed(0)}s bucket`}
            style={{
              position: 'absolute', top: 0, bottom: 0, left: `${(i / BUCKETS) * 100}%`, width: `${100 / BUCKETS}%`,
              background: d ? `color-mix(in srgb, var(--accent) ${8 + (d / densityMax) * 84}%, transparent)` : 'transparent',
            }}
          />
        ))}
      </Lane>
      <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--text-muted)', marginTop: 4 }}>{durLabel} of video</div>
    </div>
  );
}
