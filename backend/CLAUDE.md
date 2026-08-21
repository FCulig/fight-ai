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
│   │       ├── events.py     # GET /events/  (legacy, all pipeline predictions)
│   │       ├── fights.py     # /fights/ endpoints (see below) — upload, video, label-events,
│   │       │                 #   label-spans, finish-labeling, corners, delete
│   │       ├── fighters.py   # /fighters/ endpoints (CRUD-lite + per-fighter events)
│   │       └── tracking.py   # /tracking/ endpoints
│   ├── models/
│   │   ├── fight.py          # Fight model (state, pid, labeled_at, reported/decoded_frames,
│   │   │                     #   segmentation_needs_review/_reason,
│   │   │                     #   red/blue_fighter_id) + FightResponse
│   │   ├── fight_event.py    # FightEvent — PIPELINE PREDICTIONS ONLY (fighter_id/action/
│   │   │                     #   success/state) + FightEventResponse
│   │   ├── label_event.py    # LabelEvent — HAND LABELS ONLY (corner/action/target/success/
│   │   │                     #   labeler) + LabelEventCreate/Response
│   │   ├── label_span.py     # LabelSpan — round/corner_swap/excluded spans (start/end
│   │   │                     #   frame, value) + LabelSpanCreate/Update/Response
│   │   ├── fighter.py        # Fighter model + FighterResponse + FighterCreate
│   │   ├── fighter_frame.py  # FighterFrame model (corner) + FighterFrameResponse
│   │   └── round.py          # Round model + RoundResponse
│   ├── services/
│   │   ├── event_service.py        # get_fight_events(), get_events_by_fight(filters) — predictions
│   │   ├── label_event_service.py  # get/create/delete label_events
│   │   ├── label_span_service.py   # get (auto-seeds `round` spans from `rounds`), create,
│   │   │                           #   update, delete label_spans; rounds_fully_annotated()
│   │   ├── fight_service.py        # get_all_fights(), create_fight(), finish_labeling(),
│   │   │                           #   set_fight_pid()/get_fight_pid(), pid reconciliation
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
| POST | `/fights/upload` | Upload a video (`mode=ai\|manual`); creates the fight row (`state='validating'`) and spawns the full-decode validator, which spawns the pipeline itself on success |
| GET | `/fights/{fight_id}/rounds/` | Rounds for a fight (`RoundResponse[]`) — AI segmentation output |
| GET | `/fights/{fight_id}/frames/` | Fighter bounding boxes + keypoints per frame (`FighterFrameResponse[]`) |
| GET | `/fights/{fight_id}/events/` | Pipeline-predicted events scoped to a fight (`FightEventResponse[]`); optional `fighter_id` / `action` / `success` query filters — read-only, never written by the frontend |
| GET/POST/DELETE | `/fights/{fight_id}/label-events/` | Hand-labelled strike/state/etc. events (`LabelEventResponse[]`) — the Annotate page's only write path |
| GET/POST/PUT/DELETE | `/fights/{fight_id}/label-spans/` | Hand-labelled round/corner_swap/excluded spans; GET auto-seeds `round` spans from the `rounds` table on first call |
| POST | `/fights/{fight_id}/finish-labeling` | `labeling_in_progress → labeling_complete`, sets `labeled_at`; 409 if every detected round doesn't yet have a confirmed `round` label-span |
| GET | `/fights/{fight_id}/video` | Streams the source video file |
| DELETE | `/fights/{fight_id}/` | Kill any running pipeline/validator for this fight, delete the video file, then the row (child rows cascade) |

**No route exists to reassign `red_fighter_id`/`blue_fighter_id` after upload** (a `PATCH /corners/` was documented here previously but was never actually implemented — `fighter_service.py` has no corresponding function). If a fight's corners are backward relative to the footage, that's cosmetic only — `label_events.corner`/`fighter_frames.corner` are what training reads, not the fighter-name mapping — but there's currently no UI/API path to fix the displayed names short of a direct DB update.

### `/fighters/` router
| Method | Path | Description |
|--------|------|-------------|
| GET | `/fighters/` | List/search fighters (`FighterResponse[]`); optional `search` (ILIKE on names/nickname) |
| POST | `/fighters/` | Create a fighter (`FighterCreate` → `FighterResponse`) |
| GET | `/fighters/{id}/` | Single fighter (404 if not found) |
| GET | `/fighters/{id}/events/` | Cross-fight predicted events for a fighter (`FightEventResponse[]`); optional `action` (prefix) / `success` filters — serves "all jabs fighter X landed" |

### Legacy
| Method | Path | Description |
|--------|------|-------------|
| GET | `/events/` | All pipeline-predicted events regardless of fight (backwards compatibility) — read-only, `POST`/`DELETE` were removed once labelling moved to `label_events` |

## Models / Schemas

