---
paths:
  - "ai/video_processing/fighter_detection/**"
  - "ai/video_processing/fighter_tracking/**"
  - "ai/video_processing/pose_tracking/**"
  - "ai/models/FighterTracker.py"
---

# Fighter detection and tracking

## Detection (`detect_fighters`)
- **One model supplies each box and its skeleton.** The XL pose model (`yolo26x-pose`) detects every person, with a box and 17 keypoints. It is COCO person-only, so it can't tell a fighter from the referee. The nano detector (`weights.pt`) serves only as a per-frame *mask*: pose persons are matched one-to-one against the mask regions (Hungarian, `FIGHTER_SELECT_IOU_FLOOR`), and anyone without a region (referee, cornermen) is dropped.
- Don't go back to nano boxes with XL keypoints copied onto them. The nano box was the lookup key, so a bad box dropped the skeleton entirely, which silently lost training data on the hardest frames.
- **Ignore the nano red/blue class head.** It is a per-frame colour guess with no temporal consistency. Corner is `assign_corners`' job. The one-to-one matching also absorbs a real failure: class-aware NMS can keep one fighter twice, once as red and once as blue.

## Tracking (`FighterTracker`)
- A geometry-only, 2-slot tracker: IoU plus centroid-distance cost, solved with Hungarian matching. It assigns a *provisional* `track_id` of 0 or 1. Corner assignment later corrects any swaps.
- Clinch frames (inter-fighter IoU > `CLINCH_IOU_THRESHOLD`) freeze velocity updates to limit identity swaps.
- Keypoints stay attached to the detection they arrived on. There is no box↔skeleton association step.

## Pose verification
`pose_tracking/pose_verification.py` only renders the `--verify-pose` debug MP4. It has no `fight_state`, so it uses the strict all-15-joints `is_frame_valid()`.
