# Plan: Write All Fight Data to DB + Frontend Overlays

## Context

The AI pipeline currently writes fight events (text descriptions) to the `fight_events` PostgreSQL table, but all spatial per-frame data — fighter bounding boxes and round boundaries — is only written to intermediate JSON files. There is no concept of a "fight" record, making multi-fight storage impossible. The pipeline is also a one-shot CLI tool rather than a batch processor, and it relies on writing files between steps as its primary data transport.

The goal is to:
1. Add a `fights` root table with a `processed` flag, linked to all child tables
2. Make batch mode the default when no video argument is given — scan `fight_videos/`, register new files, process each unprocessed fight, mark it done
3. **The data pipeline writes nothing to disk.** Every step passes its output to the next step in-memory, and all persistent data lives in the DB. No `detection_results.json`, `output_reidentification.json`, `pose_results.json`, `samples.json`, or `manifest.json` is written. The only data store is PostgreSQL.
4. Persist fighter bounding boxes and round boundaries to the DB per fight
5. Remove all `save_to_db` / `--no-db` infrastructure — DB writes are always performed
6. Expose the new data through backend endpoints
7. Render toggleable fighter-rectangle overlays on the frontend video player

> **Scope of "nothing to disk":** this covers the *data* pipeline only. The opt-in diagnostic outputs (`--verify-pose` / `--verify-scoreboard` debug videos and scoreboard calibration debug images) are not part of the data flow and remain as explicitly-requested artifacts. No intermediate data file is ever written.

---

## Layer Dependencies

```
Layer 1 (DB Migration)
    ↓ requires schema to exist
Layer 2 (AI Pipeline)   Layer 3 (Backend)
    ↓                       ↓
    both require Layer 1 tables and indexes before they can run
Layer 4 (Frontend)
    ↓ requires Layer 3 endpoints to be live
Layer 5 (Documentation)
    ↓ can be written in parallel with any layer but should be finalised last
```

Layers 2 and 3 share no runtime dependency on each other and can be implemented in parallel once Layer 1 is merged. Layer 4 depends on Layer 3 endpoints being reachable (start the backend locally to unblock frontend development).

---

## Layer 1 — DB Migration

**New file:** `db/alembic/versions/<rev>_add_fights_fighter_frames_rounds.py`

Set `down_revision = "92f72188aec1"` (the current head — the `create_fight_events_table` revision).

### New table: `fights`
```sql
CREATE TABLE fights (
    id           SERIAL PRIMARY KEY,
    video_path   VARCHAR(500) NOT NULL UNIQUE,
    fps          INTEGER NOT NULL,
    width        INTEGER NOT NULL,
    height       INTEGER NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    processed    BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at TIMESTAMP
);
```
- `video_path` is UNIQUE so re-scanning a folder never creates duplicate rows.
- `fps`, `width`, `height` are all extracted from the video file itself at registration time (see `run_batch` / single-file upsert below). `fps` is stored as an integer — `cv2.CAP_PROP_FPS` returns a float (e.g. 29.97) which is rounded to the nearest integer (`round(cap.get(cv2.CAP_PROP_FPS))`) at registration time. This eliminates floating-point drift in `Math.floor(currentTime * fps) + 1` over thousands of frames. `fps` is the single source of truth for every frame↔seconds conversion downstream — no step re-reads fps from disk. `width`/`height` (native resolution) are served to the frontend so the overlay can scale bbox coords correctly instead of assuming a hardcoded 1920×1080.
- `processed_at` is `NULL` until processing completes; it is set to `NOW()` in the same `UPDATE` that flips `processed = true`. `processed_at - created_at` gives a rough processing-duration metric for analytics.

### New table: `rounds`
```sql
CREATE TABLE rounds (
    id           SERIAL PRIMARY KEY,
    fight_id     INTEGER NOT NULL REFERENCES fights(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    start_frame  INTEGER NOT NULL,
    end_frame    INTEGER NOT NULL,
    UNIQUE (fight_id, round_number)
);
```
The `UNIQUE (fight_id, round_number)` constraint prevents duplicate round rows from a segmentation bug; without it a re-run that double-inserts rounds before the delete step could produce silent duplicates.

