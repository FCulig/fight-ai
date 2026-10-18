// Offline stand-ins for what a Claude Design page can't reach: the /api
// backend (synthetic fixtures from synth.mjs, plus procedural keypoints), the
// fight video (a silent clock with the fight's length; no footage), and the
// /fights/stream SSE. Installed before the app mounts.

export interface ScreenConfig {
  path: string;
  /** Seconds to move the first video's playhead to once it loads. */
  start?: number;
  /** Serve /api/auth/me as 401 so AuthProvider shows the sign-in page. */
  signedOut?: boolean;
}

type Fixture = { status: number; body: unknown };

export function installHarness(fixtures: Record<string, Fixture>, screen: ScreenConfig) {
  const realFetch = window.fetch.bind(window);
  const json = (status: number, body: unknown) =>
    new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  let nextId = 900000;

  window.fetch = async (input, init) => {
    const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.href);
    if (!url.pathname.startsWith('/api/')) return realFetch(input, init);
    const method = (init?.method ?? 'GET').toUpperCase();
    if (url.pathname === '/api/auth/me' && screen.signedOut) return json(401, { detail: 'Not signed in' });
    if (method !== 'GET') {
      // Writes succeed locally so the screens stay clickable; nothing persists.
      if (method === 'DELETE') return json(204, null);
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : {};
      return json(200, { id: nextId++, ...body });
    }
    const frames = /^\/api\/fights\/(\d+)\/frames\/$/.exec(url.pathname);
    if (frames) return json(200, syntheticFrames(fixtures, Number(frames[1]), url.searchParams, screen));
    const hit = fixtures[url.pathname + url.search] ?? fixtures[url.pathname];
    return hit ? json(hit.status, hit.body) : json(404, { detail: 'Not in the recorded snapshot' });
  };

  class QuietEventSource extends EventTarget {
    readyState = 1;
    onmessage: ((e: MessageEvent) => void) | null = null;
    onerror: ((e: Event) => void) | null = null;
    close() { this.readyState = 2; }
  }
  (window as unknown as { EventSource: unknown }).EventSource = QuietEventSource;

  installVideoClock(fixtures, screen);
}

type FightRow = { id: number; fps: number; width: number; height: number; decoded_frames: number | null; reported_frames: number | null };
const fightRow = (fixtures: Record<string, Fixture>, id: number) =>
  ((fixtures['/api/fights/']?.body ?? []) as FightRow[]).find(f => f.id === id);

// COCO-17 standing guard, facing right, in units of ~1/400 of body height.
const GUARD: [number, number][] = [
  [10, 0], [14, -5], [6, -5], [16, 2], [0, 2], [18, 46], [-16, 46], [40, 74], [-10, 96], [58, 32], [24, 50],
  [12, 190], [-14, 190], [26, 290], [-34, 286], [32, 392], [-52, 388],
];

/** Two procedural fighters for any frame window: a bobbing guard with a lead
 * jab every couple of seconds. Stands in for keypoints from real footage. */
function syntheticFrames(fixtures: Record<string, Fixture>, fightId: number, params: URLSearchParams, screen: ScreenConfig) {
  const f = fightRow(fixtures, fightId);
  if (!f) return [];
  const around = Math.floor((screen.start ?? 0) * f.fps) + 1;
  const start = Number(params.get('start_frame') ?? Math.max(1, around - 40 * f.fps));
  const end = Number(params.get('end_frame') ?? around + 40 * f.fps);
  const scale = (f.height * 0.62) / 400;
  const out = [];
  for (let n = start; n <= end; n++) {
    const t = n / f.fps;
    for (const corner of [0, 1]) {
      const dir = corner === 0 ? 1 : -1;
      const phase = t * 0.9 + corner * 1.7;
      const cx = f.width * (corner === 0 ? 0.38 : 0.6) + Math.sin(phase) * f.width * 0.03;
      const top = f.height * 0.2 + Math.abs(Math.sin(t * 3 + corner)) * f.height * 0.012;
      const jab = Math.max(0, Math.sin(((t + corner * 0.9) % 2.2) / 2.2 * Math.PI * 6)) * ((t + corner * 0.9) % 2.2 < 0.37 ? 1 : 0);
      const kp = GUARD.map(([x, y], i) => {
        const reach = i === 9 ? jab * 70 : i === 7 ? jab * 30 : 0;
        return [Math.round((cx + dir * (x + reach) * scale) * 10) / 10, Math.round((top + y * scale) * 10) / 10] as [number, number];
      });
      const xs = kp.map(p => p[0]), ys = kp.map(p => p[1]);
      out.push({
        fight_id: fightId, frame: n, corner, confidence: 0.93,
        x1: Math.min(...xs) - 20 * scale, y1: Math.min(...ys) - 24 * scale, x2: Math.max(...xs) + 20 * scale, y2: Math.max(...ys) + 12 * scale,
        keypoints: kp,
      });
    }
  }
  return out;
}

