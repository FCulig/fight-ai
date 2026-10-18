// Builds the Claude Design screens: one bundle of the real frontend over the
// synthetic fixtures (synth.mjs), plus one page per entry in screens.config.mjs.
// Run from the repo root: node .design-sync/screens/build.mjs
import { copyFileSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { SCREENS } from './screens.config.mjs';

const here = fileURLToPath(new URL('.', import.meta.url));
const repo = fileURLToPath(new URL('../../', import.meta.url));
const require = createRequire(new URL('../../.ds-sync/package.json', import.meta.url));
const { build } = require('esbuild');
const out = `${repo}.design-sync/.cache/screens/out/`;
rmSync(out, { recursive: true, force: true });
mkdirSync(`${out}current`, { recursive: true });

const realRouter = require.resolve('react-router-dom', { paths: [`${repo}frontend`] });
await build({
  entryPoints: [`${here}main.tsx`],
  bundle: true,
  format: 'iife',
  jsx: 'automatic',
  minify: true,
  target: 'es2020',
  outfile: `${out}current/screens.js`,
  nodePaths: [`${repo}frontend/node_modules`],
  define: { 'process.env.NODE_ENV': '"production"' },
  loader: { '.svg': 'dataurl', '.png': 'dataurl', '.jpg': 'dataurl' },
  plugins: [{
    name: 'screen-router',
    setup(b) {
      b.onResolve({ filter: /^react-router-dom$/ }, () => ({ path: `${here}router-shim.tsx` }));
      b.onResolve({ filter: /^react-router-dom-real$/ }, () => ({ path: realRouter }));
    },
  }],
  logLevel: 'warning',
});
copyFileSync(`${repo}.design-sync/.cache/screens/fixtures.json`, `${out}current/fixtures.json`);

const FONTS = 'https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,300..900&family=Bebas+Neue&family=JetBrains+Mono:wght@400;500;600&display=swap';
const ICONS = 'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200';
const meta = JSON.parse(readFileSync(`${repo}.design-sync/.cache/screens/synth-meta.json`, 'utf8'));
for (const s of SCREENS) {
  const { name, file, ...config } = s;
  config.path = config.path.replace(/\{(\w+)\}/g, (_, k) => meta[k]);
  writeFileSync(`${out}${file} (current).html`, `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fightlytics · ${name} (current)</title>
  <!-- The implemented app (frontend/, ${new Date().toISOString().slice(0, 10)}): the real pages over invented sample
       data. Video is a silent placeholder clock; writes don't persist. Rebuild with .design-sync/screens/. -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="${FONTS}">
  <link rel="stylesheet" href="${ICONS}">
  <link rel="stylesheet" href="current/screens.css">
  <style>video { background: #16171a; aspect-ratio: 16 / 9; }</style>
</head>
<body>
  <div id="root" data-screen-label="${name}"></div>
  <script>window.__SCREEN = ${JSON.stringify(config)};</script>
  <script src="current/screens.js"></script>
</body>
</html>
`);
}
console.log(`built ${SCREENS.length} screens → .design-sync/.cache/screens/out/`);
