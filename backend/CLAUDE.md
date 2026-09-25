# Fight AI — Backend

## Workflow
- Always apply changes directly to the local working directory
- Never open PRs or suggest creating pull requests

## What it does
FastAPI service that exposes fight data (fights, rounds, fighter frames, predictions, hand labels) stored by the AI pipeline and the Annotate frontend in PostgreSQL, and spawns/tracks the AI-venv pipeline as a subprocess.

## Project Structure
```
backend/
├── app/
│   ├── main.py               # FastAPI app + router registration + startup pid reconciliation
│   ├── api/
│   │   └── routes/
│   │       ├── fights.py     # /fights/ endpoints (see below) — upload, video, events,
│   │       │                 #   finish-labeling, corners, delete
│   │       ├── fighters.py   # /fighters/ endpoints (CRUD-lite + per-fighter events)
│   │       └── tracking.py   # /tracking/ endpoints
│   ├── models/
│   │   ├── fight.py          # Fight model (state, pid, labeled_at, purpose, FIGHT_PURPOSES,
│   │   │                     #   reported/decoded_frames,
│   │   │                     #   segmentation_needs_review/_reason,
│   │   │                     #   red/blue_fighter_id) + FightResponse
│   │   ├── fight_event.py    # FightEvent — the ONE events table, holding both pipeline
│   │   │                     #   predictions and hand labels, told apart by `source`
│   │   │                     #   ('prediction'|'label') and `kind` ('point'|'round'|
│   │   │                     #   'corner_swap'|'excluded') — see "Predictions vs. labels"
│   │   │                     #   below. + FightEventCreate/Update/Response
│   │   ├── fighter.py        # Fighter model + FighterResponse + FighterCreate
│   │   ├── fighter_frame.py  # FighterFrame model (corner) + FighterFrameResponse
│   │   └── round.py          # Round model + RoundResponse
│   ├── services/
│   │   ├── event_service.py        # get_events_by_fight(filters), create_event()/
│   │   │                           #   update_event()/delete_event() — the single home for
│   │   │                           #   both predictions (read-only from here) and hand
│   │   │                           #   labels (full CRUD, always source='label'); also
│   │   │                           #   auto-seeds `round`-kind label events from `rounds`
│   │   │                           #   on first label fetch, and rounds_fully_annotated()
│   │   ├── fight_service.py        # get_all_fights(), create_fight(), finish_labeling(),
│   │   │                           #   reopen_labeling(), set_fight_pid()/get_fight_pid(),
│   │   │                           #   pid reconciliation
│   │   ├── fighter_service.py      # get_fighters(search), create_fighter(), get_events_by_fighter(), set_fight_corners()
│   │   ├── fighter_frame_service.py # get_fighter_frames(fight_id)
│   │   ├── round_service.py        # get_rounds(fight_id)
│   │   └── pipeline_runner.py      # extract_video_meta(), run_validation_async(),
│   │                                #   run_pipeline_async(), terminate_pipeline() — spawns
│   │                                #   into the ai/ venv; _AI_ENTRYPOINTS gates what a
│   │                                #   recorded pid is allowed to kill
│   └── utils/
│       ├── db.py                    # SQLAlchemy SessionLocal + run_db_query helper
│       └── fight_state_listener.py  # LISTEN fight_state (pg_notify) → fans out to /fights/stream SSE
```

## API Routes

