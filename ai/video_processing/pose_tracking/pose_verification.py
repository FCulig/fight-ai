import json
import cv2


def verify_pose_tracking(pose_json_path: str):
    """[DEBUG FUNCTION] Create a visualization video with pose tracking overlays.

    Reads a JSON file produced by :func:`track_poses` ("runs/pose_results.json") and generates an
    MP4 video with annotated bounding boxes + pose keypoints/skeletons for each detected person.

    Args:
        pose_json_path: Path to JSON file with structure {"fps": int, "frames": [...]}
            Each frame contains "image_name" and "detections" with bbox_xyxy, class_id, and
            keypoints (list of [x, y] coordinates).

    Output:
        Generates "pose_overlay.mp4" with colored skeletons by class_id:
        - Red: class_id=0
        - Blue: class_id=1
        - Green: class_id=2 (referee)
        - White: unknown
    """

    OUTPUT_MP4 = "pose_overlay.mp4"

    data = json.load(open(pose_json_path, "r"))
    fps = int(data.get("fps", 50))
    frames = data.get("frames", [])

    # COCO-like skeleton edges (connect keypoints by index)
    # Reference: https://github.com/ultralytics/ultralytics/blob/main/ultralytics/pose/models/common.py
    SKELETON_EDGES = [
        (0, 1), (0, 2), (1, 3), (2, 4),
        (0, 5), (0, 6),
        (5, 7), (7, 9),
        (6, 8), (8, 10),
        (5, 6),
        (5, 11), (6, 12),
        (11, 12),
        (11, 13), (13, 15),
        (12, 14), (14, 16),
    ]

    COLOR_FIGHTER_0 = (0, 0, 255)
    COLOR_FIGHTER_1 = (255, 0, 0)
    COLOR_REFEREE = (0, 255, 0)

    def color_for(det):
        cid = det.get("class_id")
        if cid == 2:
            return COLOR_REFEREE
        if cid == 0:
            return COLOR_FIGHTER_0
        if cid == 1:
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

    def draw_pose(frame_bgr, det):
        bbox = det.get("bbox_xyxy")
        if bbox and len(bbox) == 4:
            x1, y1, x2, y2 = [int(round(v)) for v in bbox]
            x1 = max(0, min(w - 1, x1))
            y1 = max(0, min(h - 1, y1))
            x2 = max(0, min(w - 1, x2))
            y2 = max(0, min(h - 1, y2))
            if x2 > x1 and y2 > y1:
                cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), color_for(det), 2)

        keypoints = det.get("keypoints")
        if not keypoints or len(keypoints) == 0:
            return

        # Draw skeleton edges
        for a, b in SKELETON_EDGES:
            if a < len(keypoints) and b < len(keypoints):
                pt_a = keypoints[a]
                pt_b = keypoints[b]
                if pt_a is None or pt_b is None:
                    continue
                xa, ya = int(round(pt_a[0])), int(round(pt_a[1]))
                xb, yb = int(round(pt_b[0])), int(round(pt_b[1]))
                if 0 <= xa < w and 0 <= ya < h and 0 <= xb < w and 0 <= yb < h:
                    cv2.line(frame_bgr, (xa, ya), (xb, yb), color_for(det), 2)

        # Draw points
        for k in keypoints:
            if k is None or len(k) < 2:
                continue
            x, y = int(round(k[0])), int(round(k[1]))
            if 0 <= x < w and 0 <= y < h:
                cv2.circle(frame_bgr, (x, y), 3, color_for(det), -1)

        # Label
        cid = det.get("class_id")
        label = f"id={cid}" if cid is not None else "person"
        ty = max(15, int(round(keypoints[0][1])) - 6) if keypoints and len(keypoints) > 0 else 15
        cv2.putText(frame_bgr, label, (10, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_for(det), 1, cv2.LINE_AA)

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
            draw_pose(frame, det)

        writer.write(frame)
        written += 1

    writer.release()

    print("Wrote:", OUTPUT_MP4)
    print("Frames written:", written, "Missing frames:", missing)
