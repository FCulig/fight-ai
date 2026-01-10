import argparse
from video_processing import process_video
from fight_processing.fight_processing import process_fight

parser = argparse.ArgumentParser(description='Process fight detection data.')
parser.add_argument('video_input', type=str, help='Path to the mp4 file of a fight')
args = parser.parse_args()

video_file = args.video_input

#results = process_video(video_file)
results = "detection_results.json"

process_fight(results)