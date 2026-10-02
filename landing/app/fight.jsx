// app/fight.jsx — one whole fight's pipeline output (window.FIGHT): pace per round, and strike types per corner.
const { useMemo: fMemo, useState: fState } = React;

const FAMILIES = ['Jab', 'Cross', 'Hook', 'Uppercut', 'Kick', 'Knee', 'Punch'];
function strikeFamily(a) {
  if (a.startsWith('jab')) return 'Jab';
  if (a.startsWith('cross')) return 'Cross';
  if (a.startsWith('hook')) return 'Hook';
  if (a.startsWith('uppercut')) return 'Uppercut';
  if (a.endsWith('kick')) return 'Kick';
  if (a.endsWith('knee')) return 'Knee';
  if (a.endsWith('punch')) return 'Punch';
  return null;
}
const clock = (secs) => `${Math.floor(secs / 60)}:${String(Math.floor(secs % 60)).padStart(2, '0')}`;
const BIN = 10; // seconds of round clock per bar

function FightLine() {
  const F = window.FIGHT;
  const strikes = fMemo(() => F.strikes.map(([f, c, a]) => {
    const r = F.rounds.find(([, s, e]) => f >= s && f <= e);
    return { f, c, a, fam: strikeFamily(a), round: r ? r[0] : null, at: r ? (f - r[1]) / F.fps : null };
  }).filter((s) => s.fam && s.round), []);
  // pace: strikes per corner in 10 s slices of each round's clock
  const bins = fMemo(() => {
    const out = [];
    F.rounds.forEach(([n, s, e]) => {
      const k = Math.ceil((e - s) / F.fps / BIN);
      for (let i = 0; i < k; i++) out.push({ round: n, i, f0: s + i * BIN * F.fps, f1: Math.min(e, s + (i + 1) * BIN * F.fps), n: [0, 0] });
    });
    strikes.forEach((st) => { const b = out.find((x) => x.round === st.round && x.i === Math.floor(st.at / BIN)); if (b) b.n[st.c] += 1; });
    return out;
  }, []);
  const [round, setRound] = fState(0);
  const [hover, setHover] = fState(null);

  const inRound = (s) => round === 0 || s.round === round;
  const tally = fMemo(() => {
    const t = { total: [0, 0] };
    strikes.filter(inRound).forEach((s) => {
      t[s.fam] = t[s.fam] || [0, 0];
      t[s.fam][s.c] += 1; t.total[s.c] += 1;
    });
    return t;
  }, [round]);
  const rows = FAMILIES.filter((k) => tally[k]);
  const peak = Math.max(1, ...rows.map((k) => Math.max(...tally[k])));
  const binPeak = Math.max(1, ...bins.map((b) => Math.max(...b.n)));
  const pct = (f) => ((f - 1) / F.frames) * 100;
  const tipAt = hover ? pct((hover.f0 + hover.f1) / 2) : 0;

  return (
    <div className="fight">
      <div className="fight-line-wrap">
        <div
          className="fight-line"
          onMouseLeave={() => setHover(null)}
          role="img"
          aria-label={`Strikes per 10 seconds across ${F.rounds.length} rounds: red corner ${tally.total[0]}, blue corner ${tally.total[1]}. Red above the line, blue below.`}
        >
          {F.rounds.map(([n, s, e]) => (
            <div key={n} className={'fl-round' + (round === 0 || round === n ? ' on' : '')} style={{ left: pct(s) + '%', width: pct(e) - pct(s) + '%' }}>
              <span className="mono">Round {n}</span>
            </div>
          ))}
          <div className="fl-mid" />
          <span className="fl-peak mono">{binPeak}</span>
          {bins.map((b) => (
            <div
              key={b.round + '-' + b.i}
              className={'fl-bin' + (inRound(b) ? '' : ' off') + (hover === b ? ' hot' : '')}
              style={{ left: pct(b.f0) + '%', width: pct(b.f1) - pct(b.f0) + '%' }}
              onMouseEnter={() => setHover(b)}
              onClick={() => setHover(b)}
            >
              {b.n[0] > 0 && <i className="c0" style={{ height: (b.n[0] / binPeak) * 46 + '%' }} />}
              {b.n[1] > 0 && <i className="c1" style={{ height: (b.n[1] / binPeak) * 46 + '%' }} />}
            </div>
          ))}
          {hover && (
            <div className={'fl-tip' + (tipAt > 70 ? ' flip' : '')} style={{ left: tipAt + '%' }}>
              <span className="mono">Round {hover.round}, {clock(hover.i * BIN)} to {clock(hover.i * BIN + (hover.f1 - hover.f0) / F.fps)}</span>
              <span className="tip-c c0">Red <b>{hover.n[0]}</b></span>
              <span className="tip-c c1">Blue <b>{hover.n[1]}</b></span>
            </div>
          )}
        </div>
        <div className="fl-axis mono">
          <span>0:00</span>
          <span>{clock(F.frames / F.fps)}</span>
        </div>
      </div>

      <div className="fight-tape">
        <div className="tape-head">
          <div className="tape-tabs" role="group" aria-label="Filter by round">
            {[0, ...F.rounds.map((r) => r[0])].map((n) => (
              <button key={n} type="button" aria-pressed={round === n} onClick={() => setRound(n)}>{n ? 'Round ' + n : 'All rounds'}</button>
            ))}
          </div>
          <div className="tape-totals">
            <div className="c0"><b className="mono">{tally.total[0]}</b><span>Red</span></div>
            <div className="c1"><b className="mono">{tally.total[1]}</b><span>Blue</span></div>
          </div>
        </div>
        <div className="tape-rows">
          {rows.map((k) => (
            <div className="tape-row" key={k}>
              <span className="mono n">{tally[k][0]}</span>
              <span className="bar l"><i className="c0" style={{ width: (tally[k][0] / peak) * 100 + '%' }} /></span>
              <span className="k">{k}</span>
              <span className="bar r"><i className="c1" style={{ width: (tally[k][1] / peak) * 100 + '%' }} /></span>
              <span className="mono n">{tally[k][1]}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { FightLine });
