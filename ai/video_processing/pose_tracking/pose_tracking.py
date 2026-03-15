import json
import cv2
from ultralytics import YOLO

def track_poses(reid_json_path: str, output_json_path: str = "runs/pose_results.json"):
    data = json.load(open(reid_json_path, "r"))
    frames = data["frames"]
    model = YOLO("yolo26x-pose.pt")

    for frame in frames:
        image_path = frame["image_name"]
        detections = frame["detections"]
        
        # Load the frame image
        image = cv2.imread(image_path)
        
        if image is None:
            print(f"Error: Could not load image from {image_path}")
            continue
        
        # Process each detection
        for detection in detections:
            bbox_xyxy = detection["bbox_xyxy"]
            x_min, y_min, x_max, y_max = bbox_xyxy
            
            # Convert to integers for cropping
            x_min, y_min = int(x_min), int(y_min)
            x_max, y_max = int(x_max), int(y_max)
            
            # Crop the detection from the image
            cropped_image = image[y_min:y_max, x_min:x_max]
            
            # Run YOLO pose detection on the cropped image
            results = model(cropped_image)

            # Extract keypoints and add to detection
            if results and len(results) > 0 and results[0].keypoints is not None and len(results[0].keypoints.xy) > 0:
                keypoints = results[0].keypoints.xy[0].numpy()

                # After cropping, the keypoints are relative to the cropped image. 
                # We need to shift them back to the original image coordinates.
                keypoints[:, 0] += x_min  # shift x by left edge of crop
                keypoints[:, 1] += y_min  # shift y by top edge of crop

                detection["keypoints"] = keypoints.tolist()
            else:
                detection["keypoints"] = None
    
    # Write updated data to JSON file
    with open(output_json_path, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"Pose tracking complete. Results saved to {output_json_path}")