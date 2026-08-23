from models.FighterTracker import FighterTracker
from models.constants import BOX_SMOOTHING_ENABLED
from video_processing.fighter_tracking.box_smoothing import smooth_track_boxes


def track_fighters(
    detection_data: dict,
    video_path: str | None = None,
) -> dict:
    """
    Assign stable provisional track_ids (0/1) to fighters using geometry-only tracking.

    Tracking is pure geometry — no video frames are read, so video_path is
    accepted for API compatibility but unused.

    Input comes from fighter_detection.detect_fighters(), which has already
    settled fighter-vs-bystander and capped each frame at two detections, so
    there is no class filtering left to do here.

    Red/blue corner labelling is NOT done here; that is assign_corners()'s job.

    Args:
        detection_data: In-memory detection dict from detect_fighters().
        video_path:     Unused.  Kept so callers can pass it without branching.

    Returns:
        Track dict: {"fps": float, "frames": [{"image_name": str, "detections": [...]}]}
        Each detection has:
          class_id      — provisional track_id (0 or 1), stable across frames
          bbox_xyxy     — XL pose box, smoothed (see box_smoothing) unless
                          BOX_SMOOTHING_ENABLED is off
          confidence    — unchanged, or None on a gap-filled box
          keypoints     — carried from detection, or None on a gap-filled box
          interpolated  — present and True only on gap-filled boxes
    """
    fps     = detection_data.get("fps", 50.0)
    frames  = detection_data["frames"]
    tracker = FighterTracker(fps=fps)
    output  = {"fps": fps, "frames": []}
    total   = len(frames)

    for idx, frame in enumerate(frames):
        frame_num  = frame["frame"]
        image_name = f"frames/frame_{frame_num}.jpg"

        tracked = tracker.update(frame["detections"])

        if (idx + 1) % 500 == 0:
            print(f"  Tracking: {idx + 1}/{total} frames processed")

        output["frames"].append({"image_name": image_name, "detections": tracked})

    print(f"Tracking complete — {total} frames processed")

    if BOX_SMOOTHING_ENABLED:
        smooth_track_boxes(output)

    return output
