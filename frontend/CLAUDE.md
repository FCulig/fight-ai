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
├── components/
│   ├── FighterOverlay.tsx  # canvas overlay for fighter bounding boxes
│   ├── VideoPlayer.tsx     # <video> wrapper with play/seek gestures; accepts children for overlays
│   ├── VideoControls.tsx   # playback controls + scrubber
│   ├── FrameInfo.tsx       # frame / ms / fps display
│   ├── EventFeed.tsx       # scrolling event list
│   ├── EventItem.tsx       # individual event row
│   └── Header.tsx          # top nav
└── pages/
    ├── Player.tsx          # main fight-review page
    └── Library.tsx         # fight library listing
```

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
