# Fight AI

MMA fight-video analysis. `ai/` is the Python pipeline (video → PostgreSQL), `backend/` is the FastAPI service over the same DB (it also spawns the pipeline), and `frontend/` is the React app for review, labelling and QA. `db/alembic/` holds the schema migrations, `landing/` the landing page, and `plan/` the staged design docs.

`ai/`, `backend/` and `frontend/` each have their own CLAUDE.md. Subsystem detail lives in `.claude/rules/` and loads only when you touch matching files.

## Workflow
- Apply changes directly to the local working directory.
- Never open PRs or suggest creating pull requests.
- When you learn something worth keeping, put it in the narrowest file that covers it:
  - a `.claude/skills/` skill for a multi-step procedure;
  - a `.claude/rules/` file for an invariant of one subsystem;
  - a folder's CLAUDE.md for that folder;
  - this file only for contracts that span layers.

  Write the rule and a one-line reason. Leave out history ("it used to…") and anything Claude can learn by reading the code (file trees, field lists, signatures).
## Cross-layer contracts
Every layer depends on these. Breaking one in one place breaks the others.

- **Auth is a same-origin session cookie.** Every backend route lives under `/api` and needs a session, except `/api/auth/*` (Google sign-in). The SPA and the API must share one origin: the Vite proxy in dev, and FastAPI serving `FRONTEND_DIST` in prod. `<video src>` and `EventSource` can't send an `Authorization` header, so a token scheme or a cross-origin frontend breaks video and live updates.
- **Roles (`viewer < labeller < admin`, on `users.role`) are enforced only in the backend.** Frontend gating is cosmetic. Anyone who signs in with Google joins as a viewer.
- **Frames are 1-based**: the first frame is 1. `fps` is an integer on the `fights` row, set once at registration, and it is the only fps any layer may use. To convert time to a frame, use `Math.floor(t * fps) + 1`. Never hardcode fps or re-read it from the video.
- **`fight_events` holds both predictions and hand labels**, told apart by two columns:
  - `source`: `prediction` is written only by the pipeline. `label` is written only through the backend event routes (from Annotate).
  - `kind`: one of `point`, `round`, `corner_swap`, `excluded`. Range kinds use `frame` as the start plus `end_frame`, where `end_frame IS NULL` means the span is still open. `end_frame` is always NULL on a `point`.
  - **Every new query needs an explicit `source` and/or `kind` filter**, or it mixes the two. The pipeline's delete-and-rewrite only touches `source='prediction'`, and the backend's update/delete only touches `source='label'`. DB CHECKs also enforce that `corner` is set only on labels and `fighter_id` only on predictions.
- **`corner` (0=red, 1=blue) is a track slot, not a person.** This applies to both `fighter_frames.corner` and label `fight_events.corner`. The labeller clicks the overlay box, so a tracker swap gets copied into the label. `fighter_id` is the opposite: a resolved identity (FK) that only predictions carry. `corner_swap` spans are applied **for display only**. Never rewrite stored corners from them, and training doesn't apply them.
- **`description` is NULL except when `action='fight_end'`**, which a Pydantic validator and a DB CHECK enforce. All other display text is rebuilt on every render by `frontend/src/utils/describeEvent.ts` from the structured columns, so a `corner_swap` marked later still fixes strikes that were already logged. Don't bring back stored descriptions or backfills.
- **`fights.purpose` is written once, at upload.** Its values are `training_data` (labels feed training), `reference` (held-out ground truth) and `ai_labeled` (full pipeline). A fight's pipeline never runs again. To measure accuracy, upload the same video again as a new `ai_labeled` fight and compare the two fight IDs (`eval.cli score-pair`). Never re-process a labelled fight. `training_data` and `reference` must stay disjoint: reference labels are never QA'd, trained on or shown in Training Data QA.
- **`is_verified`** is Training Data QA's verdict on a label point event: true, false, or NULL (not reviewed). Only `PUT …/events/{id}/verify` writes it, and only for `training_data` fights. The strike model trains only on `is_verified IS TRUE`.
- **`fights.state`** has its values in `ai/models/FightProcessingState.py`, mirrored in `frontend/src/types/Fight.ts`. AI-side processes must change state and pid only through `ai/database.py` (`set_fight_state`, `set_video_check`, `set_fight_pid`), because that is what drives the `pg_notify` → `/fights/stream` SSE. `labeled_at` marks ground truth as finalised: finish-labeling sets it, and reopening keeps it.

## Schema
The source of truth is `db/alembic/versions/` plus `backend/app/models/`. The pipeline writes raw SQL (`ai/fight_processing/`), so check all three when you change a column.
