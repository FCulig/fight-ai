const TERMS: { term: string; def: string }[] = [
  { term: 'TP', def: 'true positive — a predicted strike matched to a real labelled one' },
  { term: 'FP', def: 'false positive — predicted, but no matching label (a false alarm)' },
  { term: 'FN', def: 'false negative — labelled, but never predicted (a miss)' },
  { term: 'P', def: 'precision — of everything predicted, the % that was real: TP ÷ (TP + FP)' },
  { term: 'R', def: 'recall — of everything real, the % that got predicted: TP ÷ (TP + FN)' },
  { term: 'F1', def: 'one number for both — the harmonic mean of precision and recall' },
  { term: 'IoU', def: 'intersection over union — how much a predicted round overlaps the labelled one' },
];

/**
 * Acronym key for TP/FP/FN/P/R/F1 (FixtureTable, HeadlineF1, VersionTrendChart)
 * and IoU (RoundsCheck). Spelled out once, always visible, rather than as
 * hover-only tooltips — every other honesty affordance on this page
 * (ProvenanceLine, the "Seeded — not verified" badges) stays on screen
 * instead of hiding behind an interaction, so the glossary follows the same
 * rule.
 */
export default function Glossary() {
  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', rowGap: 6, columnGap: 16,
      fontSize: 11, fontWeight: 600, color: 'var(--text-muted)',
      padding: '10px 12px', marginTop: 12, borderRadius: 8,
      background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-subtle)',
    }}>
      {TERMS.map(({ term, def }) => (
        <span key={term}>
          <code style={{ color: '#9fe8f4', fontWeight: 700 }}>{term}</code> {def}
        </span>
      ))}
    </div>
  );
}
