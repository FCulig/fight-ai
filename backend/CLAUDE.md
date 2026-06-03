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
│   │       ├── fights.py     # /fights/ endpoints (see below)
│   │       └── tracking.py   # /tracking/ endpoints
│   ├── models/
│   │   ├── fight.py          # Fight SQLAlchemy model + FightResponse Pydantic schema
│   │   ├── fight_event.py    # FightEvent model + FightEventResponse
│   │   ├── fighter_frame.py  # FighterFrame model + FighterFrameResponse
│   │   └── round.py          # Round model + RoundResponse
│   ├── services/
│   │   ├── event_service.py        # get_fight_events(), get_events_by_fight()
│   │   ├── fight_service.py        # get_all_fights(), get_processed_fights(), delete_fight()
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
| GET | `/fights/{fight_id}/events/` | Fight events scoped to a fight (`FightEventResponse[]`) |
| DELETE | `/fights/{fight_id}/` | Delete fight + all child rows via FK cascade (404 if not found) |

### Legacy
| Method | Path | Description |
|--------|------|-------------|
| GET | `/events/` | All fight events regardless of fight (backwards compatibility) |

## Models / Schemas

### `FightResponse`
`id`, `video_path`, `fps` (int), `width`, `height`, `created_at`, `processed`, `processed_at`

`fps` lets the frontend map video time → frame number.
`width` / `height` are the video's native resolution; the overlay uses them to scale bbox coords.

### `FighterFrameResponse`
`fight_id`, `frame` (1-based), `fighter_id` (0=red, 1=blue), `x1`, `y1`, `x2`, `y2`, `confidence`

### `RoundResponse`
`id`, `fight_id`, `round_number`, `start_frame` (1-based), `end_frame` (1-based)

### `FightEventResponse`
`id`, `frame` (1-based), `description`, `fight_id` (nullable — legacy rows have NULL)

## Frame-numbering contract
All `frame`, `start_frame`, `end_frame` values are **1-based** (first frame of the video = 1), matching the AI pipeline writer. The frontend converts `currentTime` via `Math.floor(currentTime * fps) + 1`.

## Environment
- `DATABASE_URL` env var required (PostgreSQL connection string)
- Run with `uvicorn app.main:app --reload` from the `backend/` directory
