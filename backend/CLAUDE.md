# backend/ — FastAPI service

Serves fights, rounds, fighter frames, events and eval runs from PostgreSQL, and spawns and tracks the AI pipeline as a subprocess in the `ai/` venv. Routes live in `app/api/routes/`, SQLAlchemy models and Pydantic schemas in `app/models/`, and logic in `app/services/`.

Run it from `backend/` with `uvicorn app.main:app --reload`. It uses `backend/.venv` (see `backend/.envrc`), not the root `.venv`, which belongs to the pipeline. Install `requirements.txt` into `backend/.venv`, or the auto-reload dies on an `ImportError` and every request hangs.

## Env
- `DATABASE_URL` is required.
- `VIDEO_BASE_DIR` resolves relative `video_path`s, and uploads create `fight_videos/` inside it.
- `AI_DIR` and `AI_PYTHON` override the ai venv that `pipeline_runner.py` spawns into. They default to `../ai` and `../.venv/bin/python`.
- `KEEP_VIDEO_ON_DELETE=1` (dev only) makes `DELETE /fights/{id}` keep the video file. Set it when you test deletes by hand.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `SESSION_SECRET` are required; startup fails without them.
- `PUBLIC_BASE_URL` (required) is the origin the browser sees: `http://localhost:5173` in dev. The OAuth redirect URI (`<PUBLIC_BASE_URL>/api/auth/callback`, which must be registered in Google Cloud) and the cookie's Secure flag both derive from it, because the Vite proxy rewrites `Host`.
- `ADMIN_EMAILS` (comma-separated) makes those addresses admin **when their row is created** on first sign-in. It is not re-applied later.
- `FRONTEND_DIST` (prod only) serves the built SPA from this origin, with an `index.html` fallback for client routes.

## Auth
Route paths elsewhere in this file omit the `/api` prefix.
- **`app/main.py` mounts every router under `/api` with `Depends(current_user)`**, except `/api/auth/*`. `tests/test_auth.py` fails if a route escapes it.
- **Every write route declares its minimum role** with `require_role("labeller")` or `require_role("admin")` in its decorator. Reads need only a session. Add the new route to the role matrix in `tests/test_auth.py`.
- **The cookie holds only the user id.** `current_user` re-reads the `users` row on every request, so a role change or disable applies immediately.
- **Users are disabled (`is_active=false`), never deleted.** Auto-join would bring a deleted user straight back as a viewer. `PATCH /users/{id}` refuses self-edits, which guarantees an admin always remains.
- **A role-gated route that accepts a large body must not declare `File()`/`Form()` params.** FastAPI parses the body before it runs dependencies, so a viewer could stream a whole video to disk before the 403. `upload_fight` reads `request.form()` itself.

## Event routes: scoping is the safety guarantee
`services/event_service.py` implements these. See the root CLAUDE.md for the `source`/`kind` model.
- `GET /fights/{id}/events/` returns every row unless filtered, so callers pass `source`. The first `source=label` fetch for a fight also seeds `kind='round'` labels from `rounds`.
- `POST …/events/` always writes `source='label'` and stamps `labeler` with the signed-in user's email. `FightEventCreate` has neither field, so a client can't spoof a prediction or another labeller.
- `PUT …/events/{eid}` edits `frame`, `end_frame` or `value` on **label spans only**. It returns 404 for predictions and for `kind='point'`: points are create and delete only.
- `PUT …/events/{eid}/verify` sets `is_verified` on **label points only**, the opposite scope. It returns 409 when setting true or false on a fight whose purpose isn't `training_data`. Clearing to null is always allowed.
- `PUT …/events/{eid}/reclassify` (Training Data QA) rewrites `action`, `target` and `success` on **label points only**. It deliberately leaves `corner` and `is_verified` alone. It has no purpose check: the backend stores whatever columns the frontend's `reclassifyPayload()` computes.
- `DELETE …/events/{eid}` works on label rows only and returns 404 for anything else.
- `GET /fighters/{id}/events/` needs no source filter, because a CHECK keeps `fighter_id` prediction-only.

## Labelling lifecycle and purpose
- **`POST /fights/{id}/finish-labeling`** moves `labeling_in_progress → labeling_complete` and stamps `labeled_at`. It returns 409 until every detected round has a confirmed `round` label (`rounds_fully_annotated`).
- **`POST /fights/{id}/reopen-labeling`** moves `labeling_complete → labeling_in_progress`.
  - It **leaves `labeled_at` set**. Eval keys on it, so clearing it would drop a reference fixture off the Accuracy page mid-edit.
  - It returns 409 from any other state, so `ai_labeled` fights (which end at `completed`) can never be reopened.
- **`purpose`** is set only by `POST /fights/upload` and validated against `FIGHT_PURPOSES`. Only `ai_labeled` runs the full pipeline; the labelling purposes get `skip_events`. No API changes it afterwards (use a manual `UPDATE`), and the pipeline's upsert must never add it to its `SET` list.
- **Fighter names:** no route reassigns `red_fighter_id` or `blue_fighter_id` after upload. A backwards pair is cosmetic, since training reads `corner`, not names. Fix it with a direct DB update.

## Upload, validation and pids
- **Upload flow:**
  1. `POST /fights/upload` creates the row at `validating` and calls `pipeline_runner.run_validation_async()`.
  2. That runs `eval.cli video --fight-id` in the ai venv.
  3. The validator either marks the fight `invalid` or spawns `main.py` and records its pid, all through `ai/database.py`. The backend never relays state.
  4. `utils/fight_state_listener.py` fans `pg_notify('fight_state')` out to the `/fights/stream` SSE.
- **`DELETE /fights/{id}`** kills the running pipeline or validator, unlinks the video, and deletes the row (child rows cascade).
  - It only signals a pid whose command line matches `pipeline_runner._AI_ENTRYPOINTS`, so a recycled OS pid is never killed. **Any new AI-venv job spawned from `pipeline_runner.py` must add its marker there.**
  - `app/main.py` reconciles recorded pids at startup.

## Fighter frames
`GET /fights/{id}/frames/` without a range returns every row, which is tens of MB for a full fight. Pass `start_frame`/`end_frame` (1-based, inclusive) when you only need a window. `ix_fighter_frames_fight_frame` keeps that query index-only.