### New table: `fighter_frames`
```sql
CREATE TABLE fighter_frames (
    id         SERIAL PRIMARY KEY,
    fight_id   INTEGER NOT NULL REFERENCES fights(id) ON DELETE CASCADE,
    frame      INTEGER NOT NULL,
    fighter_id INTEGER NOT NULL,   -- 0 = red, 1 = blue
    x1 FLOAT NOT NULL, y1 FLOAT NOT NULL,
    x2 FLOAT NOT NULL, y2 FLOAT NOT NULL,
    confidence FLOAT
);
```

### Alter existing table: `fight_events`
```sql
ALTER TABLE fight_events ADD COLUMN fight_id INTEGER REFERENCES fights(id) ON DELETE CASCADE;
```
Nullable to avoid breaking existing rows; all new rows carry it. **Follow-on:** once all legacy rows have been backfilled or deleted, a subsequent migration should add `ALTER TABLE fight_events ALTER COLUMN fight_id SET NOT NULL` so the application cannot accidentally insert new events without a fight link. Track this as a separate migration step.

### Indexes
All child tables are queried and deleted by `fight_id`, and `fighter_frames` grows to ~`frames × 2` rows per fight, so the per-fight lookups must not table-scan:
```sql
CREATE INDEX ix_fighter_frames_fight_frame ON fighter_frames (fight_id, frame);
CREATE INDEX ix_rounds_fight_id            ON rounds (fight_id);
CREATE INDEX ix_fight_events_fight_id      ON fight_events (fight_id);
```
The composite `(fight_id, frame)` index serves both the `GET /fights/{id}/frames/` read and the delete-before-reinsert step in `process_fight`.

### Frame-numbering contract (cross-cutting)

The `frame` value in `fighter_frames`, the `start_frame`/`end_frame` in `rounds`, the `frame` in `fight_events`, and the frontend's per-frame overlay lookup must all use **one** numbering scheme, or overlays will lag by a frame and round boundaries will be off.

**Canonical definition:** frames are **1-based**, matching the existing writer in `process_fight` (`frame_number = index + 1`, [fight_processing.py:74](ai/fight_processing/fight_processing.py)). The Nth frame of the video is frame `N` (the first frame is `1`).

- **Writer** (`process_fight`): keep `frame_number = index + 1` for `fighter_frames`, `fight_events`, and when matching `rounds` boundaries. The `rounds` start/end frames produced by segmentation already use this scheme — do not shift them.
- **Frontend lookup** (`FighterOverlay`): convert the video element's `currentTime` to a 1-based frame with `currentFrame = Math.floor(currentTime * fps) + 1`, using the `fps` returned in `FightResponse`. This is the value passed to `frameMap.get(currentFrame)`.
- Keep this contract documented in `ai/CLAUDE.md` and `frontend/CLAUDE.md` so it is not silently broken later.

---

## Layer 2 — AI Pipeline

### `ai/main.py`

- `video_input` becomes an optional positional argument (`nargs="?", default=None`).
- When omitted → dispatch to `run_batch()`.
- When provided → dispatch to `run_pipeline(video_file, ...)`.
- Remove `--no-db` flag entirely.
- All other flags (`--detection-file`, `--reid-file`, `--pose-results`, `--scoreboard-*`, `--manifest`, `--rounds`, `--verify-*`, `--debug-level`) remain unchanged and only apply to single-file mode.

```
python main.py              # default: batch mode, scans fight_videos/
python main.py fight.mp4    # single-file mode
```

### `ai/pipeline.py` — fully in-memory data flow (no disk writes)

The pipeline currently writes large JSON files between steps and passes file paths downstream. After this change **no step writes any data file**: each step returns its output dict and the next step consumes it directly. PostgreSQL is the only data store.

This requires changing the step modules themselves, not just the orchestrator — today they write to fixed paths and return `None`/a path:

| Step / function | Currently | After |
|------|-----------|-------|
| YOLO detection — `process_video()` | writes `detection_results.json`, returns path | returns detection dict; writes nothing |
| ReID — `track_fighters()` | reads JSON, writes `output_reidentification.json`, returns `None` | accepts detection dict, returns reid dict; writes nothing |
| Pose tracking — `track_poses()` | reads JSON, writes `pose_results.json`, returns `None` | accepts reid dict, returns pose dict; writes nothing |
| Scoreboard OCR — `extract_scoreboard_samples()` | returns samples and writes `samples.json` | returns samples dict only; writes nothing |
| Segmentation — `segment_fights()` | takes a JSON file path, re-reads fps via `_read_fps` | accepts detection dict + `fps` directly |
| Fight processing — `process_fight()` | reads pose JSON file | accepts pose dict + `fight_id`, writes to DB |

