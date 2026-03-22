import json
from collections import deque

from sqlalchemy import text
from database import SessionLocal

from fight_processing.fight_processing_util import (
    detect_strikes,
    determine_fight_state,
    determine_takedown_initiator,
    get_hip_height,
    is_frame_valid
)

from models.FightState import FightState
from models.constants import (
    MIN_GRAPPLING_THRESHOLD,
    DISTANCE_GRAPPLING_THRESHOLD,
    TAKEDOWN_LOOKBACK_FRAMES
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

    # Rolling buffer of hip heights for takedown initiator detection
    hip_history = deque(maxlen=TAKEDOWN_LOOKBACK_FRAMES)

    # Previous frame keypoints for velocity-based strike detection
    prev_red_kp, prev_blue_kp = None, None

    # Per-fighter, per-limb state for strike detection (cooldown + extension frame counter)
    def _limb_state():
        return {"cooldown": 0, "extension_frames": 0}

    strike_state = {
        "red":  {"left_punch": _limb_state(), "right_punch": _limb_state(), "left_kick": _limb_state(), "right_kick": _limb_state()},
        "blue": {"left_punch": _limb_state(), "right_punch": _limb_state(), "left_kick": _limb_state(), "right_kick": _limb_state()},
    }

    for (index, frame) in enumerate(data["frames"]):
        if not is_frame_valid(frame["detections"]):
            if current_fight_state == FightState.GRAPPLING:
                frames_spent_grappling += 1
            continue

        red_kp, blue_kp = None, None
        for d in frame["detections"]:
            if d["class_id"] == 0:
                red_kp = d["keypoints"]
            elif d["class_id"] == 1:
                blue_kp = d["keypoints"]

        if red_kp and blue_kp:
            hip_history.append({
                "red": get_hip_height(red_kp),
                "blue": get_hip_height(blue_kp)
            })

            if current_fight_state == FightState.STRIKING and prev_red_kp and prev_blue_kp:
                for strike in detect_strikes(red_kp, blue_kp, prev_red_kp, prev_blue_kp, strike_state):
                    description = f"{strike['fighter']} threw a {strike['type']}"
                    db.execute(
                        text("INSERT INTO fight_events (frame, description) VALUES (:frame, :description)"),
                        {"frame": index + 1, "description": description}
                    )
                    print(description + f" at frame {index + 1}")

            prev_red_kp  = red_kp
            prev_blue_kp = blue_kp

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
            description = f"Fight state changed to {current_fight_state}"

            if current_fight_state == FightState.GRAPPLING:
                initiator = determine_takedown_initiator(hip_history)
                if initiator:
                    description += f", takedown initiated by {initiator}"

            # TODO: use db file/class to insert via function, do not hard code SQL query here
            db.execute(
                text("""
                INSERT INTO fight_events (frame, description)
                VALUES (:frame, :description)
                """),
                {"frame": index + 1, "description": description}
            )
            print(description + f" at frame {index + 1}")
            previous_fight_state = current_fight_state

    print(f"Frames spent grappling: {frames_spent_grappling}")
    db.commit()
    db.close()