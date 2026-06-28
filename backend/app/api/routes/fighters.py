from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.models.fighter import FighterCreate, FighterResponse
from app.models.fight_event import FightEventResponse
from app.services import fighter_service

router = APIRouter()


@router.get("/", response_model=List[FighterResponse])
async def list_fighters(search: Optional[str] = None):
    return fighter_service.get_fighters(search)


@router.post("/", response_model=FighterResponse, status_code=201)
async def create_fighter(payload: FighterCreate):
    return fighter_service.create_fighter(payload)


@router.get("/{fighter_id}/events/", response_model=List[FightEventResponse])
async def get_fighter_events(
    fighter_id: int,
    action: Optional[str] = None,
    success: Optional[bool] = None,
):
    return fighter_service.get_events_by_fighter(fighter_id, action, success)