function fightDuration(fixtures: Record<string, Fixture>, src: string): number {
  const f = fightRow(fixtures, Number(/\/fights\/(\d+)\/video/.exec(src)?.[1]));
  return f ? (f.decoded_frames ?? f.reported_frames ?? 0) / f.fps : 600;
}

function installVideoClock(fixtures: Record<string, Fixture>, screen: ScreenConfig) {
  interface Clock { src: string; duration: number; time: number; paused: boolean; timer?: number }
  const clocks = new WeakMap<HTMLMediaElement, Clock>();
  let startApplied = false;
  const proto = HTMLMediaElement.prototype;
  const clock = (el: HTMLMediaElement) => {
    let c = clocks.get(el);
    if (!c) { c = { src: '', duration: NaN, time: 0, paused: true }; clocks.set(el, c); }
    return c;
  };
  const fire = (el: HTMLMediaElement, type: string) => el.dispatchEvent(new Event(type));

  const load = (el: HTMLMediaElement, src: string) => {
    const c = clock(el);
    c.src = src;
    c.duration = fightDuration(fixtures, src);
    setTimeout(() => {
      ['loadstart', 'durationchange', 'loadedmetadata', 'loadeddata', 'canplay'].forEach(t => fire(el, t));
      if (!startApplied && screen.start != null) {
        startApplied = true;
        el.currentTime = screen.start;
      }
    }, 0);
  };

  const origSetAttribute = Element.prototype.setAttribute;
  proto.setAttribute = function (this: HTMLMediaElement, name: string, value: string) {
    if (name === 'src') { load(this, value); return; }
    origSetAttribute.call(this, name, value);
  };
  Object.defineProperties(proto, {
    src: { get() { return clock(this).src; }, set(v: string) { load(this, v); }, configurable: true },
    duration: { get() { return clock(this).duration; }, configurable: true },
    paused: { get() { return clock(this).paused; }, configurable: true },
    readyState: { get() { return clock(this).src ? 4 : 0; }, configurable: true },
    currentTime: {
      get() { return clock(this).time; },
      set(t: number) {
        const c = clock(this);
        c.time = Math.max(0, Math.min(Number(t) || 0, c.duration || 0));
        fire(this, 'seeking'); fire(this, 'timeupdate'); fire(this, 'seeked');
      },
      configurable: true,
    },
  });
  proto.play = function (this: HTMLMediaElement) {
    const c = clock(this);
    if (!c.paused) return Promise.resolve();
    c.paused = false;
    let last = performance.now();
    c.timer = window.setInterval(() => {
      const now = performance.now();
      c.time = Math.min(c.time + (now - last) / 1000, c.duration);
      last = now;
      fire(this, 'timeupdate');
      if (c.time >= c.duration) this.pause();
    }, 100);
    fire(this, 'play'); fire(this, 'playing');
    return Promise.resolve();
  };
  proto.pause = function (this: HTMLMediaElement) {
    const c = clock(this);
    if (c.paused) return;
    c.paused = true;
    clearInterval(c.timer);
    fire(this, 'pause');
  };
  proto.load = function () {};
  const vproto = HTMLVideoElement.prototype as unknown as {
    requestVideoFrameCallback: (cb: (now: number, meta: { mediaTime: number }) => void) => number;
    cancelVideoFrameCallback: (id: number) => void;
  };
  vproto.requestVideoFrameCallback = function (this: HTMLVideoElement, cb) {
    return requestAnimationFrame(now => cb(now, { mediaTime: clock(this).time }));
  };
  vproto.cancelVideoFrameCallback = id => cancelAnimationFrame(id);
}
