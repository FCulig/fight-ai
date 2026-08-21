from fastapi import APIRouter
from typing import List

from app.services import event_service
from app.models.fight_event import FightEventResponse

router = APIRouter()

@router.get("/", response_model=List[FightEventResponse])
def get_fight_events():
    return event_service.get_fight_events()
