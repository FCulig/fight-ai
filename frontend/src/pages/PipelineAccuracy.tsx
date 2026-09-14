import { useCallback, useEffect, useState } from 'react';
import { fetchEvalRun, fetchEvalRuns, fetchFixtures, fetchFights } from '../services/api';
import { latestPerVersion } from '../types/EvalRun';
import type { EvalReport, EvalRunSummary, FixtureSummary } from '../types/EvalRun';
import type { Fight } from '../types/Fight';
import { useWindowWidth } from '../hooks/useWindowWidth';
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

/**
 * Training Lab, Section E only ("Pipeline accuracy") — see
 * ~/.claude/plans/i-have-now-reference-radiant-salamander.md. Sections
 * A-D/F/G of the full design need labelled-data volume/infrastructure this
 * app doesn't have yet; this page covers only what the current fixtures
 * (a labelled reference fight scored against a re-uploaded, AI-processed
 * copy of itself) can honestly show — E0/E1/E2/E8.
 */
export default function PipelineAccuracy() {
  const width = useWindowWidth();
  const isMobile = width < 640;

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
    <div style={{ maxWidth: 1440, margin: '0 auto', padding: isMobile ? '14px 13px 60px' : '22px 30px 80px', width: '100%' }}>
      <div style={{ marginBottom: 16 }}>
        <h1 className="font-display" style={{ fontSize: isMobile ? 30 : 40, lineHeight: 0.94, margin: 0, color: 'var(--text-primary)' }}>
          PIPELINE ACCURACY
        </h1>
        <p style={{ margin: '5px 0 0', fontSize: 12.5, fontWeight: 600, color: 'var(--text-muted)' }}>
          Reference fixtures scored against pipeline predictions, across versions
        </p>
      </div>

      {loading && <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading…</div>}
      {error && <div style={{ fontSize: 13, color: 'var(--red-500)', marginBottom: 14 }}>{error}</div>}

      {!loading && fixtures.length === 0 && (
        <div className="glass" style={{ padding: '20px 22px', fontSize: 13, color: 'var(--text-muted)' }}>
          No labelled reference fixture exists yet. Upload a fight as "Self-annotate → Reference" and
          finish labelling it to create one.
        </div>
      )}

      {fixtures.length > 0 && (
        <div className="glass" style={{ padding: '20px 22px 22px', marginBottom: 16 }}>
          <div className="label" style={{ marginBottom: 12 }}>Fixtures</div>
          <FixtureTable fixtures={fixtures} selectedId={selectedId} onSelect={setSelectedId} />
          <Glossary />
        </div>
      )}

      {selected && (
        <div className="glass" style={{ padding: '20px 22px 22px' }}>
          {!selected.is_measurable ? (
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
          )}
        </div>
      )}
    </div>
  );
}
