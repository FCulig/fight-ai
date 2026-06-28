import os
import re
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

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
from app.services.pipeline_runner import extract_video_meta, run_pipeline_async

router = APIRouter()


_VIDEO_BASE_DIR = Path(os.getenv("VIDEO_BASE_DIR", ""))
_KEEP_VIDEO_ON_DELETE = os.getenv("KEEP_VIDEO_ON_DELETE", "").lower() in ("1", "true", "yes")


def _resolve_video_path(stored_path: str) -> Path:
    p = Path(stored_path)
    return p if p.is_absolute() else (_VIDEO_BASE_DIR / p).resolve()


_ALLOWED_EXTENSIONS = {".mp4", ".mkv", ".mov"}
_UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB


def _sanitize_filename(name: str) -> str:
    stem = Path(name).stem
    suffix = Path(name).suffix.lower()
    safe = re.sub(r"[^\w\-.]", "_", stem).strip("_") or "video"
    return safe + suffix


def _unique_path(directory: Path, filename: str) -> Path:
    dest = directory / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 2
    while True:
        dest = directory / f"{stem}_{counter}{suffix}"
        if not dest.exists():
            return dest
        counter += 1


@router.get("/", response_model=List[FightResponse])
async def get_fights():
    return fight_service.get_all_fights()


@router.post("/upload", response_model=FightResponse, status_code=201)
async def upload_fight(
    file: UploadFile = File(...),
    red_fighter_id: Optional[int] = Form(None),
    blue_fighter_id: Optional[int] = Form(None),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    if (
        red_fighter_id is not None
        and blue_fighter_id is not None
        and red_fighter_id == blue_fighter_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Red and blue corners cannot be the same fighter",
        )

    for fid in (red_fighter_id, blue_fighter_id):
        if fid is not None and fighter_service.get_fighter_by_id(fid) is None:
            raise HTTPException(status_code=404, detail=f"Fighter {fid} not found")

    fight_videos_dir = _VIDEO_BASE_DIR / "fight_videos"
    fight_videos_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _sanitize_filename(file.filename or "video.mp4")
    dest = _unique_path(fight_videos_dir, safe_name)

    try:
        with open(dest, "wb") as f:
            while chunk := await file.read(_UPLOAD_CHUNK_SIZE):
                f.write(chunk)
    except Exception:
        if dest.exists():
            dest.unlink()
        raise

    relative_path = f"fight_videos/{dest.name}"

    try:
        fps, width, height = extract_video_meta(relative_path)
    except Exception:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Could not read video metadata")

    try:
        fight = fight_service.create_fight(
            video_path=relative_path,
            fps=fps,
            width=width,
            height=height,
            red_fighter_id=red_fighter_id,
            blue_fighter_id=blue_fighter_id,
        )
    except Exception as e:
        dest.unlink(missing_ok=True)
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail="A fight with this video already exists")
        raise

    run_pipeline_async(relative_path)

    return fight


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


@router.get("/{fight_id}/video")
async def get_fight_video(fight_id: int):
    fight = fight_service.get_fight_by_id(fight_id)
    if fight is None:
        raise HTTPException(status_code=404, detail="Fight not found")
    video_path = _resolve_video_path(fight.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(str(video_path), media_type="video/mp4")


@router.delete("/{fight_id}", status_code=204)
async def delete_fight(fight_id: int):
    video_path = fight_service.delete_fight(fight_id)
    if video_path is None:
        raise HTTPException(status_code=404, detail="Fight not found")
    if not _KEEP_VIDEO_ON_DELETE:
        resolved = _resolve_video_path(video_path)
        if resolved.exists():
            resolved.unlink()
    return Response(status_code=204)
