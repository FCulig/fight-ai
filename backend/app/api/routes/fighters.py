from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.models.fighter import FighterCreate, FighterResponse
from app.models.fight_event import FightEventResponse
from app.services import fighter_service
from app.utils.auth import require_role

router = APIRouter()


@router.get("/", response_model=List[FighterResponse])
def list_fighters(search: Optional[str] = None):
    return fighter_service.get_fighters(search)


# Fighters are only created from the upload dialog, so creating one is admin-only like upload.
@router.post("/", response_model=FighterResponse, status_code=201, dependencies=[Depends(require_role("admin"))])
def create_fighter(payload: FighterCreate):
    return fighter_service.create_fighter(payload)


@router.get("/{fighter_id}/events/", response_model=List[FightEventResponse])
def get_fighter_events(
    fighter_id: int,
    action: Optional[str] = None,
    success: Optional[bool] = None,
):
    return fighter_service.get_events_by_fighter(fighter_id, action, success)
