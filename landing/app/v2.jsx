// app/v2.jsx — Fightlytics v2: scroll-driven product story
const { useState: u2S, useEffect: u2E, useRef: u2R } = React;

/* ---------- scroll engine: one rAF loop, many subscribers ---------- */
const X_SUBS = new Set();
let xRaf = 0;
const xRun = () => { xRaf = 0; X_SUBS.forEach((f) => f()); };
window.addEventListener('scroll', () => { if (!xRaf) xRaf = requestAnimationFrame(xRun); }, { passive: true });
window.addEventListener('resize', xRun);
function pinProgress(el) {
  const r = el.getBoundingClientRect();
  const d = r.height - window.innerHeight;
  return d <= 0 ? 0 : Math.min(1, Math.max(0, -r.top / d));
}
function useScrollFx(ref, fn) {
  u2E(() => {
    const sub = () => {
      const el = ref.current; if (!el) return;
      const p = pinProgress(el);
      el.style.setProperty('--p', p.toFixed(4));
      fn && fn(p, el);
    };
    X_SUBS.add(sub); sub();
    return () => X_SUBS.delete(sub);
  }, []);
}
const ease = (t) => 1 - Math.pow(1 - t, 3);

/* ---------- nav ---------- */
function XNav() {
  return (
    <nav className="x-nav">
      <div className="x-nav-in">
        <a href="#top" className="x-nav-brand"><LogoLockup size={26} wordSize={19} /></a>
        <div className="x-nav-links">
          <a href="#numbers">Numbers</a>
          <a href="#capabilities">Capabilities</a>
          <a href="#compare">Compare</a>
        </div>
        <a href="#start" className="x-pill sm">Get early access</a>
      </div>
    </nav>
  );
}

/* ---------- hero: headline hands off to the product ---------- */
const AUDIENCE = ['coaches.', 'analysts.', 'broadcasters.', 'fighters.'];
function XHero() {
  const ref = u2R(null);
  const [k, setK] = u2S(0);
  u2E(() => { const id = setInterval(() => setK((v) => (v + 1) % AUDIENCE.length), 2200); return () => clearInterval(id); }, []);
  useScrollFx(ref, (p, el) => { el.classList.toggle('past', p > 0.28); });
  u2E(() => {
    const fit = () => {
      const el = ref.current; if (!el) return;
      const copy = el.querySelector('.x-hero-copy'), media = el.querySelector('.x-hero-media');
      if (!copy || !media) return;
      const vh = window.innerHeight;
      const copyBottom = copy.offsetTop + copy.offsetHeight + 28;
      const mediaTop = (vh - media.offsetHeight) / 2;
      const peek = Math.min(vh * 0.3, 220);
      const drop = Math.max(copyBottom - mediaTop, vh - peek - mediaTop);
      el.style.setProperty('--x-drop', Math.max(0, drop) + 'px');
    };
    fit();
    window.addEventListener('resize', fit);
    const ro = new ResizeObserver(fit); ro.observe(ref.current);
    ref.current.querySelectorAll('.x-hero-copy, .x-hero-media').forEach((n) => ro.observe(n));
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
    return () => { window.removeEventListener('resize', fit); ro.disconnect(); };
  }, []);
  return (
    <section className="x-hero" ref={ref} id="top">
      <div className="x-sticky">
        <div className="x-hero-copy">
          <div className="x-eyebrow"><GloveGlyph size={15} />Automatic MMA fight intelligence</div>
          <h1 className="x-h1">Every strike.<br />Counted.</h1>
          <p className="x-hero-sub">Frame-by-frame fight analytics, built for <span className="x-rot"><span key={k}>{AUDIENCE[k]}</span></span></p>
          <div className="x-hero-ctas">
            <a href="#start" className="x-pill">Upload a fight</a>
            <a href="#numbers" className="x-link">See the numbers <span className="material-symbols-outlined">arrow_forward</span></a>
          </div>
        </div>
        <div className="x-hero-media"><AnalysisMockup tickerSpeed={1800} /></div>
      </div>
    </section>
  );
}

