---
paths:
  - "frontend/src/pages/Annotate.tsx"
  - "frontend/src/components/annotate/**"
  - "frontend/src/utils/describeEvent.ts"
---

# Annotate page (manual labelling)

- **Reads and writes labels only:** `useEvents(fightId, { source: 'label' })` plus `createEvent`/`updateEvent`/`deleteEvent`, all of which the backend scopes to `source='label'`. Point `events` and `spans` (any non-point kind) are derived from that one result with `useMemo`. Annotate opens only when `state` is `labeling_in_progress`.
- **Every modal needs a keyboard guard.** Mirror the modal's open state into a ref and check it in the global keydown handler, the way `endOpenRef` and `confirmDeleteRef` work. Otherwise keys keep writing label events and spans underneath the overlay.

## Point events (palette and keys)
- Each `ToolItem` in `annotate/taxonomy.ts` `TOOL_GROUPS` defines its palette button, shortcut and legend entry together. Add new tools there.
- **Hand strikes** (`hasTarget`): the plain key means head and Shift+key means body. Read `e.code` plus `e.shiftKey`, not `e.key`, because Shift changes `e.key` on a US layout.
- **Kicks** carry a `fixedTarget`.
- `successForAction` returns `true` only for outcome actions (`knockdown`, `takedown_landed`). Strikes get `null`: landed/missed is deferred, so never default a strike to landed.
- **Create payloads have no `description`.** `ToolItem.text()` builds only the toast. `describeEvent` rebuilds text through `ACTION_TO_TOOL`, a reverse index over `TOOL_GROUPS`. Only `fight_end`, built in `confirmFightEnd`, sends a description.
- `Annotate.tsx` builds one `describe(e)` closure (fighter names plus this fight's `corner_swap` spans) and passes it through `AnnotationPanel` to both `AnnotationList` and `AnnotationTimeline`. Never read `e.description` there. That way, marking a swap instantly corrects strikes that were already logged.
- **Fight-state marks** (`W`/`F`/`G`) are change points, not spans. The timeline's State lane pairs each mark with the next one. In the UI the last mark runs to the end of the timeline, but `ai/eval/labels_db.py` ends it at the end of its round.

## Spans (`O` and `P` keys)
- **`round`** spans are seeded server-side from `rounds` on first fetch. They show as draggable blocks in the Rounds lane, and edge-drag → `onUpdateSpan` → `PUT frame/end_frame`.
- **`corner_swap` and `excluded`** are start/end toggles. `openSpanRef` holds the in-flight id for each kind: the first press creates the span with `end_frame=null`, and the second press `PUT`s `end_frame`. An open span draws dashed up to the playhead.

## Finish and re-edit
- **Finish Labeling** is gated server-side: it returns 409 until every round has a confirmed `round` label. Don't duplicate the check client-side. On success it returns to Player with `replace`, so Back can't land on Annotate's "already labeled" screen.
- **Re-editing** (`isEditingLabels` = `labeling_in_progress && labeled_at !== null`) shows the "Edit labels" title. `needsRoundReview` also checks `labeled_at`, so the unverified-rounds banner doesn't come back during an edit. The "already labeled" screen offers the same **Edit labels** action.
