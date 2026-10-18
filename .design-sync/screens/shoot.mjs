// Screenshots every built screen (served from out/ on a local port) for review.
// Usage: node .design-sync/screens/shoot.mjs <port>
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { SCREENS } from './screens.config.mjs';
const require = createRequire(new URL('../../.ds-sync/package.json', import.meta.url));
const { chromium } = require('playwright');
const port = process.argv[2];
const dir = new URL('../.cache/screens/shots/', import.meta.url).pathname;
mkdirSync(dir, { recursive: true });
const browser = await chromium.launch();
for (const s of SCREENS) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = [];
  page.on('pageerror', e => errs.push(String(e)));
  page.on('console', m => m.type() === 'error' && errs.push(m.text()));
  await page.goto(`http://127.0.0.1:${port}/${encodeURIComponent(s.file + ' (current).html')}`);
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${dir}${s.file}.png`, fullPage: true });
  console.log(s.file, errs.length ? errs.slice(0, 3).join(' | ') : 'ok');
  await page.close();
}
await browser.close();
