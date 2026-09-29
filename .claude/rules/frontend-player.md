---
paths:
  - "frontend/src/pages/Player.tsx"
  - "frontend/src/components/player/**"
  - "frontend/src/components/FighterOverlay.tsx"
  - "frontend/src/components/VideoPlayer.tsx"
---

# Player page and fighter overlay

## Player
- **Event source by purpose:** Player reads `source='prediction'` for an `ai_labeled` fight and `source='label'` otherwise. A fight never re-runs, so exactly one source has content. It always fetches `corner_swap` spans from the labels.
- **`LiveFeed` props:**
  - `redName`/`blueName`.
  - `redFighterId`, to resolve a prediction's `fighter_id`.
  - `rounds`, to recover a round marker's number.
  - `cornerSwapSpans`. The fighter name is swap-corrected for **each event's own frame**, not the playhead.
- **Viewable fights** are those where `isFightViewable` holds (`completed` or `labeling_complete`). Otherwise Player shows the processing state.
- **Edit labels** (for a `labeling_complete` fight, `isLabelEditable`):
  1. Call `reopenLabeling()` and wait for it to succeed.
  2. Only then navigate to `/fights/{id}/annotate`, because Annotate only opens on `labeling_in_progress`.
  3. If the user leaves mid-edit, the fight stays `labeling_in_progress` with `labeled_at` set. Player then shows "labels are being edited" with **Continue editing**.
- **Responsive:** `narrow = useWindowWidth() < 1100` collapses the top grid to one column, and the live feed becomes a fixed-height block.

## `FighterOverlay`
- It is a `<canvas>` absolutely positioned over the video, with `pointer-events: none`. `VideoPlayer` accepts `children` so the overlay sits inside its `position: relative` container.
- Scale boxes from the fight's native `width`/`height` to the canvas's display size. Never use the video element's intrinsic size.
- `corner` 0 draws red and 1 draws blue. Inside a `corner_swap` span the colours flip (see "Corner-swap correction" in `frontend/CLAUDE.md`).
- `highlightCorner` limits boxes to one corner. `hideUnhighlighted`, which only Training Data QA uses, also hides the other fighter's skeleton. Both are off by default.
