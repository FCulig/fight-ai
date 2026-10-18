// Copies the real landing page (landing/, no build step) into a Claude Design
// page. Analytics is removed so design previews never count as visits, and the
// waitlist POST is answered locally so the form's success state can be seen.
// Run from the repo root: node .design-sync/screens/build-landing.mjs
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const repo = fileURLToPath(new URL('../../', import.meta.url));
const out = `${repo}.design-sync/.cache/landing/out/`;
rmSync(out, { recursive: true, force: true });
mkdirSync(`${out}current`, { recursive: true });
cpSync(`${repo}landing/app`, `${out}current/app`, { recursive: true });

let html = readFileSync(`${repo}landing/index.html`, 'utf8');
const analytics = /\s*<script>\s*\/\/ Umami Cloud analytics[\s\S]*?<\/script>/;
if (!analytics.test(html)) throw new Error('Umami block not found in landing/index.html - update build-landing.mjs');
html = html.replace(analytics, `
  <!-- Snapshot of the implemented landing page (landing/, ${new Date().toISOString().slice(0, 10)}). Analytics removed;
       the waitlist POST is answered locally. Rebuild with .design-sync/screens/build-landing.mjs. -->
  <script>
    (function () {
      var realFetch = window.fetch.bind(window);
      window.fetch = function (input, init) {
        var url = typeof input === 'string' ? input : input.url;
        if (/\\/api\\/auth\\/waitlist$/.test(url)) return Promise.resolve(new Response(null, { status: 204 }));
        return realFetch(input, init);
      };
    })();
  </script>`);
html = html.replace(/(src|href)="app\//g, '$1="current/app/');
writeFileSync(`${out}Fightlytics Landing (current).html`, html);
console.log('built landing → .design-sync/.cache/landing/out/');
