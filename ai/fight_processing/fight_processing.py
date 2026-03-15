import json

from sqlalchemy import text
from databse import SessionLocal

from fight_processing.fight_processing_util import (
    determine_fight_state,
    is_frame_valid
)

from models.FightState import FightState
from models.constants import (
    MIN_GRAPPLING_THRESHOLD,
    DISTANCE_GRAPPLING_THRESHOLD
)

def process_fight(detection_results_file):
    db = SessionLocal()
    data = json.load(open(detection_results_file))

    # Each fight/round starts in standup
    current_fight_state = FightState.STRIKING
    previous_fight_state = FightState.STRIKING

    # Counters to track consecutive frames in each state
    grappling_frames = 0
    striking_frames = 0

    # Counter to track total frames spent in grappling state used as output
    frames_spent_grappling = 0

    for (index, frame) in enumerate(data["frames"]):
        if not is_frame_valid(frame["detections"]):
            #print(f"Frame {index + 1} invalid, skipping.")

            if current_fight_state == FightState.GRAPPLING:
                frames_spent_grappling += 1
            
            continue

        current_fight_state, grappling_frames, striking_frames = determine_fight_state(
            frame["detections"],
            grappling_frames,
            striking_frames,
            current_fight_state,
            MIN_GRAPPLING_THRESHOLD,
            DISTANCE_GRAPPLING_THRESHOLD
        )

        if current_fight_state == FightState.GRAPPLING:
            frames_spent_grappling += 1

        if previous_fight_state != current_fight_state:
            # TODO: use db file/class to insert via function, do not hard code SQL query here
            db.execute(
                text("""
                INSERT INTO fight_events (frame, description)
                VALUES (:frame, :description)
                """),
                {"frame": index + 1, "description": f"Fight state changed to {current_fight_state}"}
            )
            print(f"Fight state changed to {current_fight_state} at frame {index + 1}")
            previous_fight_state = current_fight_state

    print(f"Frames spent grappling: {frames_spent_grappling}")
    db.commit()
    db.close()