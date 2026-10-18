# design-sync notes (Fightlytics)

## How this repo is synced
- The app (`frontend/`) has no library build, so `.design-sync/pkg/` is a thin wrapper package (`fightlytics`, global `window.Fightlytics`): `index.ts` re-exports the presentational components' default exports by name, `logo.ts` side-effect-imports `landing/app/logo.jsx` (a classic script that assigns to `window`) and re-exports its components, and `surface.tsx` adds `AppSurface`.
- Build inputs first: `node .design-sync/pkg/build.mjs` (cfg.buildCmd). It runs tsc for `.d.ts` (type errors are expected and ignored; declarations still emit), symlinks `pkg/node_modules` → `frontend/node_modules` so @types/react resolves, and writes `pkg/dist/styles.css` = Google Fonts imports + `frontend/src/index.css` + the landing logo-lockup block from `landing/app/site.css`.
- Converter: `node .ds-sync/package-build.mjs --config .design-sync/config.json --node-modules frontend/node_modules --entry .design-sync/pkg/index.ts --out ./ds-bundle`.
- Playwright must be **1.62.0** in `.ds-sync/` (pins chromium build 1234, already cached in ~/Library/Caches/ms-playwright).
- Data-bound components (fetch `/api`, router, auth) are deliberately NOT exported: Header, UploadDialog, CornerSelect, FightLedger, AnnotatedEvents, LabOverview, NotMeasurable, ClassGrid, EventTable, EventReview, ClipPlayer, AuthProvider, RequireRole. A new presentational component needs a line in `pkg/index.ts`.
- `EdgeMeter.tsx` has no default export; its component is `EdgeRow`.

## Preview harness
- The card harness forces a white body; `cfg.provider` = `AppSurface` with `boxShadow: 0 0 0 24px var(--bg-base)` paints the 24px gutter dark without widening the story. A negative margin there made every card trip `[GRID_OVERFLOW]`.
- Changing `cfg.provider` clears every grade (it's in the grade contract), so expect a full regrade.
- MatchupCard uses `useWindowWidth() < 1100` for its narrow layout, so its card is `single` at 1240px wide.

## Known render warns
- `[RENDER_THIN] ConfirmDialog`, `FightEndModal`: "rendered height is 0px". They're `position: fixed` overlays; the screenshots are correct.
- `[RENDER_THIN] FighterOverlay`: "variants render identically". It's a canvas, so the DOM is the same across stories; the screenshots differ (box vs. no box).

## Findings in the app itself (not sync issues)
- KeyboardLegend: the "Click" + "Delete" kbd chips overflow the 78px key column and overlap the label text.
- `LogoLockup`/`LogoStack` `sub` renders with class `brand-sub`, which no stylesheet defines (the landing page never passes `sub`).

## Re-sync risks
- `pkg/index.ts` is a hand list. Components added to `frontend/src/components` don't sync until they're added there; renamed or removed ones break the build.
- `build.mjs` pulls the logo CSS from `landing/app/site.css` by the `/* ---------- brand lockup` comment. If that block is renamed, the build throws.
- Preview fixtures (`previews/*.tsx`) inline Event / EvalRunSummary / FighterStats shapes; re-check them when those types change.
- Fonts are remote (Google Fonts); designs need network access to render the brand type.

## Current-screen snapshots (`.design-sync/screens/`)
- "<Screen> (current).html" in the "Fight AI app" project are the real `frontend/` pages (`App` with header and auth) bundled by `build.mjs`. A `router-shim.tsx` swaps BrowserRouter for a MemoryRouter at the screen's route, and `harness.ts` stubs `/api`, the video and the SSE.
- **Data is synthetic by design.** `synth.mjs` invents every fighter, label, prediction, eval run and user, and the harness draws procedural keypoints. Never record real DB responses for these: copying real fight data into Claude Design was blocked as exfiltration, and the user chose invented data.
- The "Fight AI landing page" project gets "Fightlytics Landing (current).html": `build-landing.mjs` copies `landing/` with the Umami block removed and the waitlist POST answered locally.
- Rebuild: `node .design-sync/screens/synth.mjs && node .design-sync/screens/build.mjs && node .design-sync/screens/build-landing.mjs`, then stage both outputs under `.design-sync/.cache/uikit/ui_kits/{app,landing}`. Upload them to the design-system project's `ui_kits/` (DesignSync, localPath) and `copy_files` them into the two projects. Claude Design's own `write_files` takes inline data only, too small for the 0.5 MB bundle.
- Check a build with `node .design-sync/screens/shoot.mjs <port>` while serving `.design-sync/.cache/screens/out`.
- Re-sync risk: a page that calls a new endpoint renders an empty or error state until `synth.mjs` emits it (unknown routes return 404 "Not in the recorded snapshot").
- App quirk seen while building: Player's video badge reads "Loading…" whenever the playhead is between rounds (`currentRound === '-'`).
