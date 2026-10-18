// app/app.jsx — Fightlytics landing: the fight as the model sees it.
const { useEffect: aEffect, useState: aState } = React;

const APP_URL = 'https://app-fightlytics.duckdns.org';
const SIGN_IN = 'Sign in with Google';

// Umami custom events. Each stored property also counts against the free plan's monthly cap.
function track(name, data) {
  if (window.umami) window.umami.track(name, data);
}

function Nav() {
  return (
    <nav className="nav" aria-label="Main">
      <div className="nav-in">
        <a href="#top" className="nav-brand" aria-label="Fightlytics home"><LogoLockup size={26} wordSize={19} /></a>
        <div className="nav-links">
          <a href="#how">How it works</a>
          <a href="#fight">Output</a>
          <a href="#method">Method</a>
        </div>
        <a href={APP_URL} className="btn sm" data-umami-event="sign-in" data-umami-event-from="nav">{SIGN_IN}</a>
      </div>
    </nav>
  );
}

const STEPS = [
  {
    mode: 'detect', id: 'how',
    h: 'Two fighters, 17 points each.',
    p: 'A pose model finds both fighters in every frame and places 17 keypoints on each. The referee is filtered out.',
    aside: <p className="step-note">Hollow points are joints the pose model was unsure about.</p>,
  },
  {
    mode: 'corners',
    h: 'Red corner, blue corner, every frame.',
    p: 'Corners are read from glove tape and torso colour, not from which side of the cage a fighter is on.',
    aside: <div className="chips"><span className="chip c0">Red</span><span className="chip c1">Blue</span></div>,
  },
  {
    mode: 'strike',
    h: 'Read 1.2 seconds, name the strike.',
    p: 'The strike model reads both skeletons across a 1.2 second window, then names the shot and where it was aimed.',
    aside: (
      <div className="vocab">
        <div><span className="vocab-k">Type</span>{['jab', 'cross', 'hook', 'uppercut', 'kick', 'knee'].map((w) => <span className="chip" key={w}>{w}</span>)}</div>
        <div><span className="vocab-k">Target</span>{['head', 'body', 'leg'].map((w) => <span className="chip" key={w}>{w}</span>)}</div>
      </div>
    ),
  },
  {
    mode: 'log',
    h: 'Every strike, one click from its frame.',
    p: 'Each strike lands on the fight timeline with its fighter and frame number. Click one and the video jumps there.',
    aside: <p className="step-note">Try it: click a row in the log.</p>,
  },
];

function Story() {
  const [mode, setMode] = aState('full');
  // the layer is worked out from the scroll position each time, so a fast flick or a scroll back to the top
  // never leaves a stale layer behind
  aEffect(() => {
    const els = [...document.querySelectorAll('.story [data-mode]')];
    const nav = document.querySelector('.nav'), stage = document.querySelector('.story .stage');
    let raf = 0;
    const pick = () => {
      raf = 0;
      // wide: the section that holds the middle of the screen. Narrow: the replay is pinned on top, so the step
      // whose heading has risen past the middle of the free space below it
      const narrow = window.matchMedia('(max-width: 899px)').matches;
      const top = narrow ? nav.offsetHeight + stage.offsetHeight : 0;
      const line = (top + window.innerHeight) / 2;
      let m = els[0].dataset.mode;
      els.forEach((el) => { if ((narrow ? el.firstElementChild : el).getBoundingClientRect().top < line) m = el.dataset.mode; });
      setMode(m);
    };
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(pick); };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    // narrow: each step is sized to the screen space left below the pinned replay, so CSS needs the replay's height
    const ro = new ResizeObserver(() => { document.documentElement.style.setProperty('--pin-h', stage.offsetHeight + 'px'); onScroll(); });
    ro.observe(stage);
    pick();
    return () => { cancelAnimationFrame(raf); ro.disconnect(); window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll); };
  }, []);

  return (
    <section className="story" id="top">
      <div className="story-copy">
        <header className="hero" data-mode="full">
          <h1 className="h1">Every strike, logged to the frame.</h1>
          <p className="lede">Feed it fight video. Fightlytics tracks both fighters, reads the rounds and logs strikes by type, target and fighter.</p>
          <div className="hero-ctas">
            <a href={APP_URL} className="btn" data-umami-event="sign-in" data-umami-event-from="hero">{SIGN_IN}</a>
            <a href="#how" className="link">How it works <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span></a>
          </div>
        </header>
        {STEPS.map((s) => (
          <article className="step" data-mode={s.mode} id={s.id} key={s.mode}>
            <h2 className="h3">{s.h}</h2>
            <p className="body">{s.p}</p>
            {s.aside}
          </article>
        ))}
      </div>
      <div className="stage">
        <div className="stage-in">
          <ExchangeStage mode={mode} />
          <p className="stage-cap">Real data: 3.7 seconds of one fight, replayed from the pipeline&rsquo;s pose output. Strikes shown are hand-verified labels.</p>
        </div>
      </div>
    </section>
  );
}

