import { useMemo, useState } from 'react';
import type { LabelEvent } from '../../hooks/useLabelledEvents';
import type { Fight } from '../../types/Fight';
import { TOOL_GROUPS } from '../../components/annotate/taxonomy';
import { FAMILY_BY_ACTION, STRIKE_FAMILIES } from '../../utils/trainingDataTaxonomy';
import { fightLabel } from '../../utils/fightLabel';

const MIN_EXAMPLES = 25;
type View = 'Palette actions' | 'Training classes' | 'By fight';
const VIEWS: View[] = ['Palette actions', 'Training classes', 'By fight'];

// One ink ramp, strongest at the head: these are human label counts, so no brand orange and no corner colours.
const ZONE_COLORS: Record<string, string> = { head: 'var(--text-primary)', body: 'rgba(242,241,238,0.55)', leg: 'rgba(242,241,238,0.3)', ns: 'rgba(242,241,238,0.14)' };
const ZONE_LABELS: [string, string][] = [['head', 'head'], ['body', 'body'], ['leg', 'leg'], ['ns', 'non-specific']];

const STATE_ACTIONS: Record<string, 'STRIKING' | 'CLINCH' | 'GROUND'> = {
  state_striking: 'STRIKING', state_clinch: 'CLINCH', state_ground: 'GROUND',
};
const STATE_C: Record<string, string> = {
  STRIKING: 'var(--state-striking)', CLINCH: 'var(--state-clinch)', GROUND: 'var(--state-ground)', NONE: 'var(--text-disabled)',
};

function Pill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" className={'pill' + (active ? ' active' : '')} onClick={onClick} style={{ padding: '5px 11px', fontSize: 11.5 }}>{children}</button>;
}

/** One horizontal count bar with an optional R/B split strip beneath it. */
function BarRow({ label, n, max, share, r, b, low }: { label: string; n: number; max: number; share?: string; r?: number; b?: number; low?: boolean }) {
  const w = max > 0 ? (n / max) * 100 : 0;
  const total = (r ?? 0) + (b ?? 0);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(112px,1.1fr) minmax(120px,2fr) 64px', gap: 10, alignItems: 'center', padding: '6px 10px', borderRadius: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
        <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
        {low && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, padding: '1px 6px', borderRadius: 5, background: 'color-mix(in srgb, var(--warn) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--warn) 30%, transparent)', color: 'var(--warn)', fontSize: 10.5, fontWeight: 500 }}>Low</span>
        )}
      </div>
      <div>
        <div style={{ position: 'relative', height: 8 }}>
          <div style={{ position: 'absolute', inset: '0 auto 0 0', width: `${w}%`, minWidth: n ? 3 : 0, background: 'var(--text-primary)', borderRadius: 2 }} />
        </div>
        {total > 0 && (
          <div style={{ display: 'flex', gap: 2, height: 4, marginTop: 3, width: `${w}%`, minWidth: n ? 3 : 0 }} title="Corner = the overlay box the labeller clicked (a track slot), not a named fighter.">
            <span style={{ flex: r || 0.001, background: 'var(--f-red)', borderRadius: 1 }} />
            <span style={{ flex: b || 0.001, background: 'var(--f-blue)', borderRadius: 1 }} />
          </div>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, justifyContent: 'flex-end', fontVariantNumeric: 'tabular-nums' }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, fontWeight: 500, color: 'var(--text-primary)' }}>{n}</span>
        {share && <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, fontWeight: 400, color: 'var(--text-muted)' }}>{share}</span>}
      </div>
    </div>
  );
}

interface ZonePanelProps {
  events: LabelEvent[];
  sel: string | null;
  onClear: () => void;
}

