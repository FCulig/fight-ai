import shutil
from app.utils.video import process_video

async def run_tracking(file):
    input_path = f"/tmp/{file.filename}"

    #with open(input_path, "wb") as buffer:
    #    shutil.copyfileobj(file.file, buffer)

    output_path = process_video(input_path)
    return output_path