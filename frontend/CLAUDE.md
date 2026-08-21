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
│   ├── Event.ts          # pipeline PREDICTIONS (read-only): { id, frame, description,
│   │                      #   fight_id, fighter_id, action, success }
│   ├── LabelEvent.ts      # HAND LABELS: { id, frame, description, fight_id, corner
│   │                      #   (0=red/1=blue), action, target, success, labeler, created_at }
│   ├── LabelSpan.ts       # { id, fight_id, kind: 'round'|'corner_swap'|'excluded',
│   │                      #   start_frame, end_frame (null = still open), value }
│   ├── Fight.ts           # { id, video_path, fps, width, height, created_at, state,
│   │                      #   labeled_at, reported_frames, decoded_frames,
│   │                      #   segmentation_needs_review/_reason, red/blue_fighter_id }
│   │                      #   + STATE_LABELS/STATE_PROGRESS/TERMINAL_STATES maps and
│   │                      #   isFightViewable/isLabelingReady/isInvalid/needsRoundReview
│   │                      #   predicates
│   ├── FighterFrame.ts   # { fight_id, frame, corner, x1, y1, x2, y2, confidence }
│   └── Round.ts          # { id, fight_id, round_number, start_frame, end_frame }
├── services/
│   └── api.ts            # fetchEvents/fetchFightEvents (predictions), fetchFights,
│                          #   fetchFighterFrames, fetchRounds, uploadFight, deleteFight,
│                          #   finishLabeling, fetch/create/deleteLabelEvent,
│                          #   fetch/create/update/deleteLabelSpan
├── hooks/
│   ├── useEvents.ts       # fetches PREDICTIONS; accepts optional fightId (uses
│   │                      #   /fights/{id}/events/ when set) — used by Player, not Annotate
│   ├── useLabelEvents.ts  # fetches HAND LABELS for a fightId — used by Annotate
│   ├── useLabelSpans.ts   # fetches label_spans for a fightId (round/corner_swap/excluded)
│   ├── useFights.ts       # fetches all fights, exposes selectedFightId state (defaults to latest)
│   ├── useFightStream.ts  # subscribes to /fights/stream SSE, patches `state` into the fights list live
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
│   ├── CornerSelect.tsx    # fighter search/create combobox, used by the upload dialog
│   ├── ConfirmDialog.tsx   # reusable confirm modal (title/message/danger/busy/error);
│   │                       #   backs fight deletion from both Player and FightList
│   ├── annotate/           # Annotate page sub-components — see "Labelling (Annotate page)" below
│   │   ├── taxonomy.ts         # ToolItem palette definitions, KEYMAP, colour/icon/category
│   │   │                       #   helpers, successForAction, SPAN_KEYS/EDIT_KEYS/PLAYBACK_KEYS
│   │   ├── AnnotateStage.tsx   # video + FighterOverlay + toast, wraps VideoPlayer for Annotate
│   │   ├── FighterSelectCard.tsx # red/blue corner picker (drives `selected` in Annotate.tsx)
│   │   ├── EventPalette.tsx    # click-to-log buttons for every ToolItem + End-of-fight button
│   │   ├── FightEndModal.tsx   # winner/method modal for the `fight_end` label event
│   │   ├── KeyboardLegend.tsx  # renders PLAYBACK_KEYS/EDIT_KEYS/SPAN_KEYS/TOOL_GROUPS
│   │   ├── AnnotationPanel.tsx # timeline/list view toggle + filter pills, wraps the two below
│   │   ├── AnnotationTimeline.tsx # multi-lane timeline: rounds, state segs, corner_swap/
│   │   │                       #   excluded spans (draggable edges), red/blue strike clips
│   │   ├── AnnotationList.tsx  # flat chronological list view of label events
│   │   └── SaveStatus.tsx      # small "saving…" indicator (savingCount > 0)
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
    ├── Player.tsx          # main fight-review page (Analysis Player redesign) — reads predictions
    ├── Annotate.tsx        # manual-labelling page — reads/writes label_events + label_spans
    ├── FightList.tsx       # fight library / upload entry point, live via useFightStream
    └── Library.tsx         # legacy fight library listing
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
6. Draw red rect for `corner === 0`, blue for `corner === 1`

`VideoPlayer` accepts `children` so `FighterOverlay` can be rendered inside the `position: relative` video container and stack correctly.

## Fight selector (Player.tsx)
- Populated from `useFights`, filtered to `isFightViewable(state)` (`completed` or `labeling_complete`)
- Defaults to the most recently processed fight (last element of the list)
- Changing selection re-fetches events, frames, and rounds for the new fight

