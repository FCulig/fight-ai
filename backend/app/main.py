import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.tracking import router as tracking_router
from app.api.routes.fights import router as fights_router
from app.api.routes.fighters import router as fighters_router
from app.api.routes.eval_runs import router as eval_runs_router
from app.api.routes.users import router as users_router
from app.services import fight_service
from app.services.pipeline_runner import is_pipeline_process_alive
from app.utils import fight_state_listener
from app.utils.auth import SESSION_COOKIE, SESSION_MAX_AGE, current_user, get_config


def _reconcile_pipeline_pids() -> None:
    """Fights that were mid-pipeline when the backend last stopped keep their
    PID in the DB. On restart, any of those PIDs that are no longer running
    (process died with the previous backend, or independently) are marked
    failed instead of being left stuck showing a stale in-progress state
    forever. PIDs still alive are left alone — the pipeline is still running
    and the DB-recorded PID is all a later delete needs to find and kill it.
    """
    for fight_id, pid in fight_service.get_active_pipeline_pids():
        if not is_pipeline_process_alive(pid):
            fight_service.fail_stale_pipeline(fight_id, pid)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _reconcile_pipeline_pids()
    fight_state_listener.start(asyncio.get_running_loop())
    yield
    fight_state_listener.stop()


app = FastAPI(title="Fight AI", lifespan=lifespan)

_auth_config = get_config()
app.add_middleware(
    SessionMiddleware,
    secret_key=_auth_config.session_secret,
    session_cookie=SESSION_COOKIE,
    max_age=SESSION_MAX_AGE,
    same_site="lax",  # no cookie on cross-site POST/PUT/PATCH/DELETE, which is the CSRF guard
    https_only=_auth_config.https_only,
)

# Everything under /api needs a session except /api/auth/*. Routers add their
# own require_role() on writes; tests/test_auth.py fails if a route skips auth.
api = APIRouter(prefix="/api")
signed_in = [Depends(current_user)]
api.include_router(auth_router, prefix="/auth")
api.include_router(tracking_router, prefix="/tracking", dependencies=signed_in)
api.include_router(fights_router, prefix="/fights", dependencies=signed_in)
api.include_router(fighters_router, prefix="/fighters", dependencies=signed_in)
api.include_router(eval_runs_router, prefix="/eval-runs", dependencies=signed_in)
api.include_router(users_router, prefix="/users", dependencies=signed_in)
app.include_router(api)


# Production serves the built SPA from this same origin, which keeps the
# session cookie first-party. In dev the Vite server does this instead.
_FRONTEND_DIST = os.getenv("FRONTEND_DIST")
if _FRONTEND_DIST:
    _dist = Path(_FRONTEND_DIST).resolve()
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        file = (_dist / path).resolve()
        if path and file.is_file() and file.is_relative_to(_dist):
            return FileResponse(file)
        return FileResponse(_dist / "index.html")