### `/fights/` router
| Method | Path | Description |
|--------|------|-------------|
| GET | `/fights/` | List all fights (`FightResponse[]`) |
| GET | `/fights/stream` | SSE stream of `{id, state}` on every state change (snapshot on connect, then live via `pg_notify('fight_state', …)`) |
| POST | `/fights/upload` | Upload a video (`purpose=training_data\|reference\|ai_labeled`, required); creates the fight row (`state='validating'`) and spawns the full-decode validator, which spawns the pipeline itself on success. `purpose` also picks the track — only `ai_labeled` runs the full pipeline; the two labelling purposes get `skip_events` |
| GET | `/fights/{fight_id}/rounds/` | Rounds for a fight (`RoundResponse[]`) — AI segmentation output |
| GET | `/fights/{fight_id}/frames/` | Fighter bounding boxes + keypoints per frame (`FighterFrameResponse[]`); optional `start_frame`/`end_frame` (1-based, inclusive) narrow this to a window — a full fight's keypoints run into the tens of MB (see frontend CLAUDE.md's "Fighter-frame payload size"), so ClipPlayer's ~0.6s review clip passes its own window instead of downloading the whole fight just to draw ~30 frames of it. `ix_fighter_frames_fight_frame` covers `(fight_id, frame)`, so a ranged query stays index-only regardless of fight length |
| GET | `/fights/{fight_id}/events/` | Every event row for a fight (`FightEventResponse[]`); optional `fighter_id` / `action` / `success` / `kind` / `source` query filters. Pass `source=prediction` for the Player (pipeline output, read-only from here — never written through this route) or `source=label` for Annotate (hand-authored, full CRUD below); a `source=label` fetch also auto-seeds `kind='round'` events from the `rounds` table the first time it's called for a fight |
| POST | `/fights/{fight_id}/events/` | Create a hand-labelled event or span (`FightEventCreate` → `FightEventResponse`) — always written as `source='label'`; the client cannot request `source='prediction'`. `kind='point'` (default) needs `description` only when `action='fight_end'` — every other point event is reconstructed client-side from `action`/`target`/`corner` (see "Description is reconstructed, not stored" below); `kind` in `round`/`corner_swap`/`excluded` is a span (`frame`=start, `end_frame` nullable = still open) |
| PUT | `/fights/{fight_id}/events/{event_id}` | Update a span's `frame`/`end_frame`/`value` (`FightEventUpdate`) — 404 if the row doesn't exist, isn't `source='label'`, or is `kind='point'` (point labels are create+delete-only, same as before the merge) |
| PUT | `/fights/{fight_id}/events/{event_id}/verify` | Training Data QA's write path — sets `is_verified` (`FightEventVerify`, tri-state true/false/null) on a hand-labelled point event. 404 if the row doesn't exist, isn't `source='label'`, or isn't `kind='point'` — the exact opposite scope from the plain `PUT` above |
| DELETE | `/fights/{fight_id}/events/{event_id}` | Delete a hand-labelled event or span — 404 if the row doesn't exist or isn't `source='label'` (this is the guard that makes it impossible to delete a prediction through this route) |
| POST | `/fights/{fight_id}/finish-labeling` | `labeling_in_progress → labeling_complete`, sets `labeled_at`; 409 if every detected round doesn't yet have a confirmed `round`-kind label event |
| POST | `/fights/{fight_id}/reopen-labeling` | The reverse: `labeling_complete → labeling_in_progress`, so Annotate will edit an already-labelled fight; `finish-labeling` is the way back. Leaves `labeled_at` set (the eval code keys on it — clearing it would drop a reference fixture off the Accuracy page mid-edit); `finish-labeling` re-stamps it when the edit is finalised. 409 unless the fight is `labeling_complete` — which also excludes every `ai_labeled` fight, since those end at `completed` |
| GET | `/fights/{fight_id}/video` | Streams the source video file |
| DELETE | `/fights/{fight_id}/` | Kill any running pipeline/validator for this fight, delete the video file, then the row (child rows cascade) |

**No route exists to reassign `red_fighter_id`/`blue_fighter_id` after upload** (a `PATCH /corners/` was documented here previously but was never actually implemented — `fighter_service.py` has no corresponding function). If a fight's corners are backward relative to the footage, that's cosmetic only — `fight_events.corner`/`fighter_frames.corner` are what training reads, not the fighter-name mapping — but there's currently no UI/API path to fix the displayed names short of a direct DB update.

### `/fighters/` router
| Method | Path | Description |
|--------|------|-------------|
| GET | `/fighters/` | List/search fighters (`FighterResponse[]`); optional `search` (ILIKE on names/nickname) |
| POST | `/fighters/` | Create a fighter (`FighterCreate` → `FighterResponse`) |
| GET | `/fighters/{id}/` | Single fighter (404 if not found) |
| GET | `/fighters/{id}/events/` | Cross-fight predicted events for a fighter (`FightEventResponse[]`); optional `action` (prefix) / `success` filters — serves "all jabs fighter X landed". No explicit `source` filter needed: `fighter_id` is only ever set on `source='prediction'` rows (DB CHECK), so this query already excludes every hand label |

