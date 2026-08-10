import asyncio
import json
import os
import re
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.models.fight import FightResponse
from app.models.fighter_frame import FighterFrameResponse
from app.models.fight_event import FightEventCreate, FightEventResponse
from app.models.round import RoundResponse
from app.services import (
    event_service,
    fight_service,
    fighter_frame_service,
    fighter_service,
    round_service,
)
from app.services.pipeline_runner import extract_video_meta, run_pipeline_async, terminate_pipeline
from app.utils.fight_state_listener import register_queue, unregister_queue

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
def get_fights():
    return fight_service.get_all_fights()


@router.get("/stream")
async def stream_fight_state(request: Request):
    async def event_generator():
        q: asyncio.Queue = asyncio.Queue()
        register_queue(q)
        try:
            snapshot = await asyncio.to_thread(fight_service.get_all_fights)
            data = json.dumps([
                {"id": f.id, "state": f.state} for f in snapshot
            ])
            yield f"event: snapshot\ndata: {data}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            unregister_queue(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/upload", response_model=FightResponse, status_code=201)
async def upload_fight(
    file: UploadFile = File(...),
    red_fighter_id: Optional[int] = Form(None),
    blue_fighter_id: Optional[int] = Form(None),
    mode: str = Form("ai"),
):
    if mode not in ("ai", "manual"):
        raise HTTPException(status_code=400, detail="mode must be 'ai' or 'manual'")

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
    tmp_dest = dest.with_name(f".{dest.name}.part")

    try:
        with open(tmp_dest, "wb") as f:
            while chunk := await file.read(_UPLOAD_CHUNK_SIZE):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        tmp_dest.rename(dest)
    except Exception:
        tmp_dest.unlink(missing_ok=True)
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

    pid = run_pipeline_async(relative_path, skip_events=(mode == "manual"))
    fight_service.set_fight_pid(fight.id, pid)

    return fight


@router.get("/{fight_id}/rounds/", response_model=List[RoundResponse])
def get_rounds(fight_id: int):
    return round_service.get_rounds(fight_id)


@router.get("/{fight_id}/frames/", response_model=List[FighterFrameResponse])
def get_fighter_frames(fight_id: int):
    return fighter_frame_service.get_fighter_frames(fight_id)


@router.get("/{fight_id}/events/", response_model=List[FightEventResponse])
def get_fight_events(
    fight_id: int,
    fighter_id: Optional[int] = None,
    action: Optional[str] = None,
    success: Optional[bool] = None,
):
    return event_service.get_events_by_fight(fight_id, fighter_id, action, success)


@router.post("/{fight_id}/events/", response_model=FightEventResponse, status_code=201)
def create_fight_event(fight_id: int, payload: FightEventCreate):
    fight = fight_service.get_fight_by_id(fight_id)
    if fight is None:
        raise HTTPException(status_code=404, detail="Fight not found")
    if (
        payload.fighter_id is not None
        and payload.fighter_id != fight.red_fighter_id
        and payload.fighter_id != fight.blue_fighter_id
    ):
        raise HTTPException(
            status_code=400,
            detail="fighter_id must be one of this fight's assigned corners",
        )
    return event_service.create_event(fight_id, payload)


@router.post("/{fight_id}/finish-labeling", response_model=FightResponse)
def finish_labeling(fight_id: int):
    fight = fight_service.finish_labeling(fight_id)
    if fight is None:
        raise HTTPException(
            status_code=409,
            detail="Fight is not currently in labeling_in_progress state",
        )
    return fight


@router.get("/{fight_id}/video")
def get_fight_video(fight_id: int):
    fight = fight_service.get_fight_by_id(fight_id)
    if fight is None:
        raise HTTPException(status_code=404, detail="Fight not found")
    video_path = _resolve_video_path(fight.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(str(video_path), media_type="video/mp4")


@router.delete("/{fight_id}", status_code=204)
def delete_fight(fight_id: int):
    pid = fight_service.get_fight_pid(fight_id)
    if pid is not None:
        terminate_pipeline(pid)

    video_path = fight_service.delete_fight(fight_id)
    if video_path is None:
        raise HTTPException(status_code=404, detail="Fight not found")
    if not _KEEP_VIDEO_ON_DELETE:
        resolved = _resolve_video_path(video_path)
        if resolved.exists():
            resolved.unlink()
    return Response(status_code=204)