## Deleting a fight
`DELETE /fights/{id}` is irreversible — it kills any running pipeline, unlinks the video file, and
cascades away predictions, label events/spans, rounds and fighter frames. Two entry points, both
routed through `ConfirmDialog`:

- **`Player.tsx`** — Delete button in the back-nav row (icon-only when `narrow`). The only way to
  delete a healthy fight. Two things the handler must keep doing: `videoRef.current.pause()` before
  the request, because the DELETE unlinks the file the `<video>` is streaming and the
  `requestVideoFrameCallback` loop is still reading it; and `navigate('/', { replace: true })`, so
  browser Back can't land on a now-dead `/fights/{id}`.
- **`Annotate.tsx`** — icon-only button at the far right of the header, past "Finish Labeling".
  Its `confirmDelete` state is mirrored into `confirmDeleteRef` and checked in the global keydown
  handler alongside `endOpenRef` — **any new modal on this page must do the same**, or its overlay
  will happily sit there while `z`/`o`/`p`/digit presses keep writing label events and spans
  underneath it.
- **`FightList.tsx`** — gated behind `errored` (`failed || invalid`), so it does *not* appear on
  healthy cards; it's a "delete and re-upload" recovery affordance, not a general delete. One
  dialog instance lives outside the `.map`, driven by `pendingDelete`.

Set `KEEP_VIDEO_ON_DELETE=1` on the backend when exercising this by hand — the row still goes, but
the source video survives.

## Key design decisions
- `useFighterFrames` builds a `Map<number, FighterFrame[]>` on load for O(1) per-frame overlay lookup during playback
- `useRounds` provides DB-backed round boundaries; `Player` uses `rounds.find(...)` instead of a hardcoded duration constant
- `stepFrame(delta)` uses `delta / fps` seconds, so frame-stepping is always exact regardless of the video's actual fps

## Labelling (Annotate page)

`Annotate.tsx` (`/fights/{id}/annotate`) is where a **manual**-mode upload gets hand-labelled once it reaches `labeling_in_progress`. It shares `AnnotateStage`/`VideoPlayer`/`FighterOverlay` with the Player, but reads/writes **only** `label_events`/`label_spans` — never `fight_events` (pipeline predictions), so re-running the AI pipeline over a labelled fight can never destroy the labels.

**Palette-driven strikes/state/etc. (`taxonomy.ts` → `label_events`).** Every `ToolItem` in `TOOL_GROUPS` drives its palette button, keyboard shortcut, and the keyboard legend from one definition. Hand strikes (jab/hooks/uppercuts/elbow) carry `hasTarget: true` — plain key = head, `Shift`+key = body, read via `e.code` (not `e.key`, which a US layout maps to a different character under Shift) together with `e.shiftKey`. Kicks carry a `fixedTarget` instead (the action name already encodes it: `calf_kick`/`low_kick` → leg, `middle_kick` → body, `high_kick` → head). `successForAction` returns `null` for every strike except `knockdown` — landed-vs-missed is deferred, so nothing claims a strike landed by default.

**Span annotation (`O`/`P` keys → `label_spans`).** `round`/`corner_swap`/`excluded` spans share one table with a `kind` column. `round` spans are auto-seeded server-side from the AI-segmented `rounds` table on first `GET /label-spans/` and rendered as draggable blocks in `AnnotationTimeline`'s ROUNDS lane (edge-drag calls `onUpdateSpan`). `corner_swap`/`excluded` are start/end toggles: `Annotate.tsx`'s `openSpanRef` tracks the in-flight span id per kind so the second `O`/`P` press knows what to close — `toggleSpan()` creates a span with `end_frame=null` on open, `PUT`s `end_frame` to close it. `AnnotationTimeline` renders an open span dashed, running to the current playhead.

**"Finish Labeling" is gated.** `POST /fights/{id}/finish-labeling` (via `handleFinishLabeling`) 409s until every detected round has a confirmed `round` label-span — the backend check (`rounds_fully_annotated`), not anything client-side.

**Fight-state marks are change points, not spans.** `W`/`F`/`G` (STRIKING/CLINCH/GROUND) log a single-frame `label_event`; `AnnotationTimeline`'s STATE lane derives contiguous segments by pairing each mark with the next one chronologically (last mark implicitly runs to the end of the timeline in the UI — the harness-side derivation in `ai/eval/labels_db.py` instead runs it to the end of its round, which matters when exporting).