### `FightResponse`
`id`, `video_path`, `fps` (int), `width`, `height`, `created_at`, `state`, `labeled_at` (nullable), `reported_frames`/`decoded_frames` (nullable — full-decode validation result, populated when `state=invalid`), `segmentation_needs_review`/`segmentation_review_reason` (whether the AI round list was corroborated by the scoreboard — written by the pipeline via `ai/database.py`'s `set_segmentation_review`, never by labelling; drives the Annotate page warning banner), `red_fighter_id`/`blue_fighter_id` (nullable), `red_fighter_name`/`blue_fighter_name` (nullable, joined in).

`fps` lets the frontend map video time → frame number.
`width` / `height` are the video's native resolution; the overlay uses them to scale bbox coords.
`state` is one of `validating|invalid|queued|detecting|tracking|pose|corners|scoreboard|segmenting|analyzing|completed|failed|labeling_in_progress|labeling_complete` — see `frontend/src/types/Fight.ts` for the full state machine and helper predicates (`isFightViewable`, `isLabelingReady`, `isInvalid`).
`labeled_at` is the durable "ground truth finalised" marker — distinct from `state`, which resets when a labelled fight is re-run through the AI pipeline to become an evaluation fixture.

### `FighterResponse` / `FighterCreate`
`FighterResponse`: `id`, `first_name`, `last_name`, `nickname` (nullable), `created_at`.
`FighterCreate`: `first_name`, `last_name`, `nickname` (optional).

### `FighterFrameResponse`
`fight_id`, `frame` (1-based), `corner` (0=red, 1=blue — formerly `fighter_id`), `x1`, `y1`, `x2`, `y2`, `confidence`, `keypoints`

### `RoundResponse`
`id`, `fight_id`, `round_number`, `start_frame` (1-based), `end_frame` (1-based)

### `FightEventResponse` (pipeline predictions — read-only)
`id`, `frame` (1-based), `description`, `fight_id`, `fighter_id` (nullable, FK to `fighters`), `action` (nullable), `success` (nullable bool), `state` (nullable — STRIKING/CLINCH/GROUND on a state-change row)

### `LabelEventResponse` / `LabelEventCreate` (hand labels — Annotate's write path)
`id`, `frame`, `description`, `fight_id`, `corner` (nullable int, 0=red/1=blue — null for state marks), `action` (nullable), `target` (nullable — head/body/leg), `success` (nullable bool — null unless it's a knockdown), `labeler` (nullable), `created_at`

### `LabelSpanResponse` / `LabelSpanCreate` / `LabelSpanUpdate`
`id`, `fight_id`, `kind` (`round`|`corner_swap`|`excluded`), `start_frame`, `end_frame` (nullable — null means a start/end toggle is still open), `value` (nullable — round number, or exclusion reason), `created_at`

## Frame-numbering contract
All `frame`, `start_frame`, `end_frame` values are **1-based** (first frame of the video = 1), matching the AI pipeline writer. The frontend converts `currentTime` via `Math.floor(currentTime * fps) + 1`.

## Predictions vs. labels — never mix them
`fight_events` is pipeline output: `process_fight()` `DELETE`s and rewrites the whole table for a fight on every run, so anything written there is destroyed by the next pipeline run. `label_events`/`label_spans` are hand labels: written only by the Annotate frontend via `label_event_service.py`/`label_span_service.py`, never touched by the pipeline. This split (rather than a `source` column on one table) exists specifically so a query can't accidentally blend model output into training data by forgetting a filter — see plan `0c(5)`.

## Upload / validation / pipeline pid handoff
`POST /fights/upload` creates the fight row at `state='validating'` and spawns `pipeline_runner.run_validation_async()`, which runs `eval.cli video --fight-id <id>` in the `ai/` venv. That process full-decodes the video, writes `reported_frames`/`decoded_frames`, and either sets `state='invalid'` (truncated file, pipeline never runs) or clears `pid`, spawns `main.py` itself, and writes the new pid — all via `ai/database.py`'s `set_fight_state`/`set_video_check`/`set_fight_pid`, which is why every transition reaches the SSE stream with no backend involvement. `pipeline_runner._AI_ENTRYPOINTS` lists every command-line marker (`main.py`, `eval.cli`) a recorded pid is allowed to belong to — `DELETE /fights/{id}` only signals a pid that's still one of these, so a recycled OS pid can never be killed by mistake. Any new AI-venv job spawned from `pipeline_runner.py` must add its marker there.

## Environment
- `DATABASE_URL` env var required (PostgreSQL connection string)
- `VIDEO_BASE_DIR` — resolves relative `video_path`s and is where `fight_videos/` is created on upload
- `AI_DIR` / `AI_PYTHON` (optional) — override the `ai/` venv location `pipeline_runner.py` spawns into; default to `../ai` and `../.venv/bin/python`
- `KEEP_VIDEO_ON_DELETE` (dev only) — skip deleting the video file on `DELETE /fights/{id}`
- Run with `uvicorn app.main:app --reload` from the `backend/` directory
