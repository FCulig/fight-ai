from models.FighterTracker import FighterTracker

FIGHTER_CLASSES = {0, 1}


def track_fighters(
    detection_data: dict,
    video_path: str | None = None,
) -> dict:
    """
    Assign stable provisional track_ids (0/1) to fighters using geometry-only tracking.

    Replaces the old OSNet ReID approach.  Tracking is pure geometry — no video
    frames are read, so video_path is accepted for API compatibility but unused.

    Red/blue corner labelling is NOT done here; that is assign_corners()'s job.

    Args:
        detection_data: In-memory detection dict from process_video().
        video_path:     Unused.  Kept so callers can pass it without branching.

    Returns:
        Track dict: {"fps": float, "frames": [{"image_name": str, "detections": [...]}]}
        Each detection has:
          class_id        — provisional track_id (0 or 1), stable across frames
          model_class_id  — original YOLO class, preserved for corner-assignment fallback
          bbox_xyxy, confidence — unchanged
    """
    fps     = detection_data.get("fps", 50.0)
    frames  = detection_data["frames"]
    tracker = FighterTracker()
    output  = {"fps": fps, "frames": []}
    total   = len(frames)

    for idx, frame in enumerate(frames):
        frame_num  = frame["frame"]
        image_name = f"frames/frame_{frame_num}.jpg"

        fighter_dets = [
            d for d in frame["detections"]
            if d.get("class_id") in FIGHTER_CLASSES
        ]

        tracked = tracker.update(fighter_dets)

        if (idx + 1) % 500 == 0:
            print(f"  Tracking: {idx + 1}/{total} frames processed")

        output["frames"].append({"image_name": image_name, "detections": tracked})

    print(f"Tracking complete — {total} frames processed")
    return output
