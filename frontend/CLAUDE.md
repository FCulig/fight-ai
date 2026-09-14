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
│   ├── Event.ts          # ONE shape for both pipeline predictions and hand labels,
│   │                      #   told apart by `source`/`kind`: { id, fight_id, source
│   │                      #   ('prediction'|'label'), kind ('point'|'round'|
│   │                      #   'corner_swap'|'excluded'), frame, end_frame (null
│   │                      #   for kind='point'), description (null except for
│   │                      #   action='fight_end' — see utils/describeEvent.ts),
│   │                      #   fighter_id (prediction-only), corner
│   │                      #   (label-only, 0=red/1=blue — a track-slot, not a
│   │                      #   resolved person), action, target, success, state
│   │                      #   (prediction-only), value (range-kind-only),
│   │                      #   labeler, created_at }
│   ├── Fight.ts           # { id, video_path, fps, width, height, created_at, state,
│   │                      #   labeled_at, purpose, reported_frames, decoded_frames,
│   │                      #   segmentation_needs_review/_reason, red/blue_fighter_id }
│   │                      #   + STATE_LABELS/STATE_PROGRESS/TERMINAL_STATES maps,
│   │                      #   FightPurpose + PURPOSE_LABELS/_COLORS/_ICONS, and
│   │                      #   isFightViewable/isLabelingReady/isInvalid/needsRoundReview
│   │                      #   predicates
│   ├── FighterFrame.ts   # { fight_id, frame, corner, x1, y1, x2, y2, confidence }
│   └── Round.ts          # { id, fight_id, round_number, start_frame, end_frame }
├── services/
│   └── api.ts            # fetchEvents(fightId, params) (source/kind/fighter_id/action/
│                          #   success filters), createEvent/updateEvent/deleteEvent
│                          #   (Annotate's write path — always source='label' server-side),
│                          #   fetchFights, fetchFighterFrames, fetchRounds, uploadFight,
│                          #   deleteFight, finishLabeling
├── hooks/
│   ├── useEvents.ts       # fetches events for a fightId with optional {source, kind,
│   │                      #   fighter_id, action, success} params, exposes a setter for
│   │                      #   optimistic updates — Player passes {source:'prediction'},
│   │                      #   Annotate passes {source:'label'} and derives its own
│   │                      #   point-event/span slices from the one result via useMemo
│   ├── useFights.ts       # fetches all fights, exposes selectedFightId state (defaults to latest)
│   ├── useFightStream.ts  # subscribes to /fights/stream SSE, patches `state` into the fights list live
│   ├── useFighterFrames.ts # fetches frames for selectedFightId → Map<frame, FighterFrame[]>
│   ├── useRounds.ts      # fetches rounds for selectedFightId
│   └── useWindowWidth.ts # responsive breakpoint helper
├── mocks/
│   └── fightMock.ts      # hardcoded mock data (fighters, stats, pace, form) — see TODO_BACKEND_DATA.md
├── utils/
│   ├── describeEvent.ts  # Reconstructs an Event's display text on demand (description is
│   │                     #   only ever stored for action='fight_end') from action/target/
│   │                     #   corner (labels, via annotate/taxonomy.ts's ToolItem.text()
│   │                     #   templates) or action/fighter_id/success/state + `rounds`
│   │                     #   (predictions) — used by both LiveFeed and AnnotationList/Timeline
│   ├── eventTaxonomy.ts  # categoryForAction/colorForAction/iconForAction — action-driven,
│   │                     #   shared by LiveFeed (Player) and annotate/taxonomy.ts (re-exports
│   │                     #   these for its existing importers)
│   ├── cornerSwap.ts     # isFrameSwapped(frame, spans) — shared by FighterOverlay (box/
│   │                     #   skeleton colour) and describeEvent (fighter-name resolution)
│   └── liveStats.ts      # deriveStatsForRange/derivePaceBuckets — FIGHT STATISTICS/MOMENTUM,
│                         #   attributes strikes via fighter_id (predictions, vs. fights.
│                         #   red_fighter_id) or corner (labels), never via description text
├── components/
│   ├── FighterOverlay.tsx  # canvas overlay for fighter bounding boxes
│   ├── VideoPlayer.tsx     # <video> wrapper with play/seek gestures; accepts children for overlays
│   ├── VideoControls.tsx   # playback controls + scrubber
│   ├── FrameInfo.tsx       # frame / ms / fps display
│   ├── Header.tsx          # top nav
│   ├── CornerSelect.tsx    # fighter search/create combobox, used by the upload dialog
│   ├── FightPurposeBadge.tsx # training_data/reference/ai_labeled chip — fight list
│   │                       #   subtitle + Player and Annotate headers
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
│       ├── LiveFeed.tsx    # real-event chat feed with filter pills + click-to-seek —
│       │                   #   text via utils/describeEvent.ts, category/colour/icon via
│       │                   #   utils/eventTaxonomy.ts (no more regex-over-description)
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
    ├── Annotate.tsx        # manual-labelling page — reads/writes fight_events rows with source='label'
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
`LiveFeed` drives on **real** backend events (same `useEvents` hook) — `{ source: 'prediction' }` for an `ai_labeled` fight, `{ source: 'label' }` otherwise (a fight is never re-run, so exactly one source ever has real content — see "Fight purpose" below). Each event's category/colour/icon come from `utils/eventTaxonomy.ts`'s `categoryForAction`/`colorForAction`/`iconForAction`, driven entirely by the structured `action` column; its display text comes from `utils/describeEvent.ts`, reconstructed from `action`/`target`/`corner` (labels) or `action`/`fighter_id`/`success`/`state` (predictions) — never from `description`, which is only ever stored for `action='fight_end'`. `LiveFeed` is passed `redName`/`blueName`, `redFighterId` (`fights.red_fighter_id`, to resolve a prediction's `fighter_id`), `rounds` (to recover a round marker's number), and `cornerSwapSpans` (to swap-correct a label event's fighter name for its own frame, independent of the current playhead). Filter pills (All / Strikes / Fight State / Grapple) and click-to-seek work the same way as the design reference.

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
6. Draw red rect for `corner === 0`, blue for `corner === 1` — **flipped** if the frame falls inside a `cornerSwapSpans` entry (`utils/cornerSwap.ts`'s `isFrameSwapped`), a display-only correction for a confirmed `corner_swap` label span. `fighter_frames.corner` itself is never touched — see `label-events-corner-is-box-not-person`.

`VideoPlayer` accepts `children` so `FighterOverlay` can be rendered inside the `position: relative` video container and stack correctly.

## Fight selector (Player.tsx)
- Populated from `useFights`, filtered to `isFightViewable(state)` (`completed` or `labeling_complete`)
- Defaults to the most recently processed fight (last element of the list)
- Changing selection re-fetches events, frames, and rounds for the new fight

## Fight purpose

`Fight.purpose` says what a video is *for*: `training_data` (labels feed model training),
`reference` (held out of training; scored against to measure pipeline accuracy) or
`ai_labeled` (produced by the full AI pipeline). It is chosen in `UploadDialog` and set
once server-side at upload — nothing can change it afterwards, and a fight's pipeline
never runs again after that first pass. Pipeline accuracy is validated by uploading
the *same* source video a second time as a brand-new fight (`purpose='ai_labeled'`,
a different fight_id) and comparing its predictions against the first upload's hand
labels across the two fight IDs — not by re-processing an already-labelled fight.

`UploadDialog` derives it from the two `ModeCard`s: **AI annotation** forces
`ai_labeled` (not user-selectable), **Self-annotate** reveals a radio row —
native `<input type="radio" name="fight-purpose">`, the only radio group in the app —
with **no default selected**, and the submit button stays disabled until one is picked.
That gate is deliberate: training and evaluation sets must stay disjoint, so the split
should never be decided by inattention. `uploadFight()` sends `purpose` as the sole
track selector; the old `mode: 'ai' | 'manual'` form field is gone, since `purpose`
already implies it.

`FightPurposeBadge` renders the chip. Its colours (`PURPOSE_COLORS` in `Fight.ts`)
deliberately avoid the corner colours `#ff4d4d`/`#3aa0ff` — a badge in either would read
as "red corner" — plus `#ef4444` (error) and `#f59e0b` (the rounds-unverified warning).

## Deleting a fight
`DELETE /fights/{id}` is irreversible — it kills any running pipeline, unlinks the video file, and
cascades away every fight_events row (predictions and hand labels alike), rounds and fighter frames. Two entry points, both
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

`Annotate.tsx` (`/fights/{id}/annotate`) is where a **manual**-mode upload gets hand-labelled once it reaches `labeling_in_progress`. It shares `AnnotateStage`/`VideoPlayer`/`FighterOverlay` with the Player, and calls the same `useEvents`/`GET /fights/{id}/events/` as the Player does — but always with `{ source: 'label' }`, and it only ever creates/updates/deletes through `createEvent`/`updateEvent`/`deleteEvent`, which the backend always writes as `source='label'`. The backend enforces the other half: `event_service.delete_event`/`update_event` are scoped to `source='label'` rows only, so nothing Annotate does can ever touch a `source='prediction'` row, even though both now live in one `fight_events` table.

**Palette-driven strikes/state/etc. (`taxonomy.ts` → `createEvent({ kind: 'point', ... })`).** Every `ToolItem` in `TOOL_GROUPS` drives its palette button, keyboard shortcut, and the keyboard legend from one definition. Hand strikes (jab/hooks/uppercuts/elbow) carry `hasTarget: true` — plain key = head, `Shift`+key = body, read via `e.code` (not `e.key`, which a US layout maps to a different character under Shift) together with `e.shiftKey`. Kicks carry a `fixedTarget` instead (the action name already encodes it: `calf_kick`/`low_kick` → leg, `middle_kick` → body, `high_kick` → head). `successForAction` returns `null` for every strike except `knockdown` — landed-vs-missed is deferred, so nothing claims a strike landed by default. `logTool()` no longer sends a `description` in the create payload for any of these — `ToolItem.text()` is only used locally to build the toast message; the stored row carries `action`/`target`/`corner` and its display text is reconstructed on every render by `utils/describeEvent.ts` (`ACTION_TO_TOOL`, a reverse index over `TOOL_GROUPS`, is what that reconstruction looks the `ToolItem` back up by). `fight_end` (built ad hoc in `confirmFightEnd`, not a `ToolItem`) is the one action that still sends and stores a real `description`.

`Annotate.tsx` builds one `describe(e)` closure (over `redName`/`blueName` and the fight's own `corner_swap` spans, via `utils/describeEvent.ts` + `isFrameSwapped`) and passes it down through `AnnotationPanel` to both `AnnotationList` and `AnnotationTimeline`, which call it instead of reading `e.description` anywhere (list rows, timeline clip titles, the hover tooltip) — so marking or editing a `corner_swap` span updates already-logged strikes' displayed fighter name immediately, with no backfill.

**Span annotation (`O`/`P` keys → `createEvent({ kind: 'round'|'corner_swap'|'excluded', ... })`).** `round`/`corner_swap`/`excluded` rows are the range-shaped `kind`s of the same `fight_events` table (`frame` = start, `end_frame` nullable). `round` events are auto-seeded server-side from the AI-segmented `rounds` table the first time Annotate fetches `source='label'` events for a fight, and rendered as draggable blocks in `AnnotationTimeline`'s ROUNDS lane (edge-drag calls `onUpdateSpan`, which `PUT`s `frame`/`end_frame`). `corner_swap`/`excluded` are start/end toggles: `Annotate.tsx`'s `openSpanRef` tracks the in-flight event id per kind so the second `O`/`P` press knows what to close — `toggleSpan()` creates one with `end_frame=null` on open, `PUT`s `end_frame` to close it. `AnnotationTimeline` renders an open span dashed, running to the current playhead. `Annotate.tsx` derives its `events` (kind='point') and `spans` (kind!='point') arrays from the one `useEvents(fightId, { source: 'label' })` result via `useMemo`.

**"Finish Labeling" is gated.** `POST /fights/{id}/finish-labeling` (via `handleFinishLabeling`) 409s until every detected round has a confirmed `round`-kind label event — the backend check (`rounds_fully_annotated`), not anything client-side.

**Fight-state marks are change points, not spans.** `W`/`F`/`G` (STRIKING/CLINCH/GROUND) log a single-frame `label_event`; `AnnotationTimeline`'s STATE lane derives contiguous segments by pairing each mark with the next one chronologically (last mark implicitly runs to the end of the timeline in the UI — the harness-side derivation in `ai/eval/labels_db.py` instead runs it to the end of its round, which matters when exporting).
