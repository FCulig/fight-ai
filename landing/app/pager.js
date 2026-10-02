// app/pager.js — one wheel/trackpad gesture or key press moves exactly one section.
// Stops come from each element's CSS `scroll-snap-align` (site.css), so CSS stays the single source.
// Touch screens use native CSS snapping instead (site.css); this only runs with a mouse or trackpad.
(function () {
  const TARGETS = '.hero, .step, .sec, .final, .footer';
  const MERGE_PX = 100;      // stops closer than this collapse into the later one
  const GESTURE_GAP = 180;   // ms of wheel silence that ends a gesture (trackpad momentum included)
  const DURATION = 650;      // ms per jump

  function alignOf(el) {
    const a = getComputedStyle(el).scrollSnapAlign.split(' ')[0]; // block axis
    return a === 'center' || a === 'end' ? a : 'start';
  }

  // where the page must scroll to so `el` sits at its snap alignment
  function stopFor(el, nav, vh) {
    const top = el.getBoundingClientRect().top + window.scrollY, h = el.offsetHeight;
    const align = alignOf(el);
    if (align === 'center') return top + h / 2 - (nav + (vh - nav) / 2);
    if (align === 'end') return top + h - vh;
    return top - nav;
  }

  function computeStops() {
    const nav = document.querySelector('.nav').offsetHeight, vh = window.innerHeight, port = vh - nav;
    const max = document.documentElement.scrollHeight - vh;
    const raw = [0];
    document.querySelectorAll(TARGETS).forEach((el) => {
      const y = stopFor(el, nav, vh);
      raw.push(y);
      // a section taller than the screen gets extra stops so its lower part is never skipped
      if (alignOf(el) === 'start' && el.offsetHeight > port) {
        const bottom = el.getBoundingClientRect().top + window.scrollY + el.offsetHeight - vh;
        for (let p = y + port * 0.85; p < bottom; p += port * 0.85) raw.push(p);
        raw.push(bottom);
      }
    });
    const sorted = raw.map((y) => Math.round(Math.min(max, Math.max(0, y)))).sort((a, b) => a - b);
    const out = [];
    sorted.forEach((y) => {
      const prev = out[out.length - 1];
      if (prev === undefined) out.push(y);
      else if (y - prev < MERGE_PX) { if (prev !== 0) out[out.length - 1] = y; }
      else out.push(y);
    });
    return out;
  }

  function createPager() {
    const touchFirst = window.matchMedia('(hover: none), (pointer: coarse)').matches;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (touchFirst || reduce) return null;

    let raf = 0, animating = false, armed = true, lastWheel = 0, lastMag = 0;
    const ease = (t) => 1 - Math.pow(1 - t, 3);

    function animateTo(target, instant) {
      cancelAnimationFrame(raf);
      const from = window.scrollY, dist = target - from;
      if (instant || Math.abs(dist) < 1) { window.scrollTo({ top: target, behavior: 'instant' }); animating = false; return; }
      const t0 = performance.now();
      animating = true;
      const frame = (now) => {
        const p = Math.min(1, (now - t0) / DURATION);
        window.scrollTo({ top: from + dist * ease(p), behavior: 'instant' });
        if (p < 1) raf = requestAnimationFrame(frame);
        else animating = false;
      };
      raf = requestAnimationFrame(frame);
    }

    function step(dir) {
      const stops = computeStops(), y = window.scrollY;
      const target = dir > 0 ? stops.find((s) => s > y + 2) : stops.slice().reverse().find((s) => s < y - 2);
      if (target !== undefined) animateTo(target);
    }

    function goTo(el, instant) {
      const nav = document.querySelector('.nav').offsetHeight, vh = window.innerHeight;
      const max = document.documentElement.scrollHeight - vh;
      animateTo(Math.min(max, Math.max(0, Math.round(stopFor(el, nav, vh)))), instant);
    }

    const onWheel = (e) => {
      if (e.ctrlKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return; // pinch-zoom, sideways swipes
      e.preventDefault();
      const now = performance.now(), mag = Math.abs(e.deltaY);
      // a pause, or a fresh acceleration after the jump, starts a new gesture; momentum tails never do
      if (now - lastWheel > GESTURE_GAP || (!animating && mag > lastMag * 1.6 && mag > 25)) armed = true;
      lastWheel = now; lastMag = mag;
      if (armed && !animating && mag >= 4) { armed = false; step(Math.sign(e.deltaY)); }
    };

    const onKey = (e) => {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const t = e.target;
      if (t.closest && t.closest('input, textarea, select, [contenteditable]')) return;
      let dir = 0;
      if (e.key === 'ArrowDown' || e.key === 'PageDown') dir = 1;
      else if (e.key === 'ArrowUp' || e.key === 'PageUp') dir = -1;
      else if (e.key === ' ' && !(t.closest && t.closest('button, a'))) dir = e.shiftKey ? -1 : 1;
      else if (e.key === 'Home' || e.key === 'End') {
        e.preventDefault();
        const stops = computeStops();
        animateTo(e.key === 'Home' ? stops[0] : stops[stops.length - 1]);
        return;
      }
      if (!dir) return;
      e.preventDefault();
      if (!animating) step(dir);
    };

    // in-page links land on the section's stop, not its raw top (the skip link keeps native focus behaviour)
    const onClick = (e) => {
      const a = e.target.closest && e.target.closest('a[href^="#"]');
      if (!a || a.classList.contains('skip') || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
      const el = document.getElementById(a.getAttribute('href').slice(1));
      if (!el) return;
      e.preventDefault();
      history.pushState(null, '', a.getAttribute('href'));
      goTo(el);
    };

    window.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('keydown', onKey);
    document.addEventListener('click', onClick);
    return {
      goTo,
      destroy() {
        cancelAnimationFrame(raf);
        window.removeEventListener('wheel', onWheel);
        window.removeEventListener('keydown', onKey);
        document.removeEventListener('click', onClick);
      },
    };
  }

  window.createPager = createPager;
})();
