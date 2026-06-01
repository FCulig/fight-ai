import cv2
import torch
import torchreid
from models.IdentityMemory import IdentityMemory

# torchreid only supports 'cuda' or 'cpu' (no MPS).
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

FIGHTER_CLASSES = [0, 1]


def track_fighters(
    detection_data: dict,
    video_path: str | None = None,
) -> dict:
    """
    Assign stable red/blue identities to fighters across frames.

    Args:
        detection_data: In-memory detection dict produced by process_video()
                        (or loaded from a --detection-file dev override).
        video_path:     Path to the source .mp4. When supplied, frames are read
                        directly from the video (no frames/ directory needed).
                        Falls back to frames/frame_N.jpg when None.

    Returns:
        Reid dict in-memory:
            {"fps": float, "frames": [{"image_name": str, "detections": [...]}]}
        No file is written to disk.
    """
    fps    = detection_data.get("fps", 50.0)
    frames = detection_data["frames"]

    cap = None
    if video_path:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")
        # Frames are processed in sequential order — never seek, just read forward.
        print(f"ReID: reading frames sequentially from video: {video_path}")
    else:
        print("ReID: reading frames from frames/ directory")

    extractor = torchreid.utils.FeatureExtractor(
        model_name='osnet_x1_0',
        device=_DEVICE,
    )

    id_mem  = IdentityMemory()
    output  = {"fps": fps, "frames": []}
    total   = len(frames)
    missing = 0

    for idx, frame in enumerate(frames):
        frame_num  = frame["frame"]
        image_name = f"frames/frame_{frame_num}.jpg"

        # Read frame from video or disk.
        # VideoCapture: read sequentially — no seeking, avoids H.264 decode errors.
        # Frames with no fighters are grabbed without decoding (faster).
        detections   = frame["detections"]
        fighter_dets = [d for d in detections if d.get("class_id") in FIGHTER_CLASSES]

        if cap is not None:
            if fighter_dets:
                ret, frame_image = cap.read()
                frame_image = frame_image if ret else None
            else:
                cap.grab()   # advance position without decoding
                frame_image = None
        else:
            frame_image = cv2.imread(image_name)

        if frame_image is None and fighter_dets:
            missing += 1
            output["frames"].append({"image_name": image_name, "detections": []})
            continue

        # Progress log
        if (idx + 1) % 500 == 0:
            print(f"  ReID: {idx+1}/{total} frames processed")

        cropped_detections = []

        for detection in fighter_dets:
            bbox = detection["bbox_xyxy"]
            if not bbox:
                continue
            crop = crop_fighter(frame_image, bbox)
            if crop is None:
                continue
            cropped_detections.append(crop)

        features = []
        if cropped_detections:
            features = extractor(cropped_detections)

        out_frame = {"image_name": image_name, "detections": []}
        for i, d in enumerate(fighter_dets):
            # TODO: Figure out how to not track fighters for reidentification when they are grappling
            reid_id, sim = id_mem.assign(features[i])
            out_frame["detections"].append({
                "bbox_xyxy":  d.get("bbox_xyxy"),
                "confidence": d.get("confidence"),
                "class_id":   int(reid_id),
                "sim":        float(sim),
            })

        output["frames"].append(out_frame)

    if cap:
        cap.release()

    print(f"ReID complete — {total} frames processed, {missing} unreadable")
    return output


def crop_fighter(frame_bgr, bbox_xyxy, pad=0.1):
    """Crop bbox from frame with padding and bounds checking. Returns BGR crop or None."""
    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = [int(round(v)) for v in bbox_xyxy]

    bw, bh = x2 - x1, y2 - y1
    if bw <= 1 or bh <= 1:
        return None

    px, py = int(bw * pad), int(bh * pad)
    x1 = max(0, x1 - px)
    y1 = max(0, y1 - py)
    x2 = min(w, x2 + px)
    y2 = min(h, y2 + py)

    if x2 <= x1 or y2 <= y1:
        return None

    crop = frame_bgr[y1:y2, x1:x2]
    return crop if crop.size > 0 else None