## Models / Schemas

### `FightResponse`
`id`, `video_path`, `fps` (int), `width`, `height`, `created_at`, `state`, `labeled_at` (nullable), `purpose`, `reported_frames`/`decoded_frames` (nullable — full-decode validation result, populated when `state=invalid`), `segmentation_needs_review`/`segmentation_review_reason` (whether the AI round list was corroborated by the scoreboard — written by the pipeline via `ai/database.py`'s `set_segmentation_review`, never by labelling; drives the Annotate page warning banner), `red_fighter_id`/`blue_fighter_id` (nullable), `red_fighter_name`/`blue_fighter_name` (nullable, joined in).

`fps` lets the frontend map video time → frame number.
`width` / `height` are the video's native resolution; the overlay uses them to scale bbox coords.
`state` is one of `validating|invalid|queued|detecting|tracking|pose|corners|scoreboard|segmenting|analyzing|completed|failed|labeling_in_progress|labeling_complete` — see `frontend/src/types/Fight.ts` for the full state machine and helper predicates (`isFightViewable`, `isLabelingReady`, `isInvalid`).
`labeled_at` is the durable "ground truth finalised" marker.
`purpose` is what the video is *for*: `training_data` (labels feed model training), `reference` (held out of training; scored against to measure pipeline accuracy) or `ai_labeled` (produced by the full AI pipeline). Vocabulary lives in `FIGHT_PURPOSES` (`models/fight.py`), validated in the upload handler.
**`purpose` is written once by `POST /fights/upload` and never again**, and a fight's pipeline is never re-run after that. Nothing in `ai/` writes it, and `run_pipeline`'s `ON CONFLICT (video_path) DO UPDATE` must never add it to its `SET` list. Pipeline accuracy is validated by uploading the *same* source video a second time as a brand-new fight (`purpose='ai_labeled'`, a different `fight_id`) and comparing its predictions against the first upload's hand labels across the two fight IDs — never by re-processing an already-labelled fight in place. There is no API or UI to change `purpose` after upload; a mistake needs a manual `UPDATE`.

### `FighterResponse` / `FighterCreate`
`FighterResponse`: `id`, `first_name`, `last_name`, `nickname` (nullable), `created_at`.
`FighterCreate`: `first_name`, `last_name`, `nickname` (optional).

### `FighterFrameResponse`
`fight_id`, `frame` (1-based), `corner` (0=red, 1=blue — formerly `fighter_id`), `x1`, `y1`, `x2`, `y2`, `confidence`, `keypoints`

### `RoundResponse`
`id`, `fight_id`, `round_number`, `start_frame` (1-based), `end_frame` (1-based)

### `FightEventResponse` / `FightEventCreate` / `FightEventUpdate` / `FightEventVerify`
One row shape covers pipeline predictions, hand-labelled point events, and hand-labelled spans:

`id`, `fight_id`, `source` (`prediction`|`label` — who wrote the row), `kind` (`point`|`round`|`corner_swap`|`excluded` — what shape the row is), `frame` (1-based; the start frame for a range kind), `end_frame` (nullable — null for `kind='point'`; for a range kind, null means a start/end toggle is still open), `description` (nullable — required only for `action='fight_end'`; null for every other row, including every other `kind='point'` row and every range kind), `fighter_id` (nullable, FK to `fighters` — **prediction-only** resolved identity), `corner` (nullable int, 0=red/1=blue — **label-only** track-slot, not a resolved person, null for state marks), `action` (nullable), `target` (nullable — head/body/leg), `success` (nullable bool), `state` (nullable — STRIKING/CLINCH/GROUND on a prediction state-change row), `value` (nullable — range-kind-only: round number, or exclusion reason), `labeler` (nullable), `created_at`, `is_verified` (nullable bool — Training Data QA's verdict on a `source='label'` `kind='point'` row: True=confirmed training-worthy, False=declined, NULL=not reviewed; untouched by everything else, including the pipeline and Annotate's own writes). `FightEventVerify` (`{is_verified}`) is the sole payload for `PUT .../verify`.

### Description is reconstructed, not stored

`fight_end` is the only action with no structured way to rebuild its text (winner/method/detail aren't columns), and the AI pipeline can never emit it (manual-labelling only) — so it's the one case still enforced by both a Pydantic validator and a DB `CHECK` (`ck_fight_events_point_has_description`). Every other point event — predictions and labels alike — has `description = NULL` and is reconstructed client-side on every render, from `action`/`target`/`corner` (labels, via the same `taxonomy.ts` templates that used to build the stored string) or `action`/`fighter_id`/`success`/`state` (+ the `rounds` table, for round markers) for predictions. See `frontend/src/utils/describeEvent.ts`.

The reason this needs to be a *reconstruction*, not a one-time backfill: a `corner_swap` label span can be added or edited after a strike was already logged, and a frozen string has no way to reflect that. Recomputing on every render is what makes the display correct immediately, no matter when the swap was marked relative to when the strike was.

`FightEventCreate` (the Annotate frontend's only write shape) has no `source` field at all — the service always writes `source='label'`, so a client request can never spoof a prediction row.

## Frame-numbering contract
All `frame`/`end_frame` values are **1-based** (first frame of the video = 1), matching the AI pipeline writer. The frontend converts `currentTime` via `Math.floor(currentTime * fps) + 1`.

## Predictions vs. labels — never mix them
Both live in `fight_events` now, told apart by two columns rather than by physical table separation: `source` (`prediction`|`label` — who wrote the row) and `kind` (`point`|`round`|`corner_swap`|`excluded` — what shape the row is). `process_fight()`/`write_frames_and_rounds()` `DELETE ... WHERE fight_id = :fid AND source = 'prediction'` and rewrite only that scope on every pipeline run — a hand label can never be deleted by a pipeline run because the delete is scoped to `source='prediction'`. `event_service.delete_event()`/`update_event()` are the mirror image: scoped to `source='label'`, so the Annotate API can never touch a prediction row. Two DB `CHECK` constraints back this up structurally — `corner` can only be set when `source='label'`, `fighter_id` only when `source='prediction'` — so the two provenances can't be confused even by a hand-written query. This reintroduces, at the row level, the same guarantee the old `fight_events`/`label_events`/`label_spans` table split gave physically: **any new query against this table needs an explicit `source` and/or `kind` filter, or it will blend predictions and labels.**

## Upload / validation / pipeline pid handoff
`POST /fights/upload` creates the fight row at `state='validating'` and spawns `pipeline_runner.run_validation_async()`, which runs `eval.cli video --fight-id <id>` in the `ai/` venv. That process full-decodes the video, writes `reported_frames`/`decoded_frames`, and either sets `state='invalid'` (truncated file, pipeline never runs) or clears `pid`, spawns `main.py` itself, and writes the new pid — all via `ai/database.py`'s `set_fight_state`/`set_video_check`/`set_fight_pid`, which is why every transition reaches the SSE stream with no backend involvement. `pipeline_runner._AI_ENTRYPOINTS` lists every command-line marker (`main.py`, `eval.cli`) a recorded pid is allowed to belong to — `DELETE /fights/{id}` only signals a pid that's still one of these, so a recycled OS pid can never be killed by mistake. Any new AI-venv job spawned from `pipeline_runner.py` must add its marker there.

## Environment
- `DATABASE_URL` env var required (PostgreSQL connection string)
- `VIDEO_BASE_DIR` — resolves relative `video_path`s and is where `fight_videos/` is created on upload
- `AI_DIR` / `AI_PYTHON` (optional) — override the `ai/` venv location `pipeline_runner.py` spawns into; default to `../ai` and `../.venv/bin/python`
- `KEEP_VIDEO_ON_DELETE` (dev only) — skip deleting the video file on `DELETE /fights/{id}`
- Run with `uvicorn app.main:app --reload` from the `backend/` directory