/* ---------- statement: words light up with scroll ---------- */
const STATEMENT = 'Fightlytics watches the whole fight. *Every jab, every takedown, every second on the mat* — and turns it into data you can build a gameplan on.';
function XStatement() {
  const ref = u2R(null);
  useScrollFx(ref);
  let hot = false;
  const words = STATEMENT.split(' ').map((w) => {
    if (w.startsWith('*')) hot = true;
    const out = { w: w.replace(/\*/g, ''), hot };
    if (w.endsWith('*')) hot = false;
    return out;
  });
  return (
    <section className="x-statement" ref={ref} style={{ '--n': words.length }}>
      <div className="x-sticky x-center">
        <p className="x-state-p">
          {words.map((o, i) => <span key={i} className={o.hot ? 'hot' : ''} style={{ '--i': i }}>{o.w} </span>)}
        </p>
      </div>
    </section>
  );
}

/* ---------- stats reel: pinned, scrubbed counters ---------- */
const REEL = [
  { from: 500, to: 82, dec: 0, unit: 'ms', pre: 'Just', label: 'Feed to on-air graphic', note: 'The stat hits the screen before the replay does.' },
  { from: 0, to: 98, dec: 0, unit: '%', pre: 'Up to', label: 'Strike detection accuracy', note: 'Jabs, hooks, low kicks and knees — classified on their own.' },
  { from: 0, to: 60, dec: 0, unit: 'fps', pre: '', label: 'Real-time throughput', note: 'Both fighters tracked through cuts, clinches and scrambles.' },
  { from: 0, to: 2.4, dec: 1, unit: 'M', pre: '', label: 'Frames analyzed', note: 'And counting, every fight night.' },
];
function XReel() {
  const ref = u2R(null);
  const numRef = u2R(null);
  const [idx, setIdx] = u2S(0);
  const idxRef = u2R(0);
  useScrollFx(ref, (p, el) => {
    const seg = Math.min(REEL.length - 1, Math.floor(p * REEL.length));
    const local = Math.min(1, (p * REEL.length - seg) / 0.55);
    const s = REEL[seg];
    if (numRef.current) numRef.current.textContent = (s.from + (s.to - s.from) * ease(local)).toFixed(s.dec);
    el.style.setProperty('--local', Math.min(1, p * REEL.length - seg).toFixed(4));
    if (seg !== idxRef.current) { idxRef.current = seg; setIdx(seg); }
  });
  u2E(() => { xRun(); }, [idx]);
  const s = REEL[idx];
  return (
    <section className="x-reel" ref={ref} id="numbers">
      <div className="x-sticky">
        <div className="x-wrap x-reel-grid">
          <div className="x-reel-head">
            <div className="x-eyebrow"><GloveGlyph size={15} />By the numbers</div>
            <ol className="x-reel-rail">
              {REEL.map((r, i) => (
                <li key={i} className={i === idx ? 'on' : i < idx ? 'done' : ''}>
                  <span className="bar"><i></i></span>{r.label}
                </li>
              ))}
            </ol>
          </div>
          <div className="x-reel-stat" key={idx}>
            {s.pre && <div className="x-reel-pre">{s.pre}</div>}
            <div className="x-reel-num tnum"><span ref={numRef}>{s.from.toFixed(s.dec)}</span><small>{s.unit}</small></div>
            <div className="x-reel-label">{s.label}</div>
            <p className="x-reel-note">{s.note}</p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------- capabilities: pinned horizontal gallery ---------- */
function VisTracking() {
  return (
    <div className="x-vis x-vis-video">
      <div className="fbox red" style={{ left: '12%', top: '18%', width: '30%', height: '66%' }}><span className="tag">FIGHTER_RED</span><span className="conf">0.98</span></div>
      <div className="fbox blue" style={{ right: '12%', top: '14%', width: '31%', height: '70%' }}><span className="tag">FIGHTER_BLUE</span><span className="conf">0.97</span></div>
    </div>
  );
}
function VisEvents() {
  const rows = [
    { t: 'strike', f: 5821, d: '<b>fighter_blue</b> landed a jab', uid: 1 },
    { t: 'kick', f: 5856, d: '<b>fighter_red</b> threw a low_kick', uid: 2 },
    { t: 'grapple', f: 5857, d: 'State → <b>GRAPPLING</b>', uid: 3 },
  ];
  return <div className="x-vis x-vis-list">{rows.map((r) => <EventRow ev={r} key={r.uid} />)}</div>;
}
function VisTimeline() {
  const ticks = [3, 7, 9, 14, 18, 22, 23, 29, 31, 38, 44, 47, 52, 58, 61, 63, 70, 74, 79, 83, 88, 91, 96];
  const grap = [[24, 30], [64, 72]];
  return (
    <div className="x-vis x-vis-tl">
      <div className="x-tl-rounds"><span>R1</span><span>R2</span><span>R3</span></div>
      <div className="x-tl-track">
        {grap.map(([a, b], i) => <i key={'g' + i} className="g" style={{ left: a + '%', width: (b - a) + '%' }}></i>)}
        {ticks.map((t, i) => <i key={i} className={i % 5 === 2 ? 'k' : 's'} style={{ left: t + '%' }}></i>)}
        <b className="x-tl-head" style={{ left: '61%' }}></b>
      </div>
      <div className="x-tl-legend"><span className="s">Strike</span><span className="k">Kick</span><span className="g">Grapple</span></div>
    </div>
  );
}
function VisReport() {
  const rows = [['Sig. strikes', 42, 31], ['Takedowns', 3, 1], ['Control time', '4:12', '1:05']];
  const n = (v) => (typeof v === 'number' ? v : parseInt(v) * 60 + parseInt(v.split(':')[1]));
  return (
    <div className="x-vis x-vis-rep">
      {rows.map(([l, a, b]) => {
        const pa = n(a) / (n(a) + n(b)) * 100;
        return (
          <div className="x-rep-row" key={l}>
            <div className="x-rep-top"><span className="tnum">{a}</span><em>{l}</em><span className="tnum">{b}</span></div>
            <div className="x-rep-bar"><i style={{ width: pa + '%' }}></i></div>
          </div>
        );
      })}
    </div>
  );
}
const CAPS = [
  { k: 'Detection', h: 'Strikes and grappling, classified on their own.', vis: <VisEvents /> },
  { k: 'Tracking', h: 'Both fighters locked on. Every frame.', vis: <VisTracking /> },
  { k: 'Timeline', h: 'Every exchange, one click from the frame it happened.', vis: <VisTimeline /> },
  { k: 'Lab report', h: 'Round-by-round. Fighter-by-fighter.', vis: <VisReport /> },
];
function XGallery() {
  const ref = u2R(null);
  const trackRef = u2R(null);
  const [act, setAct] = u2S(0);
  const actRef = u2R(0);
  useScrollFx(ref, (p) => {
    const t = trackRef.current; if (!t) return;
    const max = t.scrollWidth - t.parentElement.clientWidth;
    t.style.transform = `translate3d(${-Math.max(0, max) * ease(p)}px,0,0)`;
    const head = ref.current && ref.current.querySelector('.x-gal-head');
    if (head) ref.current.style.setProperty('--x-head', head.offsetHeight + 'px');
    const a = Math.min(CAPS.length - 1, Math.round(p * (CAPS.length - 1)));
    if (a !== actRef.current) { actRef.current = a; setAct(a); }
  });
  return (
    <section className="x-gallery" ref={ref} id="capabilities">
      <div className="x-sticky x-gal-stage">
        <div className="x-wrap x-gal-head">
          <div className="x-eyebrow"><GloveGlyph size={15} />Capabilities</div>
          <h2 className="x-h2">The whole fight,<br />broken down.</h2>
        </div>
        <div className="x-gal-viewport">
          <div className="x-gal-track" ref={trackRef}>
            {CAPS.map((c, i) => (
              <article className={'x-card' + (i === act ? ' on' : '')} key={i}>
                <div className="x-card-copy"><div className="x-card-k">{c.k}</div><h3>{c.h}</h3></div>
                {c.vis}
              </article>
            ))}
          </div>
        </div>
        <div className="x-gal-dots">{CAPS.map((_, i) => <i key={i} className={i === act ? 'on' : ''}></i>)}</div>
      </div>
    </section>
  );
}

/* ---------- the duo: Studio vs Broadcast ---------- */
const DUO_ROWS = [
  ['Input', 'Any fight video', 'SRT · NDI · SDI feed'],
  ['Delivered', 'Post-fight', '82 ms, live'],
  ['Frame rate', '25 fps', '60 fps'],
  ['Detection accuracy', '98%', '97.4%'],
  ['Output', 'Lab report + clips', 'Lower thirds + JSON'],
];
function XDuo() {
  return (
    <section className="x-duo" id="compare">
      <div className="x-wrap">
        <div className="x-duo-head reveal">
          <h2 className="x-h2">Two ways to see the fight.</h2>
        </div>
        <div className="x-duo-grid">
          {[
            { name: 'Studio', who: 'For coaches, analysts and fighters', line: 'Upload the tape. Get the whole breakdown.', href: 'https://app.fightlytics.com', cta: 'Try Studio', ext: true },
            { name: 'Broadcast', who: 'For networks and promotions', line: 'Live feed in. On-air graphics out.', href: 'Fightlytics Broadcast.html', cta: 'Get notified', soon: true },
          ].map((d, c) => (
            <div className={'x-duo-col reveal d' + (c + 1) + (d.soon ? ' soon' : '')} key={d.name}>
              {d.soon && <div className="x-soon">Coming soon</div>}
              <div className={'x-duo-mark' + (c ? ' alt' : '')}><GloveMark size={64} /></div>
              <div className="x-duo-name"><span>fightlytics</span> {d.name}</div>
              <div className="x-duo-who">{d.who}</div>
              <p className="x-duo-line">{d.line}</p>
              <a className={'x-pill' + (d.soon ? ' ghost' : '')} href={d.href} {...(d.ext ? { target: '_blank', rel: 'noopener' } : {})}>{d.cta}</a>
              <dl className="x-duo-specs">
                {DUO_ROWS.map((r) => (
                  <div key={r[0]}><dt>{r[0]}</dt><dd>{r[c + 1]}</dd></div>
                ))}
              </dl>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- final CTA ---------- */
function XFinal() {
  const ref = u2R(null);
  useScrollFx(ref);
  return (
    <section className="x-final" ref={ref} id="start">
      <div className="x-sticky x-center">
        <div className="x-final-in">
          <LogoStack size={56} wordSize={32} />
          <h2 className="x-final-h">Stop charting fights<br /><span>by hand.</span></h2>
          <p className="x-final-p">Upload your first fight free. Early access is opening now.</p>
          <form className="x-signup" onSubmit={(e) => e.preventDefault()}>
            <input type="email" placeholder="you@gym.com" aria-label="Email" />
            <button className="x-pill" type="submit">Request early access</button>
          </form>
          <div className="x-final-note">No card required · Your footage stays private</div>
        </div>
      </div>
    </section>
  );
}
function XFooter() {
  return (
    <footer className="x-footer">
      <div className="x-wrap x-foot-in">
        <LogoLockup size={22} wordSize={16} />
        <span>© 2026 Fightlytics</span>
        <div className="x-foot-links"><a href="#numbers">Numbers</a><a href="#capabilities">Capabilities</a><a href="Fightlytics Broadcast.html">Broadcast</a><a href="#">Privacy</a></div>
      </div>
    </footer>
  );
}

function XApp() {
  u2E(() => {
    const obs = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); obs.unobserve(e.target); } }), { threshold: 0.15 });
    document.querySelectorAll('.reveal').forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);
  return (
    <>
      <XNav />
      <XHero />
      <XStatement />
      <XReel />
      <XGallery />
      <XDuo />
      <XFinal />
      <XFooter />
    </>
  );
}
ReactDOM.createRoot(document.getElementById('root')).render(<XApp />);
