import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.models.fight import FightResponse
from app.models.fighter_frame import FighterFrameResponse
from app.models.fight_event import FightEventResponse
from app.models.round import RoundResponse
from app.services import (
    event_service,
    fight_service,
    fighter_frame_service,
    fighter_service,
    round_service,
)

router = APIRouter()


class CornerAssignment(BaseModel):
    red_fighter_id: Optional[int] = None
    blue_fighter_id: Optional[int] = None

_VIDEO_BASE_DIR = Path(os.getenv("VIDEO_BASE_DIR", ""))
_KEEP_VIDEO_ON_DELETE = os.getenv("KEEP_VIDEO_ON_DELETE", "").lower() in ("1", "true", "yes")


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
async def get_fight_events(
    fight_id: int,
    fighter_id: Optional[int] = None,
    action: Optional[str] = None,
    success: Optional[bool] = None,
):
    return event_service.get_events_by_fight(fight_id, fighter_id, action, success)


@router.patch("/{fight_id}/corners/", response_model=FightResponse)
async def assign_corners(fight_id: int, payload: CornerAssignment):
    for fid in (payload.red_fighter_id, payload.blue_fighter_id):
        if fid is not None and fighter_service.get_fighter_by_id(fid) is None:
            raise HTTPException(status_code=404, detail=f"Fighter {fid} not found")
    ok = fighter_service.set_fight_corners(
        fight_id, payload.red_fighter_id, payload.blue_fighter_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Fight not found")
    return fight_service.get_fight_by_id(fight_id)


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
    video_path = fight_service.delete_fight(fight_id)
    if video_path is None:
        raise HTTPException(status_code=404, detail="Fight not found")
    if not _KEEP_VIDEO_ON_DELETE:
        resolved = _resolve_video_path(video_path)
        if resolved.exists():
            resolved.unlink()
    return Response(status_code=204)
