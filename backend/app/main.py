import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api.routes.tracking import router as tracking_router
from app.api.routes.events import router as fight_events_router
from app.api.routes.fights import router as fights_router
from app.api.routes.fighters import router as fighters_router
from app.services import fight_service
from app.services.pipeline_runner import is_pipeline_process_alive
from app.utils import fight_state_listener


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

app.include_router(tracking_router, prefix="/tracking")
app.include_router(fight_events_router, prefix="/events")
app.include_router(fights_router, prefix="/fights")
app.include_router(fighters_router, prefix="/fighters")