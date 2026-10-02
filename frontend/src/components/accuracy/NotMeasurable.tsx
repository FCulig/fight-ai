import { useState } from 'react';
import type { Fight } from '../../types/Fight';
import type { FixtureSummary } from '../../types/EvalRun';
import { createEvalRun } from '../../services/api';
import { useAuth } from '../../hooks/useAuth';

interface NotMeasurableProps {
  fixture: FixtureSummary;
  /** Every `purpose='ai_labeled', state='completed'` fight — candidates to
   * score against this fixture. Passed down rather than fetched here so the
   * page fetches the fight list once and shares it across fixtures. */
  candidates: Fight[];
  onScored: () => void;
}

const videoStem = (path: string) => path.split('/').pop()?.replace(/\.[^.]+$/, '') ?? path;

/**
 * Section E's "E0" state (design brief §10): a labelled fixture with zero
 * eval_runs rows. Says so plainly instead of showing zeros, and gives both
 * the exact CLI command and a one-click "Run scoring" action when a
 * candidate ai_labeled fight already exists.
 */
export default function NotMeasurable({ fixture, candidates, onScored }: NotMeasurableProps) {
  const [picked, setPicked] = useState<number | ''>('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { can } = useAuth();

  const cmd = `python -m eval.cli score-pair --labels-fight-id ${fixture.reference_fight_id} --predictions-fight-id <ai_labeled fight id> --write-db`;

  const run = async () => {
    if (picked === '') return;
    setRunning(true);
    setError(null);
    try {
      await createEvalRun(fixture.reference_fight_id, picked);
      onScored();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Scoring failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div style={{
      display: 'grid', placeItems: 'center', gap: 12, padding: '40px 24px',
      borderRadius: 8, background: 'rgba(255,255,255,0.018)',
      border: '1px dashed rgba(255,255,255,0.14)', textAlign: 'center',
    }}>
      <span className="material-symbols-outlined" style={{ fontSize: 34, color: 'var(--text-disabled)' }}>help</span>
      <p style={{ margin: 0, maxWidth: '46ch', fontSize: 13, lineHeight: 1.6, fontWeight: 500, color: 'var(--text-secondary)' }}>
        <strong>Strike accuracy isn't measurable yet</strong> for {videoStem(fixture.video_path)}.
        Re-run this source video through the AI pipeline (upload it again as an
        "AI annotation" fight) to make it an evaluation fixture, then score it
        against these labels — keep it out of the training set.
      </p>
      {candidates.length > 0 && can('admin') ? (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'center' }}>
          <select
            value={picked}
            onChange={(e) => setPicked(e.target.value === '' ? '' : Number(e.target.value))}
            className="btn-glass"
            style={{ padding: '7px 10px', fontSize: 12, fontWeight: 500 }}
          >
            <option value="">Choose an AI-processed fight…</option>
            {candidates.map((f) => (
              <option key={f.id} value={f.id}>#{f.id} · {videoStem(f.video_path)}</option>
            ))}
          </select>
          <button
            type="button"
            className="btn-primary"
            disabled={picked === '' || running}
            onClick={run}
            style={{ fontWeight: 600, fontSize: 12, padding: '7px 16px', opacity: picked === '' || running ? 0.5 : 1 }}
          >
            {running ? 'Scoring…' : 'Run scoring'}
          </button>
        </div>
      ) : (
        <div style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-muted)' }}>
          {candidates.length > 0
            ? 'An admin can score it against a completed AI-processed fight.'
            : 'No completed AI-processed fight exists yet to score.'}
        </div>
      )}
      {error && <div style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--red-500)' }}>{error}</div>}
      <code style={{
        display: 'block', maxWidth: '100%', overflowX: 'auto', padding: '8px 12px',
        borderRadius: 6, background: 'rgba(0,0,0,0.42)', border: '1px solid var(--border-subtle)',
        fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-primary)', whiteSpace: 'pre',
      }}>
        {cmd}
      </code>
    </div>
  );
}
