import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { LedgerFight } from '../../hooks/useFightLedger';
import type { FixtureSummary } from '../../types/EvalRun';
import { fightLabel } from '../../utils/fightLabel';
import { TRAINING_ACTIONS } from '../../utils/trainingDataTaxonomy';
import FightPurposeBadge from '../FightPurposeBadge';
import StatusBadge from './StatusBadge';
import CoverageStrip from './CoverageStrip';

const SORTS = ['Fight', 'Strikes', 'Round min', 'Warnings'] as const;
type Sort = (typeof SORTS)[number];

interface Derived {
  strikes: number;
  perMin: number | null;
  stateMarks: number;
  swaps: number;
  excluded: number;
  f1: number | null;
  labeler: string | null;
  warnings: { t: string; d: string }[];
}

function derive(row: LedgerFight, fixtures: FixtureSummary[]): Derived {
  const { fight, pointEvents, swapEvents, excludedEvents, minutes } = row;
  const strikes = pointEvents.filter((e) => TRAINING_ACTIONS.has(e.action ?? '')).length;
  const stateMarks = pointEvents.filter((e) => e.action?.startsWith('state_')).length;
  const perMin = minutes > 0 ? strikes / minutes : null;
  const labeler = pointEvents.find((e) => e.labeler)?.labeler
    ?? row.roundEvents.find((e) => e.labeler)?.labeler
    ?? null;

  const asReference = fixtures.find((fx) => fx.reference_fight_id === fight.id);
  const asScored = fixtures.find((fx) => fx.latest_run?.scored_fight_id === fight.id);
  const f1 = asReference?.latest_run?.f1 ?? asScored?.latest_run?.f1 ?? null;

  const warnings: { t: string; d: string }[] = [];
  if (fight.segmentation_needs_review && !fight.labeled_at) {
    warnings.push({ t: 'Rounds unverified', d: fight.segmentation_review_reason ?? 'Segmentation could not confirm these rounds against the scoreboard.' });
  }
  if (minutes >= 1 && strikes === 0 && fight.purpose !== 'ai_labeled') {
    warnings.push({ t: 'No strikes despite labelled round time', d: `${minutes.toFixed(1)} min of rounds carry zero strike labels — check the fight wasn't left unannotated.` });
  }
  if (swapEvents.some((s) => s.end_frame == null)) {
    warnings.push({ t: 'Corner-swap span left open', d: 'A corner_swap span has no end frame — it never got closed in Annotate.' });
  }

  return { strikes, perMin, stateMarks, swaps: swapEvents.length, excluded: excludedEvents.length, f1, labeler, warnings };
}

function LM({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 3, whiteSpace: 'nowrap' }}>{k}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 800, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{children}</div>
    </div>
  );
}

interface FightLedgerProps {
  ledger: LedgerFight[];
  fixtures: FixtureSummary[];
}

