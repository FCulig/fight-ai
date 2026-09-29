---
paths:
  - "frontend/src/pages/TrainingDataQA.tsx"
  - "frontend/src/components/trainingData/**"
  - "frontend/src/hooks/useTrainingDataEvents.ts"
  - "frontend/src/utils/trainingData*.ts"
---

# Training Data QA (`/training-data`)

A reviewer's pass over every hand-labelled training-class point event, across **all** `training_data` fights. It is the only page not scoped to one `fightId`.

## Corpus (`useTrainingDataEvents`)
- It takes every `purpose='training_data'` fight in `labeling_in_progress` or `labeling_complete`, then each fight's `source='label' kind='point'` events filtered to `TRAINING_ACTIONS`.
- `TRAINING_CLASSES` are the `needsFighter` items of Annotate's `TOOL_GROUPS`, minus `takedown_attempt`, `takedown_defended`, `submission_attempt`, `knockdown` and every `state_*` mark.
- **Never include `reference` fights.** Their labels are held-out ground truth, and a verdict here feeds training, so including them would leak the eval set.
- **Two corner fields:**
  - `displayCorner` is `corner` flipped by the fight's swap spans. Use it for the Red/Blue text and dot.
  - Raw `corner` goes to `ClipPlayer`'s `highlightCorner`, because it matches the unswapped slot space of `fighter_frames`.

## Navigation
- Every level is a real route: `/training-data` (`ClassGrid`) → `/:action` (`EventTable`) → `/:action/:eventId` (`EventReview`). The view is derived from `useParams`, with no local view state.
- Deliberate navigation `push`es. In-review stepping (arrow keys, "up next", post-verdict auto-advance) uses `replace`.
- The "done" screen is `navigate(..., { state: { justFinished: true } })` on the class URL, not a separate route, so reloading shows the table.

## Verdicts (`fight_events.is_verified`)
- `setVerdict` updates optimistically and refetches on failure.
- `act(target)` in `EventReview` computes `v === target ? null : target`, so clicking the current verdict clears it. This is the only source of `null`.
- Clearing never auto-advances. Setting a verdict advances to the next pending event after about 170 ms, or to the done screen after about 240 ms.
- **Retyping a strike:** `EventReview`'s type select calls `reclassifyEvent` (`PUT …/reclassify`) with `reclassifyPayload()` from `trainingDataTaxonomy.ts`. That function computes `target`/`success` the same way Annotate's palette does for a fresh label. The event keeps its `corner` and its verdict.

## `ClipPlayer`
- **It plays the real video**, windowed to `CLIP_DURATION_SECS` (0.6 s) around the event. The window is converted to whole frames with `Math.round(0.6 * fps)` and loops during playback.
- It fetches only its own window of fighter frames, the ranged `useFighterFrames` call.
- The design mockup's synthesised clip and "automatic checks" panel were dropped on purpose, because no real signal backs them. Don't fake one.
- Only the attacker's skeleton is drawn (`hideUnhighlighted`).
- Speed options are `[0.25, 0.5, 1]`, defaulting to 0.5×, persisted in `localStorage['td-clip-speed']`.
- The skip buttons step one frame, clamped to the clip window.
