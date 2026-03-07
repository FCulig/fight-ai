from fastapi import APIRouter, UploadFile, File
from app.services.tracking_service import run_tracking

router = APIRouter()

@router.post("/video")
async def track_video(file: UploadFile = File(...)):
    result_path = await run_tracking(file)
    return {"output": result_path}