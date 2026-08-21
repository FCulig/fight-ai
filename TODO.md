# TODO

Quick-capture list for bugs/gaps found while manually labelling fights.
Not part of the formal [PLAN.md](PLAN.md) — triage into a plan chunk if these
turn out to be bigger than a small fix.

## 1. Fight state is modeled as if it belongs to a corner/fighter

Found while labelling: fight state (STRIKING/CLINCH/GROUND) is conceptually a
property of the *fight*, not of a corner or fighter, but it's stored through
the same `label_events` row shape as fighter-scoped events (strikes,
takedowns), which carries `corner`/`target`/`success` columns that make no
sense for a state mark.

- `backend/app/models/label_event.py` — `LabelEvent`/`LabelEventCreate`: single
  table for both fighter-scoped and fight-scoped events.
- `frontend/src/components/annotate/taxonomy.ts:85-87` — `state_striking` /
  `state_clinch` / `state_ground` already have `needsFighter: false`, and
  `frontend/src/pages/Annotate.tsx:268` already sends `corner: null` for them,
  so today's writes are *correct*, but nothing stops a future palette item or
  a direct API call from attaching a corner to a state mark — there's no
  schema-level guarantee.
- Same shape issue for `fight_events` on the pipeline side
  (`backend/app/models/fight_event.py`, `ai/fight_processing/fight_processing.py`)
  and for the harness (`ai/eval/labels_db.py:117-124`, `ai/eval/schema.py`).

Decide: either split fight-state marks into their own table/endpoint (no
`corner` column at all), or explicitly document+enforce (DB constraint or
Pydantic validator) that `corner` must be NULL when `action` starts with
`state_`. Same question applies to `fight_end`, which also has no fighter.

## 2. No event type for a *successful* takedown

Taxonomy only has `takedown_attempt` and `takedown_defended`
(`frontend/src/components/annotate/taxonomy.ts:71-72`) — there's no way to
mark a takedown that actually landed. A `GROUND`/`CLINCH` state mark implies
*something* changed position, but doesn't distinguish a successful takedown
from e.g. a pull-guard or a slip into the clinch.

Needs:
- New `ToolItem` in `taxonomy.ts` (e.g. `takedown_landed` / `takedown_successful`),
  with a keybinding and palette entry — `needsFighter: true` (it's the
  attacker's takedown).
- `ai/eval/labels_db.py:126-129` currently skips any action not in
  `LABEL_FAMILY_MAP` (comment: "state/takedown/knockdown/fight_end — not part
  of the strike/state schema yet") — decide whether takedowns need their own
  field on `ai/eval/schema.py`'s `FightLabels` (parallel to `strikes`/`states`)
  so they can be scored, or if this is UI-only for now.

## 3. No ground-and-pound punch / knee-or-leg-kick option in the palette

`frontend/src/components/annotate/taxonomy.ts:65` only has a single generic
`knee` action ("knee in the clinch") and no ground-strike actions at all — the
hand strikes (jab/hooks/uppercuts) and `knee` don't distinguish standing vs.
clinch vs. ground, so a labeller currently has no way to mark "punch landed
while on top in GROUND" or "knee/leg strike thrown from top position" as
distinct from an open-range or clinch strike.

The pipeline side already has this distinction — `ai/CLAUDE.md`'s strike
vocabulary table lists `clinch_punch`/`clinch_knee` (standing clinch) vs.
`ground_punch`/`ground_knee` (ground-and-pound), detected via
`detect_strikes(..., grappling=True, ground=True)` in
`ai/fight_processing/fight_processing_util.py`. The manual taxonomy needs the
same split so hand-labels can be compared against pipeline predictions.

Needs:
- New `ToolItem`s for `ground_punch` and `ground_knee` (or a leg-kick-from-top
  variant) in the `Grappling`/`Strikes` group of `taxonomy.ts`, each
  `needsFighter: true`, with their own keybindings.
- Wire them into `LABEL_FAMILY_MAP` in `ai/eval/labels_db.py:28-41` (currently
  only maps open-range punch/kick families) so they land in `FightLabels.strikes`
  with the right `family` for scoring against `clinch_punch`/`ground_punch`/etc.
  pipeline predictions.

## 4. Round span and fight state don't truncate at `fight_end`

Logging a `fight_end` event (KO/TKO/submission/decision — `Annotate.tsx:286-303`
via `FightEndModal.tsx`) doesn't affect anything else on the timeline: the
round it happened in and the last fight-state segment both keep running past
it, as if the fight kept going.

- **Round span** — `label_spans` (`kind='round'`) are seeded once from the
  AI-detected `rounds` table (`backend/app/services/label_span_service.py:10-33`)
  and never adjusted based on `label_events`. On an early stoppage the seeded
  round `end_frame` is whatever the AI segmentation guessed (typically the
  scheduled round length), which now runs past the real end of the fight.
- **Fight state** — the last `state_*` mark is drawn/derived as running to the
  end of the timeline: to end-of-video in the UI
  (`frontend/src/components/annotate/AnnotationTimeline.tsx:119-127`) and to
  end-of-round at export time (`ai/eval/labels_db.py:115-124`). Neither stops
  at `fight_end`'s frame.
- `frontend/src/components/annotate/AnnotationTimeline.tsx:118,355` already
  special-cases `fight_end` as a marker on the ROUNDS lane, so the frame is
  available where this would need to be wired in.

Needs: when a `fight_end` label event exists, clamp the containing round's
`end_frame` and the final state segment's end to `fight_end.frame`, both in
the UI (`AnnotationTimeline`) and in the harness export (`labels_db.py`) —
and decide whether `finish-labeling`/`label_span_service` should auto-adjust
the seeded round span server-side rather than relying on the labeller to
manually drag the round's end edge back.

## 5. Shift-for-body isn't reflected in the live feedback, only the saved description

Holding Shift while logging a hand strike already changes the *stored*
`description` correctly — `handStrikeText()` in `taxonomy.ts:32-44` bakes in
whichever `target` `Annotate.tsx:270` resolved (`shiftKey ? 'body' : 'head'`),
so `AnnotationList.tsx:55` (which renders `e.description` verbatim) already
shows "Jab to the body" after the fact. What's missing is *live* feedback at
the moment of logging:

- `Annotate.tsx:282` — the toast shown right after logging uses
  `item.name` only (e.g. "Jab"), not the resolved description, so it never
  says "to the body" even though that's what got saved.
- `EventPalette.tsx:26,41` — the palette button always renders the static
  `it.name` and a static tooltip (`"${it.name} · Shift = body"`), it doesn't
  update while Shift is held to preview which target is about to be logged.

Needs: have the toast in `logTool` (`Annotate.tsx:258-284`) show the resolved
`description` (or at least append `to the ${target}` for `hasTarget` items)
instead of bare `item.name`, and consider live-updating the palette button
label/tooltip on `shiftKey` state so it previews "Jab · Body" before the key
is pressed.
