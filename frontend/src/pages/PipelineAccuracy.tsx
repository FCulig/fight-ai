import { useCallback, useEffect, useState } from 'react';
import { fetchEvalRun, fetchEvalRuns, fetchFixtures, fetchFights } from '../services/api';
import { latestPerVersion } from '../types/EvalRun';
import type { EvalReport, EvalRunSummary, FixtureSummary } from '../types/EvalRun';
import type { Fight } from '../types/Fight';
import { useWindowWidth } from '../hooks/useWindowWidth';
import { useLabelledEvents } from '../hooks/useLabelledEvents';
import { useFightLedger } from '../hooks/useFightLedger';
import ClassificationBreakdown from '../components/accuracy/ClassificationBreakdown';
import ConfusionHeatmap from '../components/accuracy/ConfusionHeatmap';
import FixtureTable from '../components/accuracy/FixtureTable';
import Glossary from '../components/accuracy/Glossary';
import HeadlineF1 from '../components/accuracy/HeadlineF1';
import NotMeasurable from '../components/accuracy/NotMeasurable';
import OffsetDotStrip from '../components/accuracy/OffsetDotStrip';
import ProvenanceLine from '../components/accuracy/ProvenanceLine';
import RoundsCheck from '../components/accuracy/RoundsCheck';
import StateDumbbell from '../components/accuracy/StateDumbbell';
import VersionTrendChart from '../components/accuracy/VersionTrendChart';
import WorstList from '../components/accuracy/WorstList';
import LabOverview from '../components/accuracy/LabOverview';
import AnnotatedEvents from '../components/accuracy/AnnotatedEvents';
import FightLedger from '../components/accuracy/FightLedger';
import PipelineHealthTodo from '../components/accuracy/PipelineHealthTodo';
import SectionIndex from '../components/accuracy/SectionIndex';

/**
 * Training Lab — as much of the full design (Overview / Annotated events /
 * Fights / Pipeline accuracy / Pipeline health) as the app's real data can
 * honestly show, built entirely from endpoints Player/Annotate/Training
 * Data QA already use (no new backend surface beyond the existing
 * `/eval-runs/*`). Section F stays a literal TODO — the design itself never
 * finished specifying it.
 */
