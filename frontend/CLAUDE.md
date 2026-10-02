# frontend/ — React + TypeScript + Vite

**Pages** (`src/pages/`):
- `FightList`: library and upload, updated live via the SSE stream.
- `Player`: fight review.
- `Annotate`: hand labelling.
- `TrainingDataQA` (`/training-data`).
- `PipelineAccuracy` (`/accuracy`).
- `Library`: legacy.
- `Users` (`/users`, admin): roles and access.
- `SignIn`: rendered by `AuthProvider` in place of the app while signed out.

Data access goes through `services/api.ts` plus one hook per resource in `hooks/`. Every call uses `apiFetch`, which adds the `/api` prefix and reloads the page on a 401. `<video src>` and `EventSource` must use `videoUrl()` and `FIGHT_STREAM_URL`, and they authenticate through the same-origin session cookie.

**Auth:** `AuthProvider` renders the app only after `/api/auth/me` answers. Use `useAuth().can(role)` to hide controls and `RequireRole` to guard routes. Both are cosmetic, because the backend enforces roles.

**Page-specific rules load when you open matching files:**
- `.claude/rules/frontend-player.md`
- `.claude/rules/frontend-annotate.md`
- `.claude/rules/frontend-training-data-qa.md`

## Dev server
`vite.config.ts` proxies `/api` to `127.0.0.1:8000`. Every backend route lives under `/api`, so client routes never collide with it. Never add a client route under `/api`.

## Conventions
- **Frame numbers:** use `Math.floor(currentTime * fps) + 1` with `fight.fps`, and step frames with `delta / fps` seconds. Never hardcode fps.
- **Event text** comes from `utils/describeEvent.ts`, and category, colour and icon come from `utils/eventTaxonomy.ts`, keyed on `action`. Never parse or display `description`. Only `fight_end` has one.
- **Strike attribution** (`utils/liveStats.ts`) uses `fighter_id` for predictions (matched against `fights.red_fighter_id`) and `corner` for labels, never text.
- **Corner-swap correction is display-only**, via `utils/cornerSwap.ts`'s `isFrameSwapped`. It is used for box colour in `FighterOverlay` and for fighter names in `describeEvent`. Never write a swapped corner back.
- **`useFighterFrames(fightId)`** with no range downloads the whole fight's keypoints, tens of MB. That's fine for Player and Annotate, which scrub anywhere. Anything that needs only a few frames must pass `{start_frame, end_frame}`.
- **Mock data:** fighter profiles, stats, pace and recent form are hardcoded in `src/mocks/fightMock.ts`. `TODO_BACKEND_DATA.md` lists the API each one needs.
- **Badge colours:** purpose and other badges must not reuse the red/blue corner colours or the error/warning colours, because a red badge reads as "red corner". See `PURPOSE_COLORS` in `types/Fight.ts`.

## Design
The look is shared with `landing/`. Tokens and shared classes live in `src/index.css`; components style inline with those tokens.
- **Orange (`--accent`) means the brand, a screen's primary action, or the AI** (the `ai_labeled` badge, model scores and prediction charts on Accuracy). Selection, focus, playheads, progress bars and human-labelled counts use ink (`--text-primary`), so orange never sits beside the red corner like a third fighter.
- **Red and blue mean corners only, and text never wears a corner colour.** Put a swatch next to ink text instead, so a name stays readable and the colour stays a mark.
- **Type:** Archivo everywhere. Headings use `.font-display` (condensed, heavy) and are written in sentence case. Every stat, count and score uses `.font-num` (JetBrains Mono), so digits line up.
- **Shape:** controls 6px (`--r-ctl`), tiles 8px, panels 12px. No pills, and no glow shadows.
- **Don't change a data colour by eye.** Corners, the state trio, `--warn`, statuses and `PURPOSE_COLORS` were measured against each other; run the dataviz skill's `validate_palette.js` before touching one. The app's corner blue stays `#60a5fa` (the landing page uses `#4f93ea`), because the darker blue sits even closer to `--state-ground`.

## Upload (`UploadDialog`)
**AI annotation** always sends `purpose='ai_labeled'`. **Self-annotate** shows a purpose radio group (`training_data` / `reference`) with **no default**, and Upload stays disabled until one is picked. The gate is deliberate: the training and evaluation sets must never be split by inattention. `uploadFight()` sends `purpose` as the only track selector.

## Deleting a fight
`DELETE /fights/{id}` is irreversible: it kills the pipeline, unlinks the video, and cascades every event. All entry points go through `ConfirmDialog`:
- **`Player.tsx`** is the only place to delete a healthy fight. Keep two things:
  - `videoRef.current.pause()` before the request, because the `<video>` is still streaming the file being unlinked.
  - `navigate('/', { replace: true })` afterwards.
- **`Annotate.tsx`** has a header button. See the Annotate rule for the keyboard guard every modal needs.
- **`FightList.tsx`** shows delete only on `failed`/`invalid` rows, as a delete-and-re-upload recovery path. It uses one dialog outside the `.map`, driven by `pendingDelete`.