Because the on-disk fps lookups disappear (`_read_fps`, and reading `fps` back off `pose_results.json` in the verify-pose branch), `fps` is read once from the `fights` row and threaded in-memory to `segment_fights`, `process_fight`, and `verify_pose_tracking`.

**No manifest file.** `build_manifest`'s disk write (`runs/manifest.json`) is removed; the run summary (`rounds`, `quality`, timings) is returned from `run_pipeline()` in memory only.

**Developer skip-flags** (`--detection-file`, `--reid-file`, `--pose-results`, `--scoreboard-samples`, `--manifest`) remain **read-only** overrides: they load a developer-supplied file into the in-memory dict at the appropriate step. The pipeline never *produces* these files — they are purely a manual dev convenience for skipping expensive recompute. `--rounds` (inline string, no file) is unaffected.

**`run_pipeline()` changes:**
- Remove `no_db: bool` parameter.
- Add `fight_id: Optional[int] = None`:
  - When `None` (**single-file mode**), upsert the fight record, extracting `fps` + `width` + `height` from the video first. The upsert **resets the fight to "needs processing"** on conflict, because refreshing the metadata means the source video changed and any existing child rows are now stale:
    ```sql
    INSERT INTO fights (video_path, fps, width, height)
    VALUES (:path, :fps, :w, :h)
    ON CONFLICT (video_path) DO UPDATE
    SET fps = EXCLUDED.fps,
        width = EXCLUDED.width,
        height = EXCLUDED.height,
        processed = false,
        processed_at = NULL
    RETURNING id;
    ```
    This preserves the invariant that `processed = true` always means the stored `fps`/`width`/`height` and all child rows came from the *same* run.
  - When provided (**batch mode**), the record already exists, so `SELECT fps, width, height FROM fights WHERE id = :fight_id`.
- Add `fps: int` to the in-memory flow (resolved as above) and pass it to every step that needs it.
- `run_fight` condition: `run_fight = verify_pose is None and not verify_scoreboard` (drop the old `not no_db` guard).
- Pass `fight_id`, `fps`, and the in-memory pose dict to `process_fight()`.
- **Single-file mode owns its own completion update:** when `run_fight` ran and `fight_id` was created here (i.e. caller passed `None`), `run_pipeline` itself issues `UPDATE fights SET processed = true, processed_at = NOW() WHERE id = :id` after `process_fight` succeeds. There is no `run_batch` wrapper in this path, so without this a single-file run would always leave the fight `processed = false`. In batch mode (`fight_id` supplied), `run_pipeline` does **not** touch the flag — `run_batch` step 5 owns it so a mid-fight crash leaves the row `processed = false`.
- Remove all `build_manifest` disk-write wiring (and the `no_db` entry).
- `_print_plan` fight-process label: `"SKIP — debug flags present" if not run_fight else "RUN"`.

**New `run_batch(fight_videos_dir: str = "fight_videos")` function:**
1. If `fight_videos_dir` does not exist, create it, print a hint, and return early.
2. Scan for `.mp4` / `.mkv` / `.mov` files. For each, **extract `fps`, `width`, and `height` from the video file** (e.g. `cap = cv2.VideoCapture(path)`; `fps = round(cap.get(cv2.CAP_PROP_FPS))`, `CAP_PROP_FRAME_WIDTH`, `CAP_PROP_FRAME_HEIGHT`) and `INSERT INTO fights (video_path, fps, width, height) VALUES (:path, :fps, :w, :h) ON CONFLICT (video_path) DO NOTHING`. This is where fps + resolution are captured for the lifetime of the fight. Batch uses `DO NOTHING` (not `DO UPDATE`), so it never disturbs an existing row's flag or metadata. **Accepted limitation:** a file replaced at the same path is *not* re-detected by batch — the row already exists and stays `processed = true`. Re-running such a video requires single-file mode (whose upsert resets the flag, see below).
3. `SELECT id, video_path, fps, width, height FROM fights WHERE processed = false ORDER BY id`.
4. For each row: call `run_pipeline(video_file=row.video_path, fight_id=row.id, ...)` (the pipeline reads `fps`/`width`/`height` from the row).
5. On success: `UPDATE fights SET processed = true, processed_at = NOW() WHERE id = :id` (both columns set in the same statement so `processed_at` always coincides with the flag flip).
6. On exception: log the traceback (in-memory `DebugContext.log`), continue to next fight (row stays `processed = false`, `processed_at` stays `NULL`).

