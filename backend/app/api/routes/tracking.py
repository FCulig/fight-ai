from fastapi import APIRouter, Depends, UploadFile, File
from app.services.tracking_service import run_tracking
from app.utils.auth import require_role

router = APIRouter()

@router.post("/video", dependencies=[Depends(require_role("admin"))])
async def track_video(file: UploadFile = File(...)):
    result_path = await run_tracking(file)
    return {"output": result_path}