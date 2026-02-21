import json

from sqlalchemy import text
from databse import SessionLocal

from fight_processing.fight_processing_util import (
    calculate_fighter_centers,
    calculate_distance_between_points,
    determine_fight_state
)

from models.FightState import FightState
from models.constants import (
    MIN_GRAPPLING_TRESHOLD,
    IOU_GRAPPLING_TRESHOLD
)

def process_fight(detection_results_file):
    db = SessionLocal()
    data = json.load(open(detection_results_file))

    # Each fight/round starts in standup
    current_fight_state, previous_frame_fight_state = FightState.STRIKING, FightState.STRIKING

    # Varaible tracking number of frames spent in a current fight state
    current_fight_state_frames = 0
    frames_spent_grappling = 0

    for (index, frame) in enumerate(data["frames"]):
        red_center, blue_center = calculate_fighter_centers(frame["detections"])

        if red_center == (None, None) or blue_center == (None, None):
            print("Current frame is invalid, proceeding to keep the same fight state.")
            current_fight_state_frames += 1
        else:
            current_fight_state, current_fight_state_frames = determine_fight_state(
                frame["detections"],
                current_fight_state_frames,
                MIN_GRAPPLING_TRESHOLD,
                IOU_GRAPPLING_TRESHOLD
            )

        if current_fight_state == FightState.GRAPPLING:
            frames_spent_grappling += 1
            print("Fighters are grappling")
        else:
            print("Fighters are striking")
        
        if previous_frame_fight_state != current_fight_state:
            previous_frame_fight_state = current_fight_state
            # TODO: use db file/class to insert via function, do not hard code SQL query here
            db.execute(
                text("""
                INSERT INTO fight_events (frame, description)
                VALUES (:frame, :description)
                """),
                {"frame": index + 1, "description": f"Fight state changed to {current_fight_state}"}
            )
            print(f"Fight state changed to {current_fight_state} at frame {index + 1}")

    print(f"Frames spent grappling: {frames_spent_grappling}")
    db.commit()
    db.close()