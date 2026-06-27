# Fight AI — Backend

## Workflow
- Always apply changes directly to the local working directory
- Never open PRs or suggest creating pull requests

## What it does
FastAPI service that exposes fight data (fights, rounds, fighter frames, events) stored by the AI pipeline in PostgreSQL.

## Project Structure
```
backend/
├── app/
│   ├── main.py               # FastAPI app + router registration
│   ├── api/
│   │   └── routes/
│   │       ├── events.py     # GET /events/  (legacy, all events)
│   │       ├── fights.py     # /fights/ endpoints (see below) + PATCH corners
│   │       ├── fighters.py   # /fighters/ endpoints (CRUD-lite + per-fighter events)
│   │       └── tracking.py   # /tracking/ endpoints
│   ├── models/
│   │   ├── fight.py          # Fight model (+ red/blue_fighter_id) + FightResponse
│   │   ├── fight_event.py    # FightEvent model (+ fighter_id/action/success) + FightEventResponse
│   │   ├── fighter.py        # Fighter model + FighterResponse + FighterCreate
│   │   ├── fighter_frame.py  # FighterFrame model (corner) + FighterFrameResponse
│   │   └── round.py          # Round model + RoundResponse
│   ├── services/
│   │   ├── event_service.py        # get_fight_events(), get_events_by_fight(filters)
│   │   ├── fight_service.py        # get_all_fights(), get_processed_fights(), delete_fight()
│   │   ├── fighter_service.py      # get_fighters(search), create_fighter(), get_events_by_fighter(), set_fight_corners()
│   │   ├── fighter_frame_service.py # get_fighter_frames(fight_id)
│   │   └── round_service.py        # get_rounds(fight_id)
│   └── utils/
│       └── db.py             # SQLAlchemy SessionLocal + run_db_query helper
```

## API Routes

### `/fights/` router
| Method | Path | Description |
|--------|------|-------------|
| GET | `/fights/` | List all fights (`FightResponse[]`) |
| GET | `/fights/{fight_id}/rounds/` | Rounds for a fight (`RoundResponse[]`) |
| GET | `/fights/{fight_id}/frames/` | Fighter bounding boxes per frame (`FighterFrameResponse[]`) |
| GET | `/fights/{fight_id}/events/` | Fight events scoped to a fight (`FightEventResponse[]`); optional `fighter_id` / `action` / `success` query filters |
| PATCH | `/fights/{fight_id}/corners/` | Assign `red_fighter_id` / `blue_fighter_id` to a fight (validates fighters exist) |
| DELETE | `/fights/{fight_id}/` | Delete fight + all child rows via FK cascade (404 if not found) |

### `/fighters/` router
| Method | Path | Description |
|--------|------|-------------|
| GET | `/fighters/` | List/search fighters (`FighterResponse[]`); optional `search` (ILIKE on names/nickname) |
| POST | `/fighters/` | Create a fighter (`FighterCreate` → `FighterResponse`) |
| GET | `/fighters/{id}/` | Single fighter (404 if not found) |
| GET | `/fighters/{id}/events/` | Cross-fight events for a fighter (`FightEventResponse[]`); optional `action` (prefix) / `success` filters — serves "all jabs fighter X landed" |

### Legacy
| Method | Path | Description |
|--------|------|-------------|
| GET | `/events/` | All fight events regardless of fight (backwards compatibility) |

## Models / Schemas

### `FightResponse`
`id`, `video_path`, `fps` (int), `width`, `height`, `created_at`, `processed`, `processed_at`, `red_fighter_id` (nullable), `blue_fighter_id` (nullable)

`fps` lets the frontend map video time → frame number.
`width` / `height` are the video's native resolution; the overlay uses them to scale bbox coords.
`red_fighter_id` / `blue_fighter_id` are FKs to `fighters` (corner assignment).

### `FighterResponse` / `FighterCreate`
`FighterResponse`: `id`, `first_name`, `last_name`, `nickname` (nullable), `created_at`.
`FighterCreate`: `first_name`, `last_name`, `nickname` (optional).

### `FighterFrameResponse`
`fight_id`, `frame` (1-based), `corner` (0=red, 1=blue — formerly `fighter_id`), `x1`, `y1`, `x2`, `y2`, `confidence`, `keypoints`

### `RoundResponse`
`id`, `fight_id`, `round_number`, `start_frame` (1-based), `end_frame` (1-based)

### `FightEventResponse`
`id`, `frame` (1-based), `description`, `fight_id`, `fighter_id` (nullable, FK to `fighters`), `action` (nullable), `success` (nullable bool)

## Frame-numbering contract
All `frame`, `start_frame`, `end_frame` values are **1-based** (first frame of the video = 1), matching the AI pipeline writer. The frontend converts `currentTime` via `Math.floor(currentTime * fps) + 1`.

## Environment
- `DATABASE_URL` env var required (PostgreSQL connection string)
- Run with `uvicorn app.main:app --reload` from the `backend/` directory
