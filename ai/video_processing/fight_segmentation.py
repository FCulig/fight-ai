import json
from models.constants import (
    LABEL_ID,
    MIN_FIGHT_START_FRAMES,
    MIN_FIGHT_END_GAP_FRAMES,
    MIN_ROUND_GAP_FRAMES,
    MIN_ROUND_LENGTH_FRAMES,
    MIN_VALID_FRAME_RATIO,
    MIN_FIGHT_DURATION_FRAMES,
    ROUND_ENGAGEMENT_DISTANCE,
)


def segment_fights(detection_results_file):
    """
    Segments a full fight video into rounds based on detection results.
    Memory-optimized: processes frames iteratively without loading entire file.

    Args:
        detection_results_file: Path to the JSON file with detection results.

    Returns:
        dict: {
            "rounds": [(start_frame, end_frame), ...],
            "quality": {
                "is_valid": bool,
                "reason": str,
                "metrics": {...}
            }
        }
    """
    fight_segments, total_frames, valid_frames = find_fight_segments_iterative(detection_results_file)

    if not fight_segments:
        return {
            "rounds": [],
            "quality": {
                "is_valid": False,
                "reason": "No valid fight segments found",
                "metrics": {
                    "total_frames": total_frames,
                    "valid_frame_ratio": valid_frames / total_frames if total_frames > 0 else 0,
                    "round_count": 0,
                    "total_fight_duration_frames": 0,
                }
            }
        }

    all_rounds = []
    for fight_start, fight_end in fight_segments:
        rounds = split_rounds_in_segment_iterative(detection_results_file, fight_start, fight_end)
        all_rounds.extend(rounds)

    total_fight_duration = sum(end - start + 1 for start, end in all_rounds)
    valid_ratio = valid_frames / total_frames if total_frames > 0 else 0
    round_count = len(all_rounds)

    metrics = {
        "total_frames": total_frames,
        "valid_frame_ratio": valid_ratio,
        "round_count": round_count,
        "total_fight_duration_frames": total_fight_duration,
    }

    is_valid = (
        valid_ratio >= MIN_VALID_FRAME_RATIO and
        total_fight_duration >= MIN_FIGHT_DURATION_FRAMES and
        round_count > 0
    )

    reason = ""
    if not is_valid:
        if valid_ratio < MIN_VALID_FRAME_RATIO:
            reason = f"Valid frame ratio too low: {valid_ratio:.2f} < {MIN_VALID_FRAME_RATIO}"
        elif total_fight_duration < MIN_FIGHT_DURATION_FRAMES:
            reason = f"Fight duration too short: {total_fight_duration} < {MIN_FIGHT_DURATION_FRAMES}"
        elif round_count == 0:
            reason = "No valid rounds detected"

    return {
        "rounds": all_rounds,
        "quality": {
            "is_valid": is_valid,
            "reason": reason,
            "metrics": metrics
        }
    }


def iter_detection_frames(detection_results_file):
    """Stream frames from compact JSON format {"frames":[...]}."""
    import json
    with open(detection_results_file, 'r', encoding='utf-8') as f:
        # Read the file content
        content = f.read()

        # Parse the JSON
        data = json.loads(content)

        # Yield each frame
        for frame in data["frames"]:
            yield frame


def find_fight_segments_iterative(detection_results_file):
    fight_segments = []
    total_frames = 0
    valid_frames = 0
    in_segment = False
    segment_start = 0
    valid_count = 0
    invalid_count = 0
    last_valid_frame = 0

    for frame in iter_detection_frames(detection_results_file):
        total_frames += 1
        frame_num = frame["frame"]
        detections = frame["detections"]

        has_red = any(d.get('class_id') == LABEL_ID['fighter_red'] for d in detections)
        has_blue = any(d.get('class_id') == LABEL_ID['fighter_blue'] for d in detections)

        if has_red and has_blue:
            valid_frames += 1
            valid_count += 1
            invalid_count = 0
            last_valid_frame = frame_num
            if not in_segment and valid_count >= MIN_FIGHT_START_FRAMES:
                in_segment = True
                segment_start = frame_num
        else:
            invalid_count += 1
            valid_count = 0
            if in_segment and invalid_count >= MIN_FIGHT_END_GAP_FRAMES:
                fight_segments.append((segment_start, frame_num - invalid_count))
                in_segment = False

    if in_segment and total_frames > 0:
        fight_segments.append((segment_start, last_valid_frame))

    return fight_segments, total_frames, valid_frames


def split_rounds_in_segment_iterative(detection_results_file, fight_start, fight_end):
    rounds = []
    current_round_start = fight_start
    gap_count = 0
    in_gap = False
    last_frame_num = None

    for frame in iter_detection_frames(detection_results_file):
        frame_num = frame["frame"]
        if frame_num < fight_start:
            continue
        if frame_num > fight_end:
            break

        last_frame_num = frame_num
        detections = frame["detections"]

        # Simple engagement check: both fighters present and close in bounding boxes
        red_bbox = next((d["bbox_xyxy"] for d in detections if d["class_id"] == LABEL_ID['fighter_red']), None)
        blue_bbox = next((d["bbox_xyxy"] for d in detections if d["class_id"] == LABEL_ID['fighter_blue']), None)

        engaged = False
        if red_bbox and blue_bbox:
            # Check if bounding boxes are close enough to indicate sustained engagement.
            red_center_x = (red_bbox[0] + red_bbox[2]) / 2
            blue_center_x = (blue_bbox[0] + blue_bbox[2]) / 2
            distance = abs(red_center_x - blue_center_x)
            if distance < ROUND_ENGAGEMENT_DISTANCE:
                engaged = True

        if not engaged:
            if not in_gap:
                in_gap = True
                gap_count = 1
            else:
                gap_count += 1
        else:
            if in_gap and gap_count >= MIN_ROUND_GAP_FRAMES:
                end_frame = frame_num - gap_count - 1
                if end_frame >= current_round_start:
                    rounds.append((current_round_start, end_frame))
                current_round_start = frame_num
            in_gap = False
            gap_count = 0

    if last_frame_num is not None and last_frame_num >= current_round_start:
        rounds.append((current_round_start, last_frame_num))

    rounds = [r for r in rounds if r[1] - r[0] + 1 >= MIN_ROUND_LENGTH_FRAMES]
    return rounds