function ZonePanel({ events, sel, onClear }: ZonePanelProps) {
  const shown = sel ? events.filter((e) => FAMILY_BY_ACTION[e.action ?? ''] === sel) : events.filter((e) => FAMILY_BY_ACTION[e.action ?? ''] != null);
  const totals = ZONE_LABELS.map(([k, l]) => ({
    k, l, c: ZONE_COLORS[k],
    v: shown.filter((e) => (k === 'ns' ? e.target == null : e.target === k)).length,
  }));
  const grand = totals.reduce((s, t) => s + t.v, 0);
  const scale = Math.max(...totals.map((t) => t.v), 1);
  return (
    <div className="inner-tile" style={{ padding: '15px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <div className="label" style={{ flex: 1, minWidth: 0 }}>Target zone{sel ? ` · ${sel}` : ' · all families'}</div>
        {sel && <button type="button" className="btn-glass" style={{ padding: '4px 9px', fontSize: 11 }} onClick={onClear}>Clear</button>}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
        <span className="font-num" style={{ fontSize: 26, lineHeight: 1, color: 'var(--text-primary)' }}>{grand}</span>
        <span style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-muted)' }}>labels</span>
      </div>
      {totals.map((t) => (
        <div key={t.k} style={{ display: 'grid', gridTemplateColumns: '78px minmax(0,1fr) 30px', gap: 9, alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-muted)' }}>{t.l}</span>
          <div style={{ height: 8 }}>
            <div style={{ height: '100%', width: `${(t.v / scale) * 100}%`, minWidth: t.v ? 3 : 0, background: t.c, borderRadius: 2 }} />
          </div>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 500, textAlign: 'right', color: t.v ? 'var(--text-primary)' : 'var(--text-disabled)', fontVariantNumeric: 'tabular-nums' }}>{t.v || '—'}</span>
        </div>
      ))}
      <div style={{ marginTop: 12, paddingTop: 11, borderTop: '1px solid rgba(255,255,255,0.05)', fontSize: 11, lineHeight: 1.55, fontWeight: 500, color: 'var(--text-muted)' }}>
        {sel
          ? `Only the zones ${sel} can land in carry a count — the rest are not part of the taxonomy.`
          : 'Click a strike row to filter this panel to one family.'}
      </div>
    </div>
  );
}

interface StateMixProps {
  events: LabelEvent[];
}

function Stack({ segs, height }: { segs: { name: string; v: number; c: string }[]; height: number }) {
  const total = segs.reduce((s, x) => s + x.v, 0) || 1;
  return (
    <div style={{ display: 'flex', gap: 2, height, borderRadius: 2, overflow: 'hidden' }}>
      {segs.filter((s) => s.v > 0).map((s, i) => (
        <div key={i} title={`${s.v} · ${((s.v / total) * 100).toFixed(0)}% · ${s.name}`} style={{ flex: s.v, background: s.c, borderRadius: 1 }} />
      ))}
    </div>
  );
}

/** Attributes each strike to the fight state active at its frame — the
 * latest state_* mark in the same fight at or before that frame, or "no
 * state yet" if none exists. Purely derived from real label events, the
 * same technique AnnotationTimeline uses to draw the STATE lane. */
function StateMix({ events }: StateMixProps) {
  const { overall, rows } = useMemo(() => {
    const byFight = new Map<number, LabelEvent[]>();
    events.forEach((e) => {
      if (!byFight.has(e.fight.id)) byFight.set(e.fight.id, []);
      byFight.get(e.fight.id)!.push(e);
    });
    const marksByFight = new Map<number, { frame: number; state: 'STRIKING' | 'CLINCH' | 'GROUND' }[]>();
    byFight.forEach((evs, fightId) => {
      const marks = evs
        .filter((e) => STATE_ACTIONS[e.action ?? ''])
        .map((e) => ({ frame: e.frame, state: STATE_ACTIONS[e.action!] }))
        .sort((a, b) => a.frame - b.frame);
      marksByFight.set(fightId, marks);
    });

    const stateFor = (e: LabelEvent): 'STRIKING' | 'CLINCH' | 'GROUND' | 'NONE' => {
      const marks = marksByFight.get(e.fight.id) ?? [];
      let cur: 'STRIKING' | 'CLINCH' | 'GROUND' | 'NONE' = 'NONE';
      for (const m of marks) {
        if (m.frame > e.frame) break;
        cur = m.state;
      }
      return cur;
    };

    const famRows = STRIKE_FAMILIES.map((fam) => ({ name: fam, STRIKING: 0, CLINCH: 0, GROUND: 0, NONE: 0 }));
    const famIndex = new Map<string, number>(famRows.map((r, i) => [r.name, i]));
    const ov = { STRIKING: 0, CLINCH: 0, GROUND: 0, NONE: 0 };

    events.forEach((e) => {
      const fam = FAMILY_BY_ACTION[e.action ?? ''];
      if (!fam) return;
      const st = stateFor(e);
      ov[st]++;
      const row = famRows[famIndex.get(fam)!];
      row[st]++;
    });

    return { overall: ov, rows: famRows.filter((r) => r.STRIKING + r.CLINCH + r.GROUND + r.NONE > 0) };
  }, [events]);

  const segsFor = (r: { STRIKING: number; CLINCH: number; GROUND: number; NONE: number }) => [
    { name: 'STRIKING', v: r.STRIKING, c: STATE_C.STRIKING },
    { name: 'CLINCH', v: r.CLINCH, c: STATE_C.CLINCH },
    { name: 'GROUND', v: r.GROUND, c: STATE_C.GROUND },
    { name: 'no state yet', v: r.NONE, c: STATE_C.NONE },
  ];

  return (
    <div className="inner-tile" style={{ padding: '15px 16px' }}>
      <div className="label" style={{ marginBottom: 11 }}>Strikes by fight state</div>
      <div style={{ display: 'grid', gridTemplateColumns: '62px 1fr', gap: 9, alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 11.5, fontWeight: 600, color: 'var(--text-primary)' }}>Overall</span>
        <Stack height={16} segs={segsFor(overall)} />
      </div>
      {rows.map((r) => (
        <div key={r.name} style={{ display: 'grid', gridTemplateColumns: '62px 1fr', gap: 9, alignItems: 'center', marginBottom: 4 }}>
          <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)' }}>{r.name}</span>
          <Stack height={9} segs={segsFor(r)} />
        </div>
      ))}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', marginTop: 10 }}>
        {(['STRIKING', 'CLINCH', 'GROUND'] as const).map((s) => (
          <span key={s} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5, fontWeight: 500, color: 'var(--text-secondary)' }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: STATE_C[s] }} />{s[0] + s.slice(1).toLowerCase()}
          </span>
        ))}
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5, fontWeight: 500, color: 'var(--text-secondary)' }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: STATE_C.NONE }} />No state yet
        </span>
      </div>
    </div>
  );
}