### `ai/fight_processing/fight_processing.py`

- Remove `save_to_db: bool = True` parameter entirely.
- Add `fight_id: int` as a required parameter.
- First parameter changes from `detection_results_file: str` (file path) to `pose_data: dict` (in-memory dict passed by `pipeline.py`).
- Remove the `open(detection_results_file)` file read.
- Remove all `if db is not None:` guards; always create `db = SessionLocal()`.
- Update `_insert_event()` to include `fight_id`.

**Single-transaction, idempotent write (per point 3):** the entire function is one DB transaction so a crash can never leave a half-populated fight, and reprocessing is safe:
1. **Delete first** — at the top, `DELETE FROM fight_events / fighter_frames / rounds WHERE fight_id = :fight_id`. This makes re-running on an already-processed video (single-file mode) or retrying a crashed batch fight idempotent instead of duplicating rows.
2. Bulk-insert the `rounds` list into the `rounds` table.
3. Inside the per-frame loop, collect each detection's bbox (for `class_id` 0 or 1) into a batch list; every 1 000 rows call `_flush_frame_batch(db, batch)` which issues the insert and then `db.flush()` — **not `db.commit()`** — to release memory without ending the transaction.
4. Flush remaining rows after the loop.
5. **One `db.commit()` at the very end** (followed by `db.close()`). Either every row for the fight lands or none does.

- Confirm the pose dict carries per-detection bbox coords (`x1,y1,x2,y2`) and `confidence`; the loop currently only reads `keypoints`/`class_id`, so these fields must be present in the pose output to populate `fighter_frames`.
- The `processed` flag update is the caller's responsibility (`pipeline.py`), and only runs after this transaction commits successfully.

---

## Layer 3 — Backend

### Models — `backend/app/models/`

**New file:** `fight.py` — `Fight` SQLAlchemy model + `FightResponse` Pydantic schema (`id`, `video_path`, `fps`, `width`, `height`, `created_at`, `processed`, `processed_at`). `fps` lets the frontend map video time → frame; `width`/`height` let the overlay scale bbox coords to the displayed video size.  
**New file:** `fighter_frame.py` — `FighterFrame` model + `FighterFrameResponse` (`fight_id`, `frame`, `fighter_id`, `x1`, `y1`, `x2`, `y2`, `confidence`).  
**New file:** `round.py` — `Round` model + `RoundResponse` (`id`, `fight_id`, `round_number`, `start_frame`, `end_frame`).  
**Update:** `fight_event.py` — add `fight_id: int | None` to `FightEventResponse`.

### Services — `backend/app/services/`

**New:** `fight_service.py` — `get_all_fights(db)`, `get_processed_fights(db)`, `delete_fight(db, fight_id)`.  
**New:** `fighter_frame_service.py` — `get_fighter_frames(db, fight_id)`.  
**New:** `round_service.py` — `get_rounds(db, fight_id)`.  
**Update:** `event_service.py` — add `get_fight_events(db, fight_id)`.

### Routes — `backend/app/api/routes/`

**New file:** `fights.py`
```
GET    /fights/                            → list[FightResponse]
GET    /fights/{fight_id}/rounds/          → list[RoundResponse]
GET    /fights/{fight_id}/frames/          → list[FighterFrameResponse]
GET    /fights/{fight_id}/events/          → list[FightEventResponse]
DELETE /fights/{fight_id}/                 → 204 No Content
```

`DELETE /fights/{fight_id}/` cascades: it deletes all child rows (`fight_events`, `fighter_frames`, `rounds`) via the FK cascade (add `ON DELETE CASCADE` to each FK in the migration), then deletes the `fights` row itself. Returns 404 if the fight does not exist. This prevents needing raw SQL to remove corrupted or test fights.

Existing `GET /events/` stays for backwards compatibility.

### App registration — `backend/app/main.py`

Add `include_router` for `fights` router.

