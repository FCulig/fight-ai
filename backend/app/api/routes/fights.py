import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from app.models.fight import FightResponse
from app.models.fighter_frame import FighterFrameResponse
from app.models.fight_event import FightEventResponse
from app.models.round import RoundResponse
from app.services import event_service, fight_service, fighter_frame_service, round_service

router = APIRouter()

_VIDEO_BASE_DIR = Path(os.getenv("VIDEO_BASE_DIR", ""))


def _resolve_video_path(stored_path: str) -> Path:
    p = Path(stored_path)
    return p if p.is_absolute() else (_VIDEO_BASE_DIR / p).resolve()


@router.get("/", response_model=List[FightResponse])
async def get_fights():
    return fight_service.get_all_fights()


@router.get("/{fight_id}/rounds/", response_model=List[RoundResponse])
async def get_rounds(fight_id: int):
    return round_service.get_rounds(fight_id)


@router.get("/{fight_id}/frames/", response_model=List[FighterFrameResponse])
async def get_fighter_frames(fight_id: int):
    return fighter_frame_service.get_fighter_frames(fight_id)


@router.get("/{fight_id}/events/", response_model=List[FightEventResponse])
async def get_fight_events(fight_id: int):
    return event_service.get_events_by_fight(fight_id)


@router.get("/{fight_id}/video")
async def get_fight_video(fight_id: int):
    fight = fight_service.get_fight_by_id(fight_id)
    if fight is None:
        raise HTTPException(status_code=404, detail="Fight not found")
    video_path = _resolve_video_path(fight.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(str(video_path), media_type="video/mp4")


@router.delete("/{fight_id}/", status_code=204)
async def delete_fight(fight_id: int):
    found = fight_service.delete_fight(fight_id)
    if not found:
        raise HTTPException(status_code=404, detail="Fight not found")
    return Response(status_code=204)
