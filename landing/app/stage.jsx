// app/stage.jsx — replays window.EXCHANGE (real keypoints + verified strikes) on a canvas.
// `mode` peels the pipeline apart: detect (held pose, joints lock on) → corners (fight, coloured by corner)
// → strike (slowed, 1.2 s window) → log (strike timeline); `full` is the fight with everything on.
const { useEffect: sEffect, useRef: sRef, useState: sState } = React;

const BONES = [[5, 7], [7, 9], [6, 8], [8, 10], [5, 6], [5, 11], [6, 12], [11, 12], [11, 13], [13, 15], [12, 14], [14, 16]];
const HEAD = [0, 1, 2, 3, 4];
const MIN_CONF = 30;            // keypoint conf * 100 below this is a guess, not a joint
const HZ = 25;                  // samples per second (the strike model's rate)
const WINDOW = 15;              // ±15 samples = the model's 31-sample, 1.2 s window
const CORNER = ['#ef4444', '#4f93ea'];
const CORNER_RGB = [[239, 68, 68], [79, 147, 234]];
const INK_RGB = [242, 241, 238];
const CORNER_NAME = ['Red', 'Blue'];
const INK = '242,241,238';
const STRIP_H = 34;             // css px reserved for the sample strip
const LOOP_START = 10;          // skip the opening close-up, where the broadcast crops red's legs
const LOOP_HOLD = 0.7;          // seconds to rest on the last frame before restarting
const LOOP_FADE = 0.4;          // seconds for each half of the fade through black at the restart
const POSE_TWEEN = 0.8;         // seconds to glide from the live frame into the held pose
const POSE_LOCK = 1.1;          // seconds for all 17 joints to lock on, head to ankles
const POSE_ZOOM = 0.08;         // extra zoom on the held pose
const RING = 3;                 // a joint's lock-on ring fades over the next 3 joints
const LOCK_END = (17 + RING) / 17; // lock runs past the last joint so the ankles' rings fade too

const STRIKE_LABEL = {
  jab: 'Jab', cross: 'Cross', left_hook: 'Left hook', right_hook: 'Right hook',
  left_uppercut: 'Left uppercut', right_uppercut: 'Right uppercut',
  low_kick: 'Low kick', calf_kick: 'Calf kick', middle_kick: 'Middle kick', high_kick: 'Head kick', clinch_knee: 'Knee',
};
const familyOf = (a) => (a.includes('hook') ? 'hook' : a.includes('uppercut') ? 'uppercut' : a.endsWith('kick') ? 'kick' : a.endsWith('knee') ? 'knee' : a);

/* ---------- data prep ---------- */
function parseRow(r) {
  if (!r) return null;
  const kp = [];
  for (let j = 0; j < 17; j++) kp.push({ x: r[5 + j * 3], y: r[6 + j * 3], c: r[7 + j * 3] });
  return { box: r.slice(0, 4), conf: r[4], kp };
}
function holdGaps(arr) {
  const out = arr.slice();
  for (let i = 1; i < out.length; i++) if (!out[i]) out[i] = out[i - 1];
  for (let i = out.length - 2; i >= 0; i--) if (!out[i]) out[i] = out[i + 1];
  return out;
}
const mean = (pts) => pts.length ? { x: pts.reduce((s, p) => s + p.x, 0) / pts.length, y: pts.reduce((s, p) => s + p.y, 0) / pts.length } : null;
const conf = (kp, idx) => idx.map((j) => kp[j]).filter((p) => p.c >= MIN_CONF);
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

