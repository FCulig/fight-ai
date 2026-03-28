import argparse
from video_processing.video_processing import process_video
from video_processing.fighter_reidentification.fighter_reidentification import track_fighters
from video_processing.fighter_reidentification.reidentification_verification import verify_reidentification
from fight_processing.fight_processing import process_fight
from video_processing.pose_tracking.pose_tracking import track_poses
from video_processing.pose_tracking.pose_verification import verify_pose_tracking

parser = argparse.ArgumentParser(description='Process fight detection data.')
parser.add_argument('video_input', type=str, help='Path to the mp4 file of a fight')
parser.add_argument('--no-db', action='store_true', help='Run without saving events to the database')
args = parser.parse_args()

video_file = args.video_input

#results = process_video(video_file)

#track_fighters("runs/detection_results.json")

#verify_reidentification("runs/output_reidentification.json")

#track_poses("runs/output_reidentification.json")

#verify_pose_tracking("runs/pose_results.json")

process_fight("runs/pose_results.json", save_to_db=not args.no_db)