export default function FightLedger({ ledger, fixtures }: FightLedgerProps) {
  const [sort, setSort] = useState<Sort>('Fight');
  const [expanded, setExpanded] = useState<number | null>(null);
  const navigate = useNavigate();

  const rows = useMemo(() => {
    const withStats = ledger.map((row) => ({ row, d: derive(row, fixtures) }));
    const sorted = [...withStats];
    if (sort === 'Strikes') sorted.sort((a, b) => b.d.strikes - a.d.strikes);
    else if (sort === 'Round min') sorted.sort((a, b) => b.row.minutes - a.row.minutes);
    else if (sort === 'Warnings') sorted.sort((a, b) => b.d.warnings.length - a.d.warnings.length);
    else sorted.sort((a, b) => a.row.fight.id - b.row.fight.id);
    return sorted;
  }, [ledger, fixtures, sort]);

  const finished = ledger.filter((r) => r.fight.state === 'labeling_complete' || r.fight.state === 'completed').length;
  const inProgress = ledger.filter((r) => r.fight.state === 'labeling_in_progress').length;

  return (
    <section id="sec-d" style={{ animation: 'fade-up .5s ease-out .16s both' }}>
      <div className="glass" style={{ padding: '20px 22px 22px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 260px', minWidth: 0 }}>
            <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>Fights</h2>
            <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-muted)', marginTop: 4 }}>
              {ledger.length} fights · {finished} finished · {inProgress} in progress · expand a fight for its spans and coverage
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>Sort</span>
            <div style={{ display: 'flex', gap: 4, padding: 3, borderRadius: 999, background: 'var(--surface-glass)', border: '1px solid var(--border-glass)' }}>
              {SORTS.map((s) => (
                <button key={s} type="button" className={'pill' + (sort === s ? ' active' : '')} onClick={() => setSort(s)} style={{ padding: '5px 11px', fontSize: 11.5 }}>{s}</button>
              ))}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {rows.map(({ row, d }) => {
            const open = expanded === row.fight.id;
            return (
              <div
                key={row.fight.id}
                style={{
                  border: '1px solid var(--border-subtle)', borderRadius: 18, background: 'var(--surface-glass)',
                  borderColor: open ? 'var(--border-glass)' : 'var(--border-subtle)',
                  overflow: 'hidden', transition: 'border-color .12s, background .12s',
                }}
              >
                <div
                  onClick={() => setExpanded(open ? null : row.fight.id)}
                  style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: '10px 14px', alignItems: 'center', padding: '12px 14px', cursor: 'pointer' }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, minWidth: 0 }}>
                    <span className="material-symbols-outlined" style={{ fontSize: 17, color: 'var(--text-disabled)', flexShrink: 0, marginTop: 1 }}>
                      {open ? 'expand_more' : 'chevron_right'}
                    </span>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 13.5, fontWeight: 800, color: 'var(--text-primary)' }}>{fightLabel(row.fight)}</span>
                        <FightPurposeBadge purpose={row.fight.purpose} size="sm" />
                        {d.warnings.length > 0 && (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 7px', borderRadius: 6, background: 'rgba(255,177,153,0.14)', border: '1px solid rgba(255,177,153,0.3)', color: '#ffb199', fontSize: 11, fontWeight: 800 }}>
                            <span className="material-symbols-outlined" style={{ fontSize: 12 }}>warning</span>{d.warnings.length}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginTop: 4 }}>
                        #{row.fight.id} · {row.rounds.length} round{row.rounds.length === 1 ? '' : 's'} · {row.fight.state.replace(/_/g, ' ')}
                      </div>
                    </div>
                  </div>
                  <div onClick={(ev) => ev.stopPropagation()} style={{ display: 'flex', gap: 4 }}>
                    <button type="button" className="icon-btn" title="Open in Player" onClick={() => navigate(`/fights/${row.fight.id}`)} style={{ width: 30, height: 30 }}>
                      <span className="material-symbols-outlined" style={{ fontSize: 15 }}>play_circle</span>
                    </button>
                  </div>
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 22px', padding: '0 14px 13px' }}>
                  <LM k="Round min">{row.minutes > 0 ? row.minutes.toFixed(1) : <span style={{ color: 'var(--text-disabled)' }}>—</span>}</LM>
                  <LM k="Strikes · /min">
                    {row.minutes > 0 ? <>{d.strikes} <span style={{ fontWeight: 700, color: d.perMin != null && d.perMin < 0.3 ? '#ffb199' : 'var(--text-muted)' }}>{d.perMin?.toFixed(1)}/min</span></> : <span style={{ color: 'var(--text-disabled)' }}>—</span>}
                  </LM>
                  <LM k="State marks">{d.stateMarks || <span style={{ color: 'var(--text-disabled)' }}>—</span>}</LM>
                  <LM k="Swaps">{d.swaps > 0 ? <span style={{ color: '#ffb199' }}>{d.swaps}</span> : <span style={{ color: 'var(--text-disabled)' }}>—</span>}</LM>
                  <LM k="Excluded">{d.excluded || <span style={{ color: 'var(--text-disabled)' }}>—</span>}</LM>
                  <LM k="Corner check"><StatusBadge status="none" size="sm">Not run</StatusBadge></LM>
                  <LM k="Strike F1">{d.f1 != null ? <StatusBadge status="good" size="sm">{d.f1}%</StatusBadge> : <span style={{ color: 'var(--text-disabled)' }}>—</span>}</LM>
                </div>

                {open && (
                  <div style={{ padding: '15px 16px 17px', borderTop: '1px solid var(--border-subtle)', background: 'rgba(0,0,0,0.18)' }}>
                    {row.rounds.length > 0 && (
                      <div style={{ marginBottom: 18 }}>
                        <div className="label" style={{ marginBottom: 10 }}>Coverage</div>
                        <CoverageStrip fight={row.fight} rounds={row.rounds} pointEvents={row.pointEvents} swapEvents={row.swapEvents} excludedEvents={row.excludedEvents} roundEvents={row.roundEvents} />
                      </div>
                    )}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 20 }}>
                      <div>
                        <div className="label" style={{ marginBottom: 9 }}>Warnings · {d.warnings.length}</div>
                        {d.warnings.length === 0 ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, fontWeight: 700, color: 'var(--accent)' }}>
                            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>check_circle</span>Nothing flagged
                          </div>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {d.warnings.map((w, i) => (
                              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                                <span className="material-symbols-outlined" style={{ fontSize: 14, color: '#ffb199', flexShrink: 0, marginTop: 1 }}>warning</span>
                                <div style={{ minWidth: 0 }}>
                                  <div style={{ fontSize: 11.5, fontWeight: 700, color: 'var(--text-secondary)' }}>{w.t}</div>
                                  <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', lineHeight: 1.5 }}>{w.d}</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="label" style={{ marginBottom: 9 }}>Provenance</div>
                        <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '5px 12px', margin: 0 }}>
                          <dt style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>Labeller</dt>
                          <dd style={{ margin: 0, fontSize: 11.5, fontWeight: 700, color: 'var(--text-secondary)' }}>
                            {d.labeler ?? <StatusBadge status="none" size="sm">Not recorded</StatusBadge>}
                          </dd>
                          <dt style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>Segmentation</dt>
                          <dd style={{ margin: 0, fontSize: 11.5, fontWeight: 700, color: 'var(--text-secondary)' }}>
                            {row.fight.segmentation_needs_review
                              ? <StatusBadge status="warning" size="sm">Detection only</StatusBadge>
                              : <StatusBadge status="good" size="sm">Clock</StatusBadge>}
                          </dd>
                          {row.fight.segmentation_review_reason && (
                            <>
                              <dt style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>Reason</dt>
                              <dd style={{ margin: 0, fontSize: 11.5, fontWeight: 600, fontStyle: 'italic', color: 'var(--text-tertiary)' }}>“{row.fight.segmentation_review_reason}”</dd>
                            </>
                          )}
                        </dl>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