---

## Layer 4 — Frontend

### Types — `frontend/src/types/`

**New files:** `Fight.ts`, `FighterFrame.ts`, `Round.ts`

### API — `frontend/src/services/api.ts`

Add:
```ts
fetchFights(): Promise<Fight[]>
fetchFighterFrames(fightId: number): Promise<FighterFrame[]>
fetchRounds(fightId: number): Promise<Round[]>
```

### Hooks

**New:** `useFights.ts` — fetches all processed fights, exposes `selectedFightId` state (defaults to latest).  
**New:** `useFighterFrames.ts` — fetches frames for `selectedFightId`, builds `Map<number, FighterFrame[]>` for O(1) per-frame lookup.  
**New:** `useRounds.ts` — fetches rounds for `selectedFightId`.

### Overlay Component — `frontend/src/components/FighterOverlay.tsx`

A `<canvas>` absolutely positioned over the video (`pointer-events: none`). On each `currentFrame` change:
1. Clear canvas
2. If `showBoxes` is false, return
3. Compute `currentFrame = Math.floor(video.currentTime * fps) + 1` (1-based — see the frame-numbering contract in Layer 1) and look up `frameMap.get(currentFrame)`
4. Scale bbox coords from the fight's native resolution (`width`×`height` from `FightResponse`, **not** a hardcoded 1920×1080) to the canvas display size
5. Draw red rect for `fighter_id === 0`, blue for `fighter_id === 1`

### Player.tsx updates

- Consume `useFights`, `useFighterFrames`, `useRounds`
- Replace hardcoded `currentRound` calculation with DB-backed round data
- Add fight selector (shows video filename, defaults to most recently processed fight)
- Add **Overlays** section in the stats card with a **"Fighter Boxes"** checkbox
- Render `<FighterOverlay>` inside the video column

### VideoPlayer.tsx

Wrap the `<video>` in a `position: relative` container so the overlay canvas stacks correctly.

---

## Layer 5 — Documentation

- **`ai/CLAUDE.md`** — update pipeline section to describe the fully in-memory data flow (no intermediate JSON written; DB is the only data store), fps + resolution (`width`/`height`) extracted from the video at registration and stored on the `fights` row, the 1-based frame-numbering contract, batch-as-default entry point, new `fight_id` parameter, `processed`/`processed_at` lifecycle, single-transaction/idempotent `process_fight`, new DB tables + indexes; remove `--no-db` and the "writes `runs/*.json`" descriptions. Note that **PostgreSQL is now a hard runtime dependency** — there is no longer any no-DB path; the pipeline cannot run without a reachable `DATABASE_URL`.
- **`backend/CLAUDE.md`** — create if absent; document project structure, all models/services/routes including fight-scoped endpoints.
- **`frontend/CLAUDE.md`** — create if absent; document project structure, overlay component (incl. the frame-numbering contract and `width`/`height`-based scaling), hooks, fight selector, and API service.

> **Out of scope:** automated tests are deferred for now — verification is the manual checklist below.

---

## Verification

1. **Migration**: `alembic upgrade head` — confirm all four tables and the three indexes exist, and that `fights` has `fps`, `width`, `height`, `processed_at`.
2. **Batch pipeline**: place a `.mp4` in `fight_videos/`, run `python main.py` — confirm fight row inserted with non-null `fps`/`width`/`height` extracted from the video, pipeline runs fully in-memory, **no intermediate JSON files appear in `runs/`**, `processed = true` and `processed_at` set after completion, `rounds` and `fighter_frames` populated.
3. **Re-run**: run `python main.py` again — no duplicate fight row, no reprocessing.
4. **Idempotency**: re-run a single processed video in single-file mode — child rows are deleted-then-reinserted, not duplicated (counts unchanged).
5. **Single-file mode**: `python main.py fight.mp4` — fight record upserted with `fps`/`width`/`height`, data written to DB.
6. **Backend**: `GET /fights/` returns the fight incl. `fps`/`width`/`height`; `GET /fights/1/frames/` and `GET /fights/1/rounds/` return data.
7. **Frontend**: fighter rectangles overlay on video and stay aligned with fighters as playback advances (validates the frame-numbering contract), boxes scale correctly for a non-1080p video (validates `width`/`height` usage), checkbox toggles visibility, round display uses DB data, no regressions.
