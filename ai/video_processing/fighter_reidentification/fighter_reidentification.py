import os
import cv2
import json
import torchreid
from models.IdentityMemory import IdentityMemory

FIGHTER_CLASSES = [0, 1]

def track_fighters(detection_results_path: str):
    frames = json.load(open(detection_results_path))

    extractor = torchreid.utils.FeatureExtractor(
        model_name='osnet_x1_0',
        device='cpu'
    )

    id_mem = IdentityMemory()
    output = {"fps": 50, "frames": []}

    for frame in frames:
        image_name = f"frames/frame_{frame['frame']}.jpg"
        frame_image = cv2.imread(image_name)
        cropped_detections = []

        detections = frame["detections"]
        fighter_detections = [d for d in detections if d.get("class_id") in FIGHTER_CLASSES]

        cropped_detections = []
        for detection in fighter_detections:
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
        for i, d in enumerate(fighter_detections):
            # TODO: Figure out how to not track fighters for reidentification when they are grappling
            #current_fight_state, _ = determine_fight_state(
            #    frame["detections"],
            #    0,
            #    constants.MIN_GRAPPLING_TRESHOLD,
            #    constants.DISTANCE_GRAPPLING_TRESHOLD
            #)

            # TODO: This is not doing much better for grappling frames
            #if current_fight_state == FightState.STRIKING:
            #    reid_id, sim = id_mem.assign(features[i])

            reid_id, sim = id_mem.assign(features[i])
            out_frame["detections"].append({
                "bbox_xyxy": d.get("bbox_xyxy"),
                "confidence": d.get("confidence"),
                "class_id": int(reid_id),
                "sim": float(sim)
            })
        
        output["frames"].append(out_frame)

        with open("runs/output_reidentification.json", "w") as f:
            json.dump(output, f, indent=2)


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
    if crop.size == 0:
        return None
    return crop