function FightSection() {
  return (
    <section className="sec fight-sec" id="fight">
      <div className="wrap">
        <div className="sec-head reveal">
          <h2 className="h2">A whole fight on one line.</h2>
          <p className="body">Pipeline output for one three-round fight. Rounds come from the broadcast scoreboard, and walkouts, breaks and replays are left out of the count.</p>
        </div>
        <div className="reveal d1"><FightLine /></div>
        <p className="fight-key mono reveal d2"><span className="k0">Red corner, above the line</span><span className="k1">Blue corner, below</span><span>Each bar: strikes in 10 seconds of the round clock</span></p>
      </div>
    </section>
  );
}

const METHOD = [
  ['Label', 'Labellers mark each strike on the frame it happens, with the fighter, type and target.'],
  ['Verify', 'A QA pass accepts or rejects every label. Only accepted strikes are used for training.'],
  ['Measure', 'Each new model is scored on hand-labelled fights it never trained on.'],
];
function Method() {
  return (
    <section className="sec method" id="method">
      <div className="wrap method-grid">
        <h2 className="h2 method-h reveal">Trained only on strikes a person confirmed.</h2>
        <ol className="method-list">
          {METHOD.map(([k, p], i) => (
            <li className={'reveal d' + (i + 1)} key={k}>
              <span className="method-k">{k}</span>
              <p className="body">{p}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Live() {
  return (
    <section className="live" id="live" aria-labelledby="live-h">
      <div className="wrap live-in reveal">
        <span className="live-tag mono">Coming later</span>
        <h2 className="h3" id="live-h">Live broadcast feeds.</h2>
        <p className="body">Today Fightlytics works on recorded fights. A version that runs on a live feed, for broadcasters, is on the way.</p>
      </div>
    </section>
  );
}

function Final() {
  return (
    <section className="final" id="start">
      <div className="wrap final-in reveal">
        <LogoStack size={52} wordSize={28} />
        <h2 className="h1 final-h">Stop charting fights by hand.</h2>
        <p className="lede">Sign in with Google to browse analysed fights. Uploading is by invite.</p>
        <a href={APP_URL} className="btn" data-umami-event="sign-in" data-umami-event-from="final">{SIGN_IN}</a>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="footer">
      <div className="wrap foot-in">
        <LogoLockup size={20} wordSize={15} />
        <span>&copy; 2026 Fightlytics</span>
        <div className="foot-links"><a href="#how">How it works</a><a href="#fight">Output</a><a href="#method">Method</a></div>
      </div>
    </footer>
  );
}

function App() {
  aEffect(() => {
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
    }), { threshold: 0.15 });
    document.querySelectorAll('.reveal').forEach((el) => io.observe(el));
    // how far down people get; the first section is the pageview itself
    const seen = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) { track('section', { id: e.target.id }); seen.unobserve(e.target); }
    }), { threshold: 0.5 });
    document.querySelectorAll('main > section:not(:first-child)').forEach((el) => seen.observe(el));
    const pager = window.createPager();
    // the page renders after load, so the browser's own jump to #hash found nothing
    const target = location.hash && document.getElementById(location.hash.slice(1));
    if (target) pager ? pager.goTo(target, true) : target.scrollIntoView({ behavior: 'instant' });
    return () => { io.disconnect(); seen.disconnect(); if (pager) pager.destroy(); };
  }, []);
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <Nav />
      <main id="main">
        <Story />
        <FightSection />
        <Method />
        <Live />
        <Final />
      </main>
      <Footer />
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
