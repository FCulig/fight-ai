import argparse
from video_processing.video_processing import process_video
from video_processing.fighter_reidentification.fighter_reidentification import track_fighters
from video_processing.fighter_reidentification.reidentification_verification import verify_reidentification
from video_processing.pose_tracking.pose_tracking import track_poses
from video_processing.pose_tracking.pose_verification import verify_pose_tracking
from video_processing.fight_segmentation import segment_fights

parser = argparse.ArgumentParser(description='Process fight detection data.')
parser.add_argument('video_input', type=str, help='Path to the mp4 file of a fight')
parser.add_argument('--detection-file', type=str, help='Path to existing detection results JSON file (skip video processing)')
parser.add_argument('--no-db', action='store_true', help='Run without saving events to the database')
parser.add_argument('--segment', action='store_true', help='Run fight segmentation instead of full processing')
args = parser.parse_args()

video_file = args.video_input

#python main.py your_video.mp4 --segment
if args.segment:
    # Run segmentation on full video
    if args.detection_file:
        print("Using existing detection results from:", args.detection_file)
        detection_file = args.detection_file
    else:
        print("Processing video for detection results:", video_file)
        detection_file = process_video(video_file)
    result = segment_fights(detection_file)
    print("Segmentation Result:")
    print(f"Rounds: {result['rounds']}")
    print(f"Quality: {result['quality']}")
else:
    # Original stepwise flow - import fight_processing only when needed
    from fight_processing.fight_processing import process_fight
    results = process_video(video_file)

    #track_fighters("runs/detection_results.json")

    #verify_reidentification("runs/output_reidentification.json")

    #track_poses("runs/output_reidentification.json")

    verify_pose_tracking("runs/pose_results.json")

    #process_fight("runs/pose_results.json", save_to_db=not args.no_db)