export default function PipelineAccuracy() {
  const width = useWindowWidth();
  const isMobile = width < 640;
  const narrow = width < 1100;

  const [fixtures, setFixtures] = useState<FixtureSummary[]>([]);
  const [fights, setFights] = useState<Fight[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [runs, setRuns] = useState<EvalRunSummary[]>([]);
  /** `id` of the version being drilled into below the trend chart — not
   * necessarily the latest one; defaults to latest but the user can pick an
   * earlier version (including v1) via VersionTrendChart. */
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [report, setReport] = useState<EvalReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { events: labelledEvents, fights: labelledFights, roundMinutes, loading: labelledLoading } = useLabelledEvents();
  const { ledger, loading: ledgerLoading } = useFightLedger();

  const loadFixtures = useCallback(() => {
    setLoading(true);
    Promise.all([fetchFixtures(), fetchFights()])
      .then(([fx, fl]) => {
        setFixtures(fx);
        setFights(fl);
        setSelectedId((prev) => {
          if (prev !== null && fx.some((f) => f.reference_fight_id === prev)) return prev;
          const measurable = fx.find((f) => f.is_measurable);
          return (measurable ?? fx[0])?.reference_fight_id ?? null;
        });
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Unknown error'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadFixtures(); }, [loadFixtures]);

  const selected = fixtures.find((f) => f.reference_fight_id === selectedId) ?? null;

  useEffect(() => {
    if (!selected || !selected.is_measurable) {
      setRuns([]);
      setReport(null);
      return;
    }
    // Switching fixtures should default back to that fixture's latest
    // version, not carry over whatever version id was selected before.
    setSelectedRunId(null);
    fetchEvalRuns(selected.reference_fight_id)
      .then(setRuns)
      .catch((err) => setError(err instanceof Error ? err.message : 'Unknown error'));
  }, [selected]);

  const versions = latestPerVersion(runs);
  const selectedIndex = selectedRunId === null
    ? versions.length - 1
    : versions.findIndex((v) => v.id === selectedRunId);
  const current = selectedIndex >= 0 ? versions[selectedIndex] : null;
  const previous = current && selectedIndex > 0 ? versions[selectedIndex - 1] : null;
  const currentRunId = current?.id ?? null;

  useEffect(() => {
    if (currentRunId === null) {
      setReport(null);
      return;
    }
    fetchEvalRun(currentRunId)
      .then((r) => setReport(r.report))
      .catch((err) => setError(err instanceof Error ? err.message : 'Unknown error'));
  }, [currentRunId]);

  const candidates = fights.filter((f) => f.purpose === 'ai_labeled' && f.state === 'completed');

  return (
    <div style={{ position: 'relative', zIndex: 1, maxWidth: 1440, margin: '0 auto', padding: isMobile ? '18px 16px 70px' : '22px 30px 90px', width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, marginBottom: 22, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <span className="eyebrow">Lab</span>
          <h1 className="font-display" style={{ fontSize: isMobile ? 32 : 'clamp(36px, 4.6vw, 60px)', lineHeight: 0.94, margin: '10px 0 0', color: 'var(--text-primary)' }}>
            Training lab.
          </h1>
          <p style={{ margin: '10px 0 0', fontSize: 13.5, fontWeight: 500, color: 'var(--text-muted)' }}>
            What the model learns from, and how well it scores.
          </p>
        </div>
      </div>

      {error && <div style={{ fontSize: 13, color: 'var(--red-500)', marginBottom: 14 }}>{error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: narrow ? 'minmax(0,1fr)' : '172px minmax(0,1fr)', gap: 22, alignItems: 'start' }}>
        <SectionIndex narrow={narrow} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
          {labelledLoading ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading labelled data…</div>
          ) : (
            <LabOverview
              events={labelledEvents}
              fights={labelledFights}
              roundMinutes={roundMinutes}
              allFights={ledger.map((r) => r.fight)}
              fixtures={fixtures}
              onNavigate={(id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            />
          )}

          {!labelledLoading && <AnnotatedEvents events={labelledEvents} fights={labelledFights} />}

          {ledgerLoading ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading fights…</div>
          ) : (
            <FightLedger ledger={ledger} fixtures={fixtures} />
          )}

          <section id="sec-e" style={{ animation: 'fade-up .5s ease-out .32s both' }}>
            <div className="glass" style={{ padding: '20px 22px 22px' }}>
              <h2 className="font-display" style={{ margin: '0 0 4px', fontSize: 24, lineHeight: 1.05, color: 'var(--text-primary)' }}>Pipeline accuracy</h2>
              <p style={{ margin: '0 0 16px', fontSize: 12.5, fontWeight: 500, color: 'var(--text-muted)' }}>
                Reference fixtures scored against pipeline predictions, across versions
              </p>

              {loading && <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading…</div>}

              {!loading && fixtures.length === 0 && (
                <div className="inner-tile" style={{ padding: '20px 22px', fontSize: 13, color: 'var(--text-muted)' }}>
                  No labelled reference fixture exists yet. Upload a fight as "Self-annotate → Reference" and
                  finish labelling it to create one.
                </div>
              )}

              {fixtures.length > 0 && (
                <div className="inner-tile" style={{ padding: '16px 18px 18px', marginBottom: 16 }}>
                  <div className="label" style={{ marginBottom: 12 }}>Fixtures</div>
                  <FixtureTable fixtures={fixtures} selectedId={selectedId} onSelect={setSelectedId} />
                  <Glossary />
                </div>
              )}

              {selected && (
                !selected.is_measurable ? (
                  <NotMeasurable fixture={selected} candidates={candidates} onScored={loadFixtures} />
                ) : current ? (
                  <>
                    <div style={{ marginBottom: 16 }}>
                      <ProvenanceLine run={current} />
                    </div>
                    <div style={{ marginBottom: 20 }}>
                      <HeadlineF1 current={current} previous={previous} />
                    </div>
                    <div style={{ marginBottom: 20 }}>
                      <div className="label" style={{ marginBottom: 11 }}>Accuracy history — this fixture, every pipeline version</div>
                      <VersionTrendChart versions={versions} selectedId={current.id} onSelect={setSelectedRunId} />
                    </div>

                    {report && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 20, paddingTop: 18, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                        <div>
                          <div className="label" style={{ marginBottom: 11 }}>Classification — matched strikes only</div>
                          <ClassificationBreakdown strikes={report.strikes} />
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 20 }}>
                          <div>
                            <div className="label" style={{ marginBottom: 11 }}>Strike family confusion</div>
                            <ConfusionHeatmap confusion={report.strikes.family_confusion} emptyLabel="No specific-family matches yet." />
                          </div>
                          <div>
                            <div className="label" style={{ marginBottom: 11 }}>Timing</div>
                            <OffsetDotStrip offsets={report.strikes.matched_offsets} />
                          </div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 20 }}>
                          <div>
                            <div className="label" style={{ marginBottom: 11 }}>Fight state</div>
                            <StateDumbbell state={report.state} />
                            <div style={{ marginTop: 12 }}>
                              <ConfusionHeatmap confusion={report.state.confusion} emptyLabel="No state frames scored yet." />
                            </div>
                          </div>
                          <div>
                            <div className="label" style={{ marginBottom: 11 }}>Rounds</div>
                            <RoundsCheck rounds={report.rounds} />
                          </div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 20 }}>
                          <WorstList title="Worst misses" fps={report.fps} items={report.strikes.missed} emptyLabel="No missed strikes." />
                          <WorstList title="Worst false positives" fps={report.fps} items={report.strikes.spurious} emptyLabel="No false positives." />
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading runs…</div>
                )
              )}
            </div>
          </section>

          <PipelineHealthTodo />
        </div>
      </div>
    </div>
  );
}
