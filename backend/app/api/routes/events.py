from fastapi import APIRouter, HTTPException, Response
from typing import List

from app.services import event_service
from app.models.fight_event import FightEventResponse

router = APIRouter()

@router.get("/", response_model=List[FightEventResponse])
def get_fight_events():
    return event_service.get_fight_events()


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int):
    deleted = event_service.delete_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")
    return Response(status_code=204)