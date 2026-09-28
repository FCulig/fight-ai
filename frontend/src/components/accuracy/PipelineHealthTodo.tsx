/**
 * Section F ("Pipeline health") in the Training Lab design is itself an open
 * placeholder — its own copy reads "Design of this section is still open —
 * no health data is shown for now." Matching the design here means
 * reproducing that honesty, not inventing label-free sanity checks the real
 * pipeline doesn't expose yet (no sanity-check endpoint exists under
 * /eval-runs — see ai/eval/cli.py's `sanity` command, which is CLI-only today).
 */
export default function PipelineHealthTodo() {
  return (
    <section id="sec-f" style={{ animation: 'fade-up .5s ease-out .24s both' }}>
      <div className="glass" style={{ padding: '20px 22px 22px' }}>
        <h2 style={{ margin: '0 0 16px', fontSize: 22, fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>Pipeline health</h2>
        <div style={{
          display: 'grid', placeItems: 'center', gap: 12, padding: '54px 20px', borderRadius: 12,
          background: 'rgba(255,255,255,0.018)', border: '1px dashed rgba(255,255,255,0.12)', textAlign: 'center',
        }}>
          <span className="font-display" style={{ fontSize: 'clamp(44px,9vw,86px)', lineHeight: 0.9, letterSpacing: '0.04em', color: '#ffb199' }}>TODO</span>
          <p style={{ margin: 0, maxWidth: '46ch', fontSize: 12.5, lineHeight: 1.6, fontWeight: 600, color: 'var(--text-muted)' }}>
            Label-free sanity checks (event rate, duplicate detection, round-break plausibility) run today only via <code style={{ fontFamily: 'var(--mono)', color: 'var(--accent-hover)' }}>python -m eval.cli sanity</code> —
            no API surface exists yet to show them here.
          </p>
        </div>
      </div>
    </section>
  );
}
