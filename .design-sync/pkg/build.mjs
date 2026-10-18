// Builds the design-sync input package: .d.ts for the entry (tsc) and one stylesheet
// (the app's index.css plus the landing page's logo-lockup rules, which logo.jsx needs).
// Run from the repo root: node .design-sync/pkg/build.mjs
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, '../..');
const dist = join(here, 'dist');
rmSync(dist, { recursive: true, force: true });
// The converter type-checks from this directory; link the app's node_modules so @types/react resolves.
if (!existsSync(join(here, 'node_modules'))) symlinkSync('../../frontend/node_modules', join(here, 'node_modules'));
mkdirSync(dist, { recursive: true });

try {
  execFileSync(join(repo, 'frontend/node_modules/.bin/tsc'), ['-p', join(here, 'tsconfig.json')], { stdio: 'pipe' });
} catch (e) {
  // Type errors are expected (vite/client types, strict-only code); declarations still emit.
  console.error(`tsc reported type errors (declarations still emitted): ${String(e.stdout).split('\n').length} lines`);
}

const site = readFileSync(join(repo, 'landing/app/site.css'), 'utf8');
const brand = site.match(/\/\* -+ brand lockup[\s\S]*?(?=\n\/\* -+ )/);
if (!brand) throw new Error('brand lockup block not found in landing/app/site.css');
writeFileSync(join(dist, 'styles.css'), [
  readFileSync(join(here, 'fonts.css'), 'utf8'),
  '/* frontend/src/index.css */',
  readFileSync(join(repo, 'frontend/src/index.css'), 'utf8'),
  '/* landing/app/site.css: logo lockup (its --ink is the app\'s --text-primary) */',
  ':root { --ink: var(--text-primary); }',
  brand[0],
].join('\n'));
console.log('built .design-sync/pkg/dist');