// the broadcast camera zooms and pans; a smoothed union box keeps both fighters framed
function buildCam(a, b) {
  const raw = a.map((p, i) => {
    const q = b[i];
    const x1 = Math.min(p.box[0], q.box[0]), y1 = Math.min(p.box[1], q.box[1]);
    const x2 = Math.max(p.box[2], q.box[2]), y2 = Math.max(p.box[3], q.box[3]);
    return [(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1];
  });
  const R = 10;
  return raw.map((_, i) => {
    const acc = [0, 0, 0, 0]; let ws = 0;
    for (let k = -R; k <= R; k++) {
      const s = raw[Math.min(raw.length - 1, Math.max(0, i + k))];
      const w = Math.exp(-(k * k) / (2 * (R / 2) ** 2));
      for (let d = 0; d < 4; d++) acc[d] += s[d] * w;
      ws += w;
    }
    return acc.map((v) => v / ws);
  });
}

// which limb threw it, and where it was aimed, read from the pose at the strike frame
function strikeGeometry(e, tracks) {
  const i = Math.round(e.si);
  const me = tracks[e.c][i].kp, op = tracks[1 - e.c][i].kp;
  const opHead = mean(conf(op, HEAD)) || mean(conf(op, [5, 6]));
  const opBody = mean(conf(op, [5, 6, 11, 12]));
  const opLeg = mean(conf(op, [13, 14])) || opBody;
  const target = e.t === 'head' ? opHead : e.t === 'leg' ? opLeg : opBody;
  const fam = familyOf(e.a);
  let chain;
  if (fam === 'kick' || fam === 'knee') {
    const hip = mean(conf(me, [11, 12])) || mean(conf(me, [5, 6]));
    const end = fam === 'kick' ? [15, 16] : [13, 14];
    const pick = end.map((j) => me[j]).map((p, k) => ({ p, k })).filter((o) => o.p.c >= MIN_CONF)
      .sort((u, v) => (hip ? dist(v.p, hip) - dist(u.p, hip) : 0))[0];
    const left = pick ? pick.k === 0 : true;
    chain = fam === 'kick' ? (left ? [11, 13, 15] : [12, 14, 16]) : (left ? [11, 13] : [12, 14]);
  } else if (e.a.startsWith('left_')) chain = [5, 7, 9];
  else if (e.a.startsWith('right_')) chain = [6, 8, 10];
  else {
    const aim = target || opHead;
    const d9 = me[9].c >= MIN_CONF && aim ? dist(me[9], aim) : Infinity;
    const d10 = me[10].c >= MIN_CONF && aim ? dist(me[10], aim) : Infinity;
    chain = d9 <= d10 ? [5, 7, 9] : [6, 8, 10];
  }
  return { chain, fam, targetKind: e.t };
}

// the held pose for the detect layer: the most confidently seen frame within 3 samples of a strike
function pickPose(tracks, events) {
  let best = null;
  events.forEach((e) => {
    for (let i = Math.round(e.si) - 3; i <= Math.round(e.si) + 3; i++) {
      if (i < LOOP_START || i >= tracks[0].length) continue;
      const cs = tracks.flatMap((tr) => tr[i].kp.map((p) => p.c));
      const score = cs.filter((c) => c >= 50).length * 100 + Math.min(...cs);
      if (!best || score > best.score) best = { i, score };
    }
  });
  return best ? best.i : LOOP_START;
}

function prepExchange(E) {
  const tracks = [holdGaps(E.red.map(parseRow)), holdGaps(E.blue.map(parseRow))];
  const events = E.events.map((ev) => {
    const e = { f: ev.f, c: ev.c, a: ev.a, t: ev.t, si: (ev.f - E.start) / E.step };
    return Object.assign(e, strikeGeometry(e, tracks));
  });
  return { n: tracks[0].length, start: E.start, step: E.step, tracks, cam: buildCam(tracks[0], tracks[1]), events, pose: pickPose(tracks, events) };
}

/* ---------- drawing ---------- */
const lerp = (a, b, t) => a + (b - a) * t;
const easeInOut = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
function poseAt(track, t) {
  const i0 = Math.floor(t), i1 = Math.min(track.length - 1, i0 + 1), a = t - i0;
  const p = track[i0], q = track[i1];
  return {
    box: p.box.map((v, k) => lerp(v, q.box[k], a)),
    conf: lerp(p.conf, q.conf, a),
    kp: p.kp.map((k0, j) => ({ x: lerp(k0.x, q.kp[j].x, a), y: lerp(k0.y, q.kp[j].y, a), c: Math.min(k0.c, q.kp[j].c) })),
  };
}
// glide between two poses; a joint only glides if it was seen at both ends, otherwise it waits for the lock-on
function mixPose(a, b, u) {
  return {
    box: a.box.map((v, k) => lerp(v, b.box[k], u)),
    conf: lerp(a.conf, b.conf, u),
    kp: b.kp.map((q, j) => {
      const p = a.kp[j], both = p.c >= MIN_CONF && q.c >= MIN_CONF;
      return { x: both ? lerp(p.x, q.x, u) : q.x, y: both ? lerp(p.y, q.y, u) : q.y, c: u < 1 ? Math.min(p.c, q.c) : q.c };
    }),
  };
}
const camAt = (S, t) => {
  const i0 = Math.floor(t), a = t - i0, c0 = S.cam[i0], c1 = S.cam[Math.min(S.n - 1, i0 + 1)];
  return c0.map((v, k) => lerp(v, c1[k], a));
};
// ink when k = 0, the corner's colour when k = 1
const tone = (c, k, alpha = 1) => `rgba(${INK_RGB.map((v, i) => Math.round(lerp(v, CORNER_RGB[c][i], k))).join(',')},${alpha})`;
function bracket(ctx, x1, y1, x2, y2, len) {
  ctx.beginPath();
  ctx.moveTo(x1, y1 + len); ctx.lineTo(x1, y1); ctx.lineTo(x1 + len, y1);
  ctx.moveTo(x2 - len, y1); ctx.lineTo(x2, y1); ctx.lineTo(x2, y1 + len);
  ctx.moveTo(x2, y2 - len); ctx.lineTo(x2, y2); ctx.lineTo(x2 - len, y2);
  ctx.moveTo(x1 + len, y2); ctx.lineTo(x1, y2); ctx.lineTo(x1, y2 - len);
  ctx.stroke();
}

// view: { t, mode, colour 0..1, strip 0..1, zoom, pose: null | { fromT, u (eased), lock 0..LOCK_END } }
function drawStage(ctx, S, W, H, view, dpr) {
  const { t, mode, colour, strip, zoom, pose } = view;
  ctx.clearRect(0, 0, W, H);
  const strikes = !pose && (mode === 'full' || mode === 'strike' || mode === 'log');
  const plotH = H - STRIP_H * dpr * strip;
  const cam = pose ? camAt(S, pose.fromT).map((v, k) => lerp(v, S.cam[S.pose][k], pose.u)) : camAt(S, t);
  const sc = Math.min((W * 0.84) / cam[2], (plotH * 0.8) / cam[3]) * zoom;
  const P = (p) => [W / 2 + (p.x - cam[0]) * sc, plotH / 2 + (p.y - cam[1]) * sc];
  const font = (px, w = 500) => `${w} ${px * dpr}px "JetBrains Mono", ui-monospace, monospace`;
  const poses = S.tracks.map((tr) => (pose ? mixPose(poseAt(tr, pose.fromT), tr[S.pose], pose.u) : poseAt(tr, t)));
  const locked = pose ? Math.min(17, Math.floor(pose.lock * 17 + 1e-6)) : 17; // joints revealed so far, in COCO order (head to ankles)

  poses.forEach((ps, c) => {
    const kp = ps.kp;
    const col = tone(c, colour);
    // tracking box, as corner brackets
    const [bx1, by1] = P({ x: ps.box[0], y: ps.box[1] });
    const [bx2, by2] = P({ x: ps.box[2], y: ps.box[3] });
    const x1 = Math.max(2 * dpr, bx1), y1 = Math.max(18 * dpr, by1), x2 = Math.min(W - 2 * dpr, bx2), y2 = Math.min(plotH - 4 * dpr, by2);
    ctx.lineWidth = 1.5 * dpr; ctx.strokeStyle = tone(c, colour, lerp(0.62, 0.75, colour));
    bracket(ctx, x1, y1, x2, y2, Math.min(x2 - x1, y2 - y1) * 0.12);
    ctx.font = font(11); ctx.fillStyle = col; ctx.textBaseline = 'bottom';
    ctx.fillText((colour > 0.5 ? CORNER_NAME[c].toUpperCase() : 'PERSON') + '  ' + (ps.conf / 100).toFixed(2), x1, y1 - 5 * dpr);

    // bones; while a pose is locking on, a bone turns solid once both of its joints are found
    ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.lineWidth = 2.4 * dpr;
    const solid = new Path2D(), ghost = new Path2D();
    BONES.forEach(([u, v]) => {
      if (kp[u].c < MIN_CONF || kp[v].c < MIN_CONF) return;
      const p = P(kp[u]), q = P(kp[v]);
      const path = u < locked && v < locked ? solid : ghost;
      path.moveTo(p[0], p[1]); path.lineTo(q[0], q[1]);
    });
    ctx.strokeStyle = tone(c, colour, lerp(0.85, 1, colour)); ctx.stroke(solid);
    ctx.strokeStyle = `rgba(${INK_RGB.join(',')},.26)`; ctx.stroke(ghost);

    // head
    const head = mean(conf(kp, HEAD));
    if (head) {
      const sh = kp[5].c >= MIN_CONF && kp[6].c >= MIN_CONF ? dist(kp[5], kp[6]) * sc : 40 * dpr;
      const [hx, hy] = P(head);
      ctx.strokeStyle = locked >= 5 ? tone(c, colour, lerp(0.85, 1, colour)) : `rgba(${INK_RGB.join(',')},.26)`;
      ctx.beginPath(); ctx.arc(hx, hy, Math.max(6 * dpr, Math.min(34 * dpr, sh * 0.3)), 0, Math.PI * 2); ctx.stroke();
    }

    // joints
    kp.forEach((p, j) => {
      const [x, y] = P(p);
      if (pose) {
        if (j >= locked) return;
        if (p.c >= MIN_CONF) { ctx.fillStyle = `rgba(${INK_RGB.join(',')},${0.4 + (p.c / 100) * 0.6})`; ctx.beginPath(); ctx.arc(x, y, 3.4 * dpr, 0, Math.PI * 2); ctx.fill(); }
        else if (x > 0 && x < W && y > 0 && y < plotH) { ctx.lineWidth = 1 * dpr; ctx.strokeStyle = `rgba(${INK_RGB.join(',')},.35)`; ctx.beginPath(); ctx.arc(x, y, 3.4 * dpr, 0, Math.PI * 2); ctx.stroke(); }
        const age = pose.lock * 17 - j; // how long ago this joint locked, in joints
        if (age < RING) {
          ctx.lineWidth = 1.2 * dpr; ctx.strokeStyle = `rgba(${INK_RGB.join(',')},${(1 - age / RING) * 0.9})`;
          ctx.beginPath(); ctx.arc(x, y, (4 + age * 6) * dpr, 0, Math.PI * 2); ctx.stroke();
        }
      } else if (j >= 5 && p.c >= MIN_CONF) {
        ctx.fillStyle = '#0f1012'; ctx.beginPath(); ctx.arc(x, y, 2.6 * dpr, 0, Math.PI * 2); ctx.fill();
        ctx.lineWidth = 1.4 * dpr; ctx.strokeStyle = col; ctx.stroke();
      }
    });
  });

  // strikes: flash the limb that threw it and ring the target
  let callout = null;
  if (strikes) {
    S.events.forEach((e) => {
      const ph = t - e.si;
      if (ph < -3 || ph > 14) return;
      const k = ph < 0 ? (ph + 3) / 3 : 1 - ph / 14;
      const kp = poses[e.c].kp;
      const pts = e.chain.map((j) => kp[j]).filter((p) => p.c >= MIN_CONF).map(P);
      if (pts.length < 2) return;
      ctx.globalAlpha = k; ctx.strokeStyle = CORNER[e.c]; ctx.lineWidth = 6 * dpr;
      ctx.beginPath(); pts.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]))); ctx.stroke();
      const end = pts[pts.length - 1];
      ctx.lineWidth = 1.6 * dpr;
      ctx.beginPath(); ctx.arc(end[0], end[1], (9 + 10 * (1 - k)) * dpr, 0, Math.PI * 2); ctx.stroke();
      ctx.font = font(11, 600); ctx.fillStyle = CORNER[e.c]; ctx.textBaseline = 'middle';
      ctx.fillText((STRIKE_LABEL[e.a] || e.a).toUpperCase(), end[0] + 16 * dpr, end[1] - 14 * dpr);
      ctx.globalAlpha = 1;
      if (Math.abs(ph) <= WINDOW) callout = e;
    });
  }

  // 1.2 s trail of the striking hand or foot, as the strike model reads it
  if (mode === 'strike' && !pose) {
    const e = S.events.reduce((best, ev) => (Math.abs(t - ev.si) < Math.abs(t - (best ? best.si : Infinity)) ? ev : best), null);
    if (e && Math.abs(t - e.si) <= WINDOW) {
      const j = e.chain[e.chain.length - 1];
      const from = Math.max(0, Math.ceil(e.si - WINDOW)), to = Math.min(t, e.si + WINDOW);
      ctx.lineWidth = 1.5 * dpr;
      for (let i = from; i < to; i++) {
        const p = S.tracks[e.c][i].kp[j], q = S.tracks[e.c][Math.min(S.n - 1, i + 1)].kp[j];
        if (p.c < MIN_CONF || q.c < MIN_CONF) continue;
        const u = P(p), v = P(q);
        ctx.strokeStyle = CORNER[e.c]; ctx.globalAlpha = 0.25 + 0.6 * ((i - from) / (2 * WINDOW));
        ctx.beginPath(); ctx.moveTo(u[0], u[1]); ctx.lineTo(v[0], v[1]); ctx.stroke();
        ctx.beginPath(); ctx.arc(u[0], u[1], 1.8 * dpr, 0, Math.PI * 2); ctx.fillStyle = CORNER[e.c]; ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
  }

  // sample strip: one tick per pose sample, playhead, strike marks, model window (hidden on the pose and corner layers)
  if (strip > 0.01) {
    ctx.globalAlpha = strip;
    const xL = 14 * dpr, xR = W - 14 * dpr, base = H - 12 * dpr;
    const X = (s) => xL + (s / (S.n - 1)) * (xR - xL);
    ctx.fillStyle = `rgba(${INK_RGB.join(',')},.16)`;
    for (let i = 0; i < S.n; i++) ctx.fillRect(X(i), base - (i % HZ === 0 ? 9 : 4) * dpr, 1 * dpr, (i % HZ === 0 ? 9 : 4) * dpr);
    if (mode === 'strike') {
      const w0 = X(Math.max(0, t - WINDOW)), w1 = X(Math.min(S.n - 1, t + WINDOW));
      ctx.fillStyle = `rgba(${INK_RGB.join(',')},.09)`; ctx.fillRect(w0, base - 16 * dpr, w1 - w0, 16 * dpr);
      ctx.font = font(10.5); ctx.fillStyle = `rgba(${INK_RGB.join(',')},.7)`; ctx.textBaseline = 'bottom';
      ctx.fillText('1.2 s WINDOW  31 POSES', Math.min(w0, xR - 150 * dpr), base - 20 * dpr);
    }
    if (strikes) S.events.forEach((e) => { ctx.fillStyle = CORNER[e.c]; ctx.fillRect(X(e.si) - 2.5 * dpr, base - 14 * dpr, 5 * dpr, 5 * dpr); });
    ctx.fillStyle = `rgb(${INK_RGB.join(',')})`; ctx.fillRect(X(t) - 0.75 * dpr, base - 18 * dpr, 1.5 * dpr, 18 * dpr);
    ctx.globalAlpha = 1;
  }
  return { callout, locked };
}

/* ---------- component ---------- */
const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const colourFor = (mode) => (mode === 'detect' ? 0 : 1);
const stripFor = (mode) => (mode === 'detect' || mode === 'corners' ? 0 : 1);
const zoomFor = (mode) => (mode === 'detect' ? 1 + POSE_ZOOM : 1);

function ExchangeStage({ mode }) {
  const S = sRef(null);
  if (!S.current) S.current = prepExchange(window.EXCHANGE);
  const canvasRef = sRef(null), wrapRef = sRef(null), frameRef = sRef(null), readRef = sRef(null);
  const modeRef = sRef(mode);
  const tRef = sRef(LOOP_START);
  const [playing, setPlaying] = sState(() => !reducedMotion());
  const playingRef = sRef(playing);
  const [passed, setPassed] = sState(0);
  const passedRef = sRef(0);
  const redraw = sRef(() => {});
  // restart = hold on the last frame, fade out, jump back while invisible, fade in already playing
  const loop = sRef({ phase: 'play', time: 0 });
  const settle = sRef(() => {});
  const kick = () => wrapRef.current.dispatchEvent(new Event('stage:play'));

  modeRef.current = mode;
  playingRef.current = playing;

  sEffect(() => {
    const s = S.current, cv = canvasRef.current, ctx = cv.getContext('2d');
    let W = 0, H = 0, dpr = 1, raf = 0, last = 0, visible = true;
    let lastMode = null, pose = null; // pose: { fromT, u, lock } while the detect layer holds a frame
    const vis = { colour: colourFor(modeRef.current), strip: stripFor(modeRef.current), zoom: zoomFor(modeRef.current) };
    if (!playingRef.current) tRef.current = s.events[2].si + 2;

    const setFade = (v) => wrapRef.current.style.setProperty('--fade', v.toFixed(3));
    const smooth = (x) => x * x * (3 - 2 * x);
    const paint = () => {
      const view = { t: tRef.current, mode: modeRef.current, colour: vis.colour, strip: vis.strip, zoom: vis.zoom, pose: pose && { fromT: pose.fromT, u: easeInOut(pose.u), lock: pose.lock } };
      const out = drawStage(ctx, s, W, H, view, dpr);
      const shownT = pose ? lerp(pose.fromT, s.pose, easeInOut(pose.u)) : tRef.current;
      if (frameRef.current) frameRef.current.textContent = Math.round(s.start + shownT * s.step);
      if (readRef.current) {
        readRef.current.textContent = pose ? `keypoints  ${out.locked * 2} / 34`
          : out.callout && modeRef.current === 'strike' ? `${out.callout.fam}  /  ${out.callout.t}` : '';
      }
      const n = s.events.filter((e) => e.si <= tRef.current).length;
      if (n !== passedRef.current) { passedRef.current = n; setPassed(n); }
    };
    redraw.current = paint;
    const size = () => {
      const r = cv.getBoundingClientRect();
      dpr = Math.min(2, window.devicePixelRatio || 1);
      W = cv.width = Math.round(r.width * dpr); H = cv.height = Math.round(r.height * dpr);
      paint();
    };
    settle.current = () => {
      const L = loop.current;
      if (L.phase === 'out') tRef.current = LOOP_START;
      if (L.phase === 'out' || L.phase === 'in') { L.phase = 'play'; L.time = 0; setFade(1); paint(); }
    };

    const enterMode = (prev, next) => {
      if (next === 'detect') {
        // stop the fight and glide into the held pose; a restart fade in progress is dropped
        pose = reducedMotion() ? { fromT: s.pose, u: 1, lock: LOCK_END } : { fromT: tRef.current, u: 0, lock: 0 };
        loop.current = { phase: 'play', time: 0 }; setFade(1);
      } else if (prev === 'detect') {
        tRef.current = s.pose; // the fight resumes from the held pose
        pose = null;
      }
    };
    // colour, strip, zoom and pose ease toward the current layer; true while anything is still moving
    const stepVisuals = (dt) => {
      const k = 1 - Math.exp(-dt * 7);
      let busy = false;
      [['colour', colourFor(modeRef.current)], ['strip', stripFor(modeRef.current)], ['zoom', zoomFor(modeRef.current)]].forEach(([key, target]) => {
        vis[key] += (target - vis[key]) * k;
        if (Math.abs(target - vis[key]) < 0.002) vis[key] = target; else busy = true;
      });
      if (pose && pose.lock < LOCK_END) {
        if (pose.u < 1) pose.u = Math.min(1, pose.u + dt / POSE_TWEEN);
        else pose.lock = Math.min(LOCK_END, pose.lock + dt / POSE_LOCK);
        busy = true;
      }
      return busy;
    };
    const stepPlayback = (dt) => {
      const L = loop.current;
      if (L.phase === 'play' && tRef.current >= s.n - 1) { L.phase = 'hold'; L.time = 0; }
      if (L.phase === 'hold') {
        L.time += dt;
        if (L.time >= LOOP_HOLD) { L.phase = 'out'; L.time = 0; }
      } else if (L.phase === 'out') {
        L.time += dt;
        setFade(1 - smooth(Math.min(1, L.time / LOOP_FADE)));
        if (L.time >= LOOP_FADE) { tRef.current = LOOP_START; L.phase = 'in'; L.time = 0; }
      } else {
        tRef.current = Math.min(s.n - 1, tRef.current + dt * HZ * (modeRef.current === 'strike' ? 0.45 : 1));
        if (L.phase === 'in') {
          L.time += dt;
          setFade(smooth(Math.min(1, L.time / LOOP_FADE)));
          if (L.time >= LOOP_FADE) { L.phase = 'play'; setFade(1); }
        }
      }
    };
    const tick = (now) => {
      raf = 0;
      if (!visible) { last = 0; return; }
      const dt = last ? Math.min(0.1, (now - last) / 1000) : 0; last = now;
      if (modeRef.current !== lastMode) { enterMode(lastMode, modeRef.current); lastMode = modeRef.current; }
      const busy = stepVisuals(dt);
      if (playingRef.current && !pose) stepPlayback(dt);
      paint();
      if ((playingRef.current && !pose) || busy) raf = requestAnimationFrame(tick); else last = 0; // a held pose needs no frames
    };
    const start = () => { if (!raf) raf = requestAnimationFrame(tick); };
    const ro = new ResizeObserver(size); ro.observe(cv);
    const io = new IntersectionObserver(([en]) => { visible = en.isIntersecting; if (visible) start(); }, { threshold: 0.05 });
    io.observe(wrapRef.current);
    const onPlay = () => start();
    wrapRef.current.addEventListener('stage:play', onPlay);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(size);
    size(); start();
    const el = wrapRef.current;
    return () => { cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); el.removeEventListener('stage:play', onPlay); };
  }, []);

  // a layer change animates even while paused; the loop stops itself once everything has settled
  sEffect(() => {
    if (!playing) settle.current(); // never leave a paused replay half-faded
    redraw.current();
    kick();
  }, [playing, mode]);

  const seek = (e) => {
    loop.current = { phase: 'play', time: 0 };
    wrapRef.current.style.setProperty('--fade', '1');
    tRef.current = Math.max(0, e.si - 8);
    setPlaying(true);
    redraw.current();
    kick();
  };

  const s = S.current;
  const log = s.events.slice(0, passed).reverse().slice(0, 4);
  const layers = [['detect', 'Pose'], ['corners', 'Corners'], ['strike', 'Strikes'], ['log', 'Timeline']];
  const on = (k) => mode === 'full' || mode === k;

  return (
    <div className={'stage-panel mode-' + mode} ref={wrapRef}>
      <div className="stage-hud">
        <ol className="stage-layers" aria-label="Pipeline layers shown">
          {layers.map(([k, l]) => <li key={k} className={on(k) ? 'on' : ''}>{l}</li>)}
        </ol>
        <div className="stage-frame mono"><span>frame</span> <b ref={frameRef}>{s.start}</b></div>
        <button className="stage-play" type="button" onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'Pause replay' : 'Play replay'}>
          <span className="material-symbols-outlined" aria-hidden="true">{playing ? 'pause' : 'play_arrow'}</span>
        </button>
      </div>
      <div className="stage-canvas">
        <canvas ref={canvasRef} role="img" aria-label="Two fighters drawn as skeletons from real pose data, with red and blue tracking boxes. Each strike flashes the limb that threw it." />
        <div className="stage-read mono" ref={readRef} aria-hidden="true"></div>
      </div>
      <div className="stage-log" aria-hidden={mode === 'full' || mode === 'log' ? undefined : true}>
        {log.length === 0 && <div className="log-empty">Strikes appear here as they land.</div>}
        {log.map((e) => (
          <button type="button" className="log-row" key={e.f} onClick={() => seek(e)} tabIndex={mode === 'full' || mode === 'log' ? undefined : -1}>
            <span className="mono log-f">{e.f}</span>
            <span className={'log-c c' + e.c}>{CORNER_NAME[e.c]}</span>
            <span className="log-d">{STRIKE_LABEL[e.a] || e.a} to the {e.t}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { ExchangeStage });
