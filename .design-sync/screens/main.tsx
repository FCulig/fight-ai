// Entry for the Claude Design screens bundle: the real <App /> (header, auth,
// routes, pages) over recorded data. Each screen page sets window.__SCREEN.
import { createRoot } from 'react-dom/client';
import '../../frontend/src/index.css';
import { installHarness, type ScreenConfig } from './harness';

const screen = (window as unknown as { __SCREEN: ScreenConfig }).__SCREEN;
const base = document.currentScript ? new URL('.', (document.currentScript as HTMLScriptElement).src).href : location.href;

fetch(new URL('fixtures.json', base))
  .then(r => r.json())
  .then(async fixtures => {
    installHarness(fixtures, screen);
    // Imported after the harness so nothing in the app captures the real fetch first.
    const { default: App } = await import('../../frontend/src/App');
    createRoot(document.getElementById('root')!).render(<App />);
  });
