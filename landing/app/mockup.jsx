// app/mockup.jsx — recreated Fight.AI analysis player + faux-live event feed
const { useState, useEffect, useRef } = React;

// Event color system from the design system
const EV = {
  strike:  { color: '#ff4d1c', icon: 'bolt' },
  kick:    { color: '#ff4d1c', icon: 'sports_martial_arts' },
  block:   { color: '#94a3b8', icon: 'shield' },
  grapple: { color: '#ff7043', icon: 'sports_kabaddi' },
  round:   { color: '#a3c900', icon: 'timer' },
  state:   { color: '#64748b', icon: 'radio_button_checked' },
};

// Scripted event stream (cycles). Frame numbers tick up to feel live.
const STREAM = [
  { t: 'kick',    f: 5256, d: '<b>fighter_blue</b> threw a low_kick' },
  { t: 'kick',    f: 5256, d: '<b>fighter_red</b> threw a low_kick' },
  { t: 'grapple', f: 5257, d: 'State → <b>GRAPPLING</b> · takedown by fighter_red' },
  { t: 'state',   f: 5493, d: 'Fight state changed to <b>STRIKING</b>' },
  { t: 'strike',  f: 5821, d: '<b>fighter_blue</b> landed a jab' },
  { t: 'block',   f: 6002, d: '<b>fighter_red</b> checked a leg kick' },
  { t: 'strike',  f: 6340, d: '<b>fighter_red</b> landed a right_hand' },
  { t: 'strike',  f: 6712, d: '<b>fighter_blue</b> landed a hook' },
  { t: 'round',   f: 7829, d: '<b>Round 1</b> ended' },
  { t: 'grapple', f: 8104, d: 'clinch broken by <b>fighter_blue</b>' },
  { t: 'round',   f: 9995, d: '<b>Round 2</b> started' },
];

function EventRow({ ev }) {
  const meta = EV[ev.t];
  return (
    <div className="ev" style={{ '--ev-color': meta.color }} key={ev.uid}>
      <div className="badge"><span className="material-symbols-outlined">{meta.icon}</span></div>
      <div style={{ minWidth: 0 }}>
        <div className="frame">Frame {ev.f}</div>
        <div className="desc" dangerouslySetInnerHTML={{ __html: ev.d }} />
      </div>
    </div>
  );
}

function AnalysisMockup({ tickerSpeed = 2000, live = true }) {
  const [rows, setRows] = useState(() =>
    [2, 1, 0].map((i) => ({ ...STREAM[i], uid: 'init' + i }))
  );
  const idx = useRef(3);
  const uid = useRef(100);

  useEffect(() => {
    if (!live) return;
    const id = setInterval(() => {
      const next = STREAM[idx.current % STREAM.length];
      idx.current += 1;
      uid.current += 1;
      setRows((r) => [{ ...next, uid: uid.current }, ...r].slice(0, 5));
    }, tickerSpeed);
    return () => clearInterval(id);
  }, [tickerSpeed, live]);

  return (
    <div className="mockup">
      <div className="mockup-bar">
        <div className="dotrow"><i style={{ background: '#ff5f57' }} /><i style={{ background: '#febc2e' }} /><i style={{ background: '#28c840' }} /></div>
        <span className="mockup-title">fightlytics — analysis player</span>
        <span className="mockup-badge"><span style={{ width: 5, height: 5, borderRadius: 9, background: '#ff4d1c', display: 'inline-block', boxShadow: '0 0 6px #ff4d1c' }} />Processing</span>
      </div>

      <div className="mockup-body">
        {/* video pane */}
        <div className="video-pane">
          <div className="video-placeholder"><div className="cage-floor" /></div>
          <div className="scanline" />

          <div className="hud">
            <span className="rec" />
            <span className="txt">DETECTING · 25 FPS</span>
          </div>

          {/* fighter overlay boxes */}
          <div className="fbox red" style={{ left: '14%', top: '24%', width: '24%', height: '58%' }}>
            <span className="tag">FIGHTER_RED</span>
            <span className="conf">0.98</span>
          </div>
          <div className="fbox blue" style={{ right: '16%', top: '20%', width: '25%', height: '62%' }}>
            <span className="tag">FIGHTER_BLUE</span>
            <span className="conf">0.97</span>
          </div>

          <div className="scorestrip">
            <span className="name">BATUR</span>
            <span className="clock">R2 · 04:49</span>
            <span className="name">STAMATOVIC</span>
          </div>
        </div>

        {/* side panel */}
        <div className="side">
          <div className="round-block">
            <div className="lbl">Active Round</div>
            <div className="val">ROUND 2</div>
          </div>

          <div className="stat-tiles">
            <div className="stat-tile">
              <div className="k">Sig. Strikes</div>
              <div className="v cyan">14<small> /22</small></div>
            </div>
            <div className="stat-tile">
              <div className="k">Grapple</div>
              <div className="v orange">00:04</div>
            </div>
          </div>

          <div className="feed">
            <div className="feed-head">
              <span className="lbl">Event Timeline</span>
              <div className="feed-pills">
                <span className="feed-pill on">All</span>
                <span className="feed-pill">Strikes</span>
              </div>
            </div>
            <div className="feed-list">
              {rows.map((r) => <EventRow ev={r} key={r.uid} />)}
            </div>
            <div className="feed-cta">View Full Lab Report</div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AnalysisMockup });
