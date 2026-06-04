# Fight AI — Frontend

## Workflow
- Always apply changes directly to the local working directory
- Never open PRs or suggest creating pull requests

## What it does
React + TypeScript + Vite app for reviewing processed MMA fight videos. Displays fight events in a live feed, shows DB-backed round information, and renders toggleable fighter bounding-box overlays on the video.

## Project Structure
```
frontend/src/
├── types/
│   ├── Event.ts          # { id, frame, description, fight_id }
│   ├── Fight.ts          # { id, video_path, fps, width, height, created_at, processed, processed_at }
│   ├── FighterFrame.ts   # { fight_id, frame, fighter_id, x1, y1, x2, y2, confidence }
│   └── Round.ts          # { id, fight_id, round_number, start_frame, end_frame }
├── services/
│   └── api.ts            # fetchEvents, fetchFightEvents, fetchFights, fetchFighterFrames, fetchRounds
├── hooks/
│   ├── useEvents.ts      # fetches events; accepts optional fightId (uses /fights/{id}/events/ when set)
│   ├── useFights.ts      # fetches all fights, exposes selectedFightId state (defaults to latest)
│   ├── useFighterFrames.ts # fetches frames for selectedFightId → Map<frame, FighterFrame[]>
│   ├── useRounds.ts      # fetches rounds for selectedFightId
│   └── useWindowWidth.ts # responsive breakpoint helper
├── mocks/
│   └── fightMock.ts      # hardcoded mock data (fighters, stats, pace, form) — see TODO_BACKEND_DATA.md
├── components/
│   ├── FighterOverlay.tsx  # canvas overlay for fighter bounding boxes
│   ├── VideoPlayer.tsx     # <video> wrapper with play/seek gestures; accepts children for overlays
│   ├── VideoControls.tsx   # playback controls + scrubber
│   ├── FrameInfo.tsx       # frame / ms / fps display
│   ├── EventFeed.tsx       # scrolling event list (legacy — not used in the new Player)
│   ├── EventItem.tsx       # individual event row
│   ├── Header.tsx          # top nav
│   └── player/             # Analysis Player sub-components
│       ├── eventMeta.ts    # deriveEventCat / eventColor / eventIcon helpers (regex-based)
│       ├── LiveFeed.tsx    # real-event chat feed with filter pills + click-to-seek
│       ├── ScopeToggle.tsx # Whole Fight / Round 1 / Round 2 pill group
│       ├── AccGauge.tsx    # SVG accuracy ring gauge
│       ├── SegBar.tsx      # horizontal segmented bar (strikes by target / position)
│       ├── PaceChart.tsx   # SVG area/line pace chart with live playhead
│       ├── MiniStat.tsx    # small inner-tile stat (Takedowns, Control, KD, Sub Att)
│       ├── EdgeMeter.tsx   # tale-of-the-tape needle (Height / Reach / Age)
│       ├── RecentForm.tsx  # W/L chip list (Recent Form · Last 5)
│       ├── FighterColumn.tsx  # per-fighter stats card (AccGauge + MiniStat + SegBar)
│       ├── FightStatistics.tsx # scope bar + ScopeToggle + two FighterColumn
│       ├── Momentum.tsx    # MOMENTUM card wrapping PaceChart
│       └── MatchupCard.tsx # tale-of-the-tape + EdgeMeter rows + RecentForm
└── pages/
    ├── Player.tsx          # main fight-review page (Analysis Player redesign)
    └── Library.tsx         # fight library listing
```

## Analysis Player Layout

`Player.tsx` implements a cinematic, full-page layout with five stacked sections (top → bottom):

1. **Top grid** (`1fr 410px`, collapses single-column below 1100px) — `<VideoPlayer>` + `FighterOverlay` + ROUND chip on the left; `LiveFeed` filling the right column via absolute positioning so it always matches the video column height.
2. **FIGHT STATISTICS** — `FightStatistics.tsx`: glass bar with `monitoring` icon + `ScopeToggle` (Whole Fight / Round 1 / Round 2); two `FighterColumn` cards below (real scope state selects the mock stat set from `fightMock.ts`).
3. **MOMENTUM** — `Momentum.tsx`: `PaceChart` (SVG area/line, mock pace data, real time-axis from `currentTime`/`duration`; real `r1EndSeconds` from `useRounds` or fallback mock).
4. **MATCHUP** — `MatchupCard.tsx`: tale-of-the-tape header + `EdgeRow` needles for Height/Reach/Age + Recent Form W/L chips.

### Live feed event derivation
`LiveFeed` drives on **real** backend events (same `useEvents` hook). Each `Event.description` is classified by `deriveEventCat()` in `eventMeta.ts` using the same strike/ground regexes that existed before in `Player.tsx` and `EventFeed.tsx`. Filter pills (All / Strikes / Fight State / Grapple) and click-to-seek work the same way as the design reference.

### Mock data
All hardcoded values (fighter profiles, per-round stats, pace arrays, recent form) live in `src/mocks/fightMock.ts`. Every gap is documented with the API shape needed to replace it in `TODO_BACKEND_DATA.md`.

### Responsive
`useWindowWidth()` drives a `narrow = width < 1100` flag. Below 1100px: top grid collapses to single column (live feed becomes a fixed-height `420px` block below controls); fighter columns stack; matchup tale-of-the-tape collapses; form lists both align left.

## API Proxy (vite.config.ts)
Both `/events` and `/fights` are proxied to `http://127.0.0.1:8000`.
Video files are served from `public/` via a custom range-request middleware.

## Frame-numbering contract
**Frames are 1-based** — the first frame of the video is frame 1.

Convert `video.currentTime` to a frame number with:
```ts
const currentFrame = Math.floor(currentTime * fps) + 1;
```
where `fps` comes from `FightResponse.fps` (an integer stored on the `fights` DB row).

This value is used to:
- Look up `frameMap.get(currentFrame)` in `FighterOverlay`
- Filter `events.filter(e => e.frame <= currentFrame)` in `Player`
- Match round boundaries: `rounds.find(r => currentFrame >= r.start_frame && currentFrame <= r.end_frame)`

Never hardcode an fps value — always use `selectedFight.fps`.

## FighterOverlay component
`<canvas>` absolutely positioned over the video (`pointer-events: none`).

On each `currentFrame` change:
1. Resize canvas to its CSS display size (`canvas.width = canvas.clientWidth`, etc.)
2. Clear canvas
3. If `showBoxes` is false, return early
4. Look up `frameMap.get(currentFrame)` → array of `FighterFrame`
5. Scale each bbox from the fight's **native resolution** (`fightWidth` × `fightHeight` from `FightResponse`) to the canvas display size:
   ```ts
   const scaleX = canvas.width / fightWidth;
   const scaleY = canvas.height / fightHeight;
   ```
6. Draw red rect for `fighter_id === 0`, blue for `fighter_id === 1`

`VideoPlayer` accepts `children` so `FighterOverlay` can be rendered inside the `position: relative` video container and stack correctly.

## Fight selector (Player.tsx)
- Populated from `useFights` (filtered to `processed === true`)
- Defaults to the most recently processed fight (last element of the list)
- Changing selection re-fetches events, frames, and rounds for the new fight

## Key design decisions
- `useFighterFrames` builds a `Map<number, FighterFrame[]>` on load for O(1) per-frame overlay lookup during playback
- `useRounds` provides DB-backed round boundaries; `Player` uses `rounds.find(...)` instead of a hardcoded duration constant
- `stepFrame(delta)` uses `delta / fps` seconds, so frame-stepping is always exact regardless of the video's actual fps
