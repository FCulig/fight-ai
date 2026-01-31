import json

from fight_processing.fight_processing_util import (
    calculate_fighter_centers,
    calculate_distance_between_points,
    determine_fight_state
)

from models.FightState import FightState

def process_fight(detection_results_file):
    # In future extract this from an input video
    INPUT_FPS = 50

    # Mininum number of frames for which delta distance needs to hold value in order for grappling to start
    MIN_GRAPPLING_TRESHOLD = 20

    # Intersection over Union threshold to determine if fighters are grappling
    IOU_GRAPPLING_TRESHOLD = 0.2

    data = json.load(open(detection_results_file))

    # Find first frame where both fighters are visible so that velocity can be calculated
    #first_frame = next((index for index, value in enumerate(data) if len(value["detections"]) == 3), None)
    #if first_frame is None:
    #    raise ValueError("No frame found with 3 detections")

    # Delta distance is change of the distance between centers of fighters accross two frames:
    # if 0 -> fighters at the same distance as in the previous frame
    # if positive -> figters are separating, bigger distance as in the previous frame
    # if negative -> fighters are closer than in the previous frame
    delta_distance = 0
    previous_distance = 0

    # Each fight/round starts in standup
    current_fight_state = FightState.STRIKING
    # Varaible tracking number of frames spent in a current fight state
    current_fight_state_frames = 0

    frames_spent_grappling = 0

    for frame in data:
        print(f"---{frame["frame"]}---")

        red_center, blue_center = calculate_fighter_centers(frame["detections"])

        if red_center == (None, None) or blue_center == (None, None):
            previous_distance = None
            current_fight_state = FightState.STRIKING

            # When one of the fighters is not visible, we cannot do anything.
            # This can occur mid fight due to bad camera angles/camera operators.
            print("Current frame is invalid, skipping.")
            continue
        
        # Currently distance is not used for anything other than debug prints.
        # TODO: Use distance to detect who initiated the grappling.
        distance = calculate_distance_between_points(*red_center, *blue_center)

        #print(f"Red center: {red_center}, Blue center: {blue_center}")
        print(f"Distance between fighters: {distance}")

        # Calculate delta distance
        #if previous_distance is None:
        #    delta_distance = None  # No previous frame to compare with
        #else:
        #    delta_distance = distance - previous_distance

        # Update previous distance for the next iteration
        previous_distance = distance

        # Determine and update fight state
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

    print(f"Frames spent grappling: {frames_spent_grappling}")