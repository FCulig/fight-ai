---
name: add-db-column
description: Checklist for adding or changing a PostgreSQL column end to end — hand-written Alembic migration in db/, backend SQLAlchemy model and Pydantic response, the pipeline's raw SQL in ai/, and frontend types. Use whenever a table in the fight-ai database gains, loses or changes a column.
---

# Add or change a DB column

The schema is written in four places that nothing keeps in sync automatically: the migration, the backend model, the pipeline's raw SQL, and the frontend types.

## 1. Migration (`db/alembic/versions/`)
- **Write it by hand.** `env.py` sets `target_metadata = None`, so autogenerate produces nothing.
- **Name and link it:** `<revision>_<what_it_does>.py`, with `down_revision` set to the current head (`cd db && alembic heads`).
- **Explain why in the module docstring,** as the existing migrations do, and always write `downgrade()`.
- **`fight_events` columns:** decide which `source` may carry the new column. Enforce it structurally with a CHECK when that's cheap, as `corner` and `fighter_id` do (`d7e8f9a0b1c2`), or in the service layer, as `is_verified` does. Record the choice in the docstring.
- **Apply it:** run `cd db && alembic upgrade head`, which reads `DATABASE_URL` from `db/.env`. Right after creating it, before any data exists, test the round trip with `alembic downgrade -1 && alembic upgrade head`.

## 2. Backend (`backend/app/models/<table>.py`)
- Add the SQLAlchemy `Column` and the field on the matching `*Response` schema. Both live in the same file.
- If the column is writable, add or extend the service function and route, scoped by `source`/`kind` for `fight_events` (see `backend/CLAUDE.md`).

## 3. Pipeline (`ai/`)
- Only needed if the pipeline reads or writes the column. The raw SQL lives in `ai/database.py`, `ai/pipeline.py` (the fights upsert) and `ai/fight_processing/fight_processing.py` (bulk inserts).
- **A write-once column must never go into the upsert's `ON CONFLICT … DO UPDATE SET`.** `purpose` is the example.

## 4. Frontend
- Add the field to `frontend/src/types/<Type>.ts`.
- Add request fields in `services/api.ts` if the frontend writes the column.

## 5. Docs
If the column carries a contract that other layers must respect, such as who writes it, what NULL means, or write-once, add one line to the root `CLAUDE.md` contracts.