interface AnnotatedEventsProps {
  events: LabelEvent[];
  fights: Fight[];
}

export default function AnnotatedEvents({ events, fights }: AnnotatedEventsProps) {
  const [view, setView] = useState<View>('Palette actions');
  const [sel, setSel] = useState<string | null>(null);

  const strikes = events.filter((e) => e.action != null);
  const otherTotal = strikes.filter((e) => FAMILY_BY_ACTION[e.action!] == null).length;
  const strikeTotal = strikes.length - otherTotal;

  const paletteRows = useMemo(() => {
    const counts = new Map<string, { n: number; r: number; b: number }>();
    events.forEach((e) => {
      const a = e.action ?? '';
      const cur = counts.get(a) ?? { n: 0, r: 0, b: 0 };
      cur.n++;
      if (e.displayCorner === 0) cur.r++;
      else if (e.displayCorner === 1) cur.b++;
      counts.set(a, cur);
    });
    return TOOL_GROUPS.map((g) => ({
      group: g.group,
      rows: g.items.map((it) => ({ action: it.action, name: it.name, needsFighter: it.needsFighter, ...(counts.get(it.action) ?? { n: 0, r: 0, b: 0 }) })),
    }));
  }, [events]);
  const paletteMax = Math.max(...paletteRows.flatMap((g) => g.rows.map((r) => r.n)), 1);

  const famRows = useMemo(() => {
    const counts = new Map<string, { n: number; r: number; b: number }>();
    events.forEach((e) => {
      const fam = FAMILY_BY_ACTION[e.action ?? ''];
      if (!fam) return;
      const cur = counts.get(fam) ?? { n: 0, r: 0, b: 0 };
      cur.n++;
      if (e.displayCorner === 0) cur.r++;
      else if (e.displayCorner === 1) cur.b++;
      counts.set(fam, cur);
    });
    return STRIKE_FAMILIES.map((fam) => ({ name: fam, ...(counts.get(fam) ?? { n: 0, r: 0, b: 0 }) }));
  }, [events]);
  const famMax = Math.max(...famRows.map((r) => r.n), 1);

  const byFight = useMemo(() => {
    const perFight = fights.map((f) => {
      const counts = new Map<string, number>();
      events.filter((e) => e.fight.id === f.id).forEach((e) => {
        const fam = FAMILY_BY_ACTION[e.action ?? ''] ?? e.action ?? 'other';
        counts.set(fam, (counts.get(fam) ?? 0) + 1);
      });
      const rows = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
      return { fight: f, rows };
    });
    const gmax = Math.max(...perFight.flatMap((f) => f.rows.map((r) => r[1])), 1);
    return { perFight, gmax };
  }, [events, fights]);

  return (
    <section id="sec-b" style={{ animation: 'fade-up .5s ease-out .08s both' }}>
      <div className="glass" style={{ padding: '20px 22px 22px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 260px', minWidth: 0 }}>
            <h2 className="font-display" style={{ margin: 0, fontSize: 24, lineHeight: 1.05, color: 'var(--text-primary)' }}>Annotated events</h2>
            <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text-muted)', marginTop: 4 }}>
              {strikeTotal} strikes · {otherTotal} other events · {fights.length} labelled fight{fights.length === 1 ? '' : 's'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 4, padding: 3, borderRadius: 8, background: 'var(--surface-glass)', border: '1px solid var(--border-glass)' }}>
            {VIEWS.map((v) => <Pill key={v} active={view === v} onClick={() => setView(v)}>{v}</Pill>)}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '8fr 4fr', gap: 22, alignItems: 'start' }}>
          <div style={{ minWidth: 0 }}>
            {view === 'Palette actions' && (
              <div style={{ overflowX: 'auto' }}>
                <div style={{ minWidth: 560 }}>
                  {paletteRows.map((g) => (
                    <div key={g.group} style={{ marginBottom: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 10px 5px' }}>
                        <span style={{ fontSize: 11.5, fontWeight: 500, color: 'var(--text-muted)' }}>{g.group}</span>
                        <span style={{ flex: 1, height: 1, background: 'rgba(255,255,255,0.05)' }} />
                      </div>
                      {g.rows.map((row) => {
                        const fam = FAMILY_BY_ACTION[row.action];
                        const on = fam != null && fam === sel;
                        return (
                          <div
                            key={row.action}
                            onClick={() => fam && setSel(on ? null : fam)}
                            style={{
                              cursor: fam ? 'pointer' : 'default', borderRadius: 6,
                              background: on ? 'rgba(255,255,255,0.06)' : 'transparent',
                              boxShadow: on ? 'inset 0 0 0 1px var(--border-strong)' : 'none',
                              opacity: sel && !on ? 0.45 : 1,
                            }}
                          >
                            <BarRow label={row.name} n={row.n} max={paletteMax} share={row.needsFighter ? `${strikeTotal ? Math.round((row.n / strikeTotal) * 100) : 0}%` : undefined} r={row.r} b={row.b} />
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {view === 'Training classes' && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 10 }}>
                  Collapsed to the eight export families. Rows under the {MIN_EXAMPLES}-example minimum carry a Low chip.
                </div>
                {famRows.map((f) => (
                  <div
                    key={f.name}
                    onClick={() => setSel(sel === f.name ? null : f.name)}
                    style={{
                      cursor: 'pointer', borderRadius: 6,
                      background: sel === f.name ? 'rgba(255,255,255,0.06)' : 'transparent',
                      boxShadow: sel === f.name ? 'inset 0 0 0 1px var(--border-strong)' : 'none',
                      opacity: sel && sel !== f.name ? 0.45 : 1,
                    }}
                  >
                    <BarRow label={f.name} n={f.n} max={famMax} share={`${strikeTotal ? Math.round((f.n / strikeTotal) * 100) : 0}%`} r={f.r} b={f.b} low={f.n < MIN_EXAMPLES} />
                  </div>
                ))}
              </div>
            )}

            {view === 'By fight' && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 10 }}>
                  Shared scale across every fight's panel.
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 11 }}>
                  {byFight.perFight.map(({ fight, rows }) => (
                    <div key={fight.id} className="inner-tile" style={{ padding: '12px 13px' }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 9, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {fightLabel(fight)}
                      </div>
                      {rows.map(([name, n]) => (
                        <div key={name} style={{ display: 'grid', gridTemplateColumns: '1fr 32px', gap: 8, alignItems: 'center', marginBottom: 5 }}>
                          <div>
                            <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--text-muted)', marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</div>
                            <div style={{ height: 6 }}>
                              <div style={{ height: '100%', width: `${(n / byFight.gmax) * 100}%`, background: 'var(--text-primary)', borderRadius: 2 }} />
                            </div>
                          </div>
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, fontWeight: 500, textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)' }}>{n}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, minWidth: 0 }}>
            <ZonePanel events={events} sel={sel} onClear={() => setSel(null)} />
            <StateMix events={events} />
          </div>
        </div>
      </div>
    </section>
  );
}
