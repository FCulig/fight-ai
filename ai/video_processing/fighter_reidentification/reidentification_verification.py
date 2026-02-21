import os
import json
import cv2

def verify_reidentification(reid_json_path: str):
    """
    [DEBUG FUNCTION] Create a visualization video with fighter reidentification overlays.
    
    This debugging utility reads a JSON file containing reidentification results and generates
    an MP4 video with annotated bounding boxes for each detected person. It's useful for
    visually inspecting how well the fighter reidentification (reid) system is tracking
    individuals across frames.
    
    Args:
        reid_json_path: Path to JSON file with structure {"fps": int, "frames": [...]}
                       Each frame contains "image_name" and "detections" with bbox_xyxy, 
                       reid_id, and class_id (2=referee, other=fighter).
    
    Output:
        Generates "reid_overlay.mp4" with colored bounding boxes:
        - Yellow: Fighter with reid_id=0
        - Cyan: Fighter with reid_id=1
        - Green: Referee (class_id=2)
        - White: Unidentified fighter
        
    Each box includes a label with reid_id and similarity score (if available).
    """
    OUTPUT_MP4 = "reid_overlay.mp4"

    # If your JSON is {"fps":..., "frames":[...]} this reads correctly.
    data = json.load(open(reid_json_path, "r"))
    fps = int(data.get("fps", 50))
    frames = data["frames"]

    # Colors (BGR). Change if you want.
    COLOR_FIGHTER_0 = (0, 255, 255)   # id 0
    COLOR_FIGHTER_1 = (255, 255, 0)   # id 1
    COLOR_REFEREE   = (0, 255, 0)

    def color_for(det):
        if det.get("class_id") == 2:   # referee
            return COLOR_REFEREE
        rid = det.get("reid_id", None)
        if rid == 0:
            return COLOR_FIGHTER_0
        if rid == 1:
            return COLOR_FIGHTER_1
        return (255, 255, 255)

    # Find first readable frame to initialize writer
    first_img = None
    for fe in frames:
        img_name = fe.get("image_name")
        
        if not img_name:
            continue
        
        im = cv2.imread(img_name)
        if im is not None:
            first_img = im
            break

    if first_img is None:
        raise FileNotFoundError("No readable frames found. Check FRAMES_DIR and image_name mapping.")

    h, w = first_img.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUTPUT_MP4, fourcc, fps, (w, h))

    def draw_det(frame_bgr, det):
        bbox = det.get("bbox_xyxy")
        if not bbox:
            return
        x1, y1, x2, y2 = [int(round(v)) for v in bbox]
        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(0, min(w - 1, x2))
        y2 = max(0, min(h - 1, y2))
        if x2 <= x1 or y2 <= y1:
            return

        col = color_for(det)
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), col, 2)

        # Label
        cls = det.get("class_id", None)
        if cls == 2:
            label = "ref"
        else:
            rid = det.get("reid_id", None)
            sim = det.get("sim", None)
            if rid is None:
                label = "fighter"
            else:
                label = f"id={rid}"
            if sim is not None:
                label += f" s={sim:.2f}"

        ty = max(15, y1 - 6)
        cv2.putText(frame_bgr, label, (x1, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)

    # Render
    written = 0
    missing = 0

    for fe in frames:
        img_name = fe.get("image_name")
        if not img_name:
            missing += 1
            continue

        frame = cv2.imread(img_name)
        if frame is None:
            missing += 1
            continue

        for det in fe.get("detections", []):
            draw_det(frame, det)

        writer.write(frame)
        written += 1

    writer.release()

    print("Wrote:", OUTPUT_MP4)
    print("Frames written:", written, "Missing frames:", missing)
