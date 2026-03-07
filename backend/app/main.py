from fastapi import FastAPI
from app.api.routes.tracking import router as tracking_router
from app.api.routes.events import router as fight_events_router

app = FastAPI(title="Fight AI")

app.include_router(tracking_router, prefix="/tracking")
app.include_router(fight_events_router, prefix="/events")