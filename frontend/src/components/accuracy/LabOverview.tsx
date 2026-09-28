import { useMemo, useState } from 'react';
import type { LabelEvent } from '../../hooks/useLabelledEvents';
import type { Fight } from '../../types/Fight';
import type { FixtureSummary } from '../../types/EvalRun';
import { TRAINING_ACTIONS, FAMILY_BY_ACTION, STRIKE_FAMILIES } from '../../utils/trainingDataTaxonomy';
import { fightLabel } from '../../utils/fightLabel';

const TRAINING_TARGET = 300;
const MIN_EXAMPLES = 25;

interface LabOverviewProps {
  events: LabelEvent[];
  fights: Fight[];
  roundMinutes: Map<number, number>;
  allFights: Fight[];
  fixtures: FixtureSummary[];
  onNavigate: (id: string) => void;
}

function Tile({ label, value, sub, color, onClick }: { label: string; value: React.ReactNode; sub: string; color?: string; onClick?: () => void }) {
  return (
    <div
      className="inner-tile"
      onClick={onClick}
      style={{ padding: '14px 16px 15px', cursor: onClick ? 'pointer' : 'default', display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}
    >
      <div className="label">{label}</div>
      <span className="font-display" style={{ fontSize: 30, lineHeight: 0.92, color: color ?? 'var(--text-primary)' }}>{value}</span>
      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', lineHeight: 1.45 }}>{sub}</div>
    </div>
  );
}

export default function LabOverview({ events, fights, roundMinutes, allFights, fixtures, onNavigate }: LabOverviewProps) {
  // Computed once at mount, not on every render — react-hooks/purity forbids
  // an impure Date.now() call directly in the render body.
  const [now] = useState(() => Date.now());
  const stats = useMemo(() => {
    const strikes = events.filter((e) => TRAINING_ACTIONS.has(e.action ?? ''));
    const have = strikes.length;
    const pct = Math.min(100, Math.round((have / TRAINING_TARGET) * 100));

    const byFight = new Map<number, number>();
    strikes.forEach((e) => byFight.set(e.fight.id, (byFight.get(e.fight.id) ?? 0) + 1));
    let largestFightId: number | null = null;
    let largestFightCount = 0;
    byFight.forEach((n, id) => { if (n > largestFightCount) { largestFightCount = n; largestFightId = id; } });
    const largestFight = fights.find((f) => f.id === largestFightId) ?? null;
    const largestShare = have > 0 ? Math.round((largestFightCount / have) * 100) : 0;

    const byFamily = new Map<string, number>();
    strikes.forEach((e) => {
      const fam = FAMILY_BY_ACTION[e.action ?? ''];
      if (fam) byFamily.set(fam, (byFamily.get(fam) ?? 0) + 1);
    });
    const belowMin = STRIKE_FAMILIES.filter((f) => (byFamily.get(f) ?? 0) < MIN_EXAMPLES);

    const totalMinutes = fights.reduce((sum, f) => sum + (roundMinutes.get(f.id) ?? 0), 0);

    const cutoff = now - 14 * 24 * 60 * 60 * 1000;
    const recent = events.filter((e) => new Date(e.created_at).getTime() >= cutoff).length;

    return { have, pct, largestFight, largestShare, belowMin, totalMinutes, totalLabelEvents: events.length, recent };
  }, [events, fights, roundMinutes, now]);

  const fightBreakdown = useMemo(() => {
    const inProgress = allFights.filter((f) => f.state === 'labeling_in_progress').length;
    const complete = allFights.filter((f) => f.state === 'labeling_complete' || f.state === 'completed').length;
    return { total: allFights.length, inProgress, complete };
  }, [allFights]);

  const bestMeasurable = useMemo(() => {
    const measurable = fixtures.filter((f) => f.is_measurable && f.latest_run);
    if (measurable.length === 0) return null;
    return measurable.reduce((best, f) => (f.latest_run!.f1! > (best.latest_run?.f1 ?? -1) ? f : best), measurable[0]);
  }, [fixtures]);

  return (
    <section id="sec-a" style={{ animation: 'fade-up .5s ease-out both' }}>
      <div className="glass" style={{ padding: '20px 22px 22px', display: 'grid', gridTemplateColumns: '5fr 7fr', gap: 14 }}>
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div className="label" style={{ marginBottom: 12 }}>Training set progress</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, marginBottom: 3 }}>
              <span className="font-display" style={{ fontSize: 52, lineHeight: 0.86, color: 'var(--text-primary)' }}>{stats.have}</span>
              <span className="font-display" style={{ fontSize: 26, lineHeight: 1, color: 'var(--text-disabled)' }}>/ {TRAINING_TARGET}</span>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)' }}>strikes</span>
            </div>
          </div>
          <div>
            <div style={{ position: 'relative', height: 14, borderRadius: 7, background: 'color-mix(in srgb, var(--accent) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--accent) 16%, transparent)', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', inset: '0 auto 0 0', width: `${stats.pct}%`, background: 'linear-gradient(90deg, var(--accent-deep), var(--accent))', borderRadius: '7px 4px 4px 7px' }} />
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8, fontSize: 11.5, fontWeight: 700, color: 'var(--text-tertiary)' }}>
              <span style={{ color: 'var(--accent)' }}>{stats.pct}%</span>
              <span style={{ color: 'var(--text-disabled)' }}>·</span>
              <span>{stats.recent} in the last 14 days</span>
            </div>
            <div style={{ marginTop: 9, paddingTop: 9, borderTop: '1px solid rgba(255,255,255,0.05)', fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', lineHeight: 1.6 }}>
              {stats.totalMinutes.toFixed(0)} min of labelled round time across {fights.length} fight{fights.length === 1 ? '' : 's'}
              {stats.largestFight && stats.largestShare >= 40 && (
                <> · <span style={{ color: '#ffb199' }}>{fightLabel(stats.largestFight)} alone is {stats.largestShare}% of it</span></>
              )}
              {stats.belowMin.length > 0 && (
                <> · <span style={{ color: '#ffb199' }}>{stats.belowMin.length} of {STRIKE_FAMILIES.length} families below the {MIN_EXAMPLES}-example minimum</span> ({stats.belowMin.join(', ')})</>
              )}
            </div>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0,1fr))', gap: 12 }}>
          <Tile
            label="Label events"
            value={stats.totalLabelEvents}
            sub={`+${stats.recent} in the last 14 days · includes state marks`}
            onClick={() => onNavigate('sec-b')}
          />
          <Tile
            label="Fights"
            value={fightBreakdown.total}
            sub={`${fightBreakdown.complete} finished · ${fightBreakdown.inProgress} in progress`}
            onClick={() => onNavigate('sec-d')}
          />
          <Tile
            label="Strike detection F1"
            value={bestMeasurable?.latest_run ? `${bestMeasurable.latest_run.f1}%` : 'Not scorable'}
            color={bestMeasurable?.latest_run ? 'var(--accent)' : undefined}
            sub={bestMeasurable?.latest_run ? `${bestMeasurable.latest_run.tp! + bestMeasurable.latest_run.fn!} labelled · v${bestMeasurable.latest_run.pipeline_version}` : 'No evaluation fixture scored yet'}
            onClick={() => onNavigate('sec-e')}
          />
        </div>
      </div>
    </section>
  );
}
