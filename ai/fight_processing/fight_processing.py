import json
from collections import deque
from typing import Optional

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

_FRAME_BATCH_SIZE = 1_000


def _insert_event(db, frame: int, description: str, fight_id: int) -> None:
    db.execute(
        text(
            "INSERT INTO fight_events (frame, description, fight_id) "
            "VALUES (:frame, :description, :fight_id)"
        ),
        {"frame": frame, "description": description, "fight_id": fight_id},
    )


def _flush_frame_batch(db, batch: list[dict]) -> None:
    """Bulk-insert fighter_frames rows and flush (without committing)."""
    db.execute(
        text(
            "INSERT INTO fighter_frames "
            "(fight_id, frame, fighter_id, x1, y1, x2, y2, confidence, keypoints) "
            "VALUES (:fight_id, :frame, :fighter_id, :x1, :y1, :x2, :y2, :confidence, "
            "CAST(:keypoints AS JSONB))"
        ),
        batch,
    )
    db.flush()   # release memory; does NOT end the transaction


def process_fight(
    pose_data: dict,
    fight_id: int,
    rounds: Optional[list[tuple[int, int]]] = None,
) -> None:
    """
    Run the fight state machine and persist all events, rounds, and fighter
    bounding boxes to the database.

    Everything is written inside a single transaction so either every row for
    the fight lands or none does.  Existing rows for `fight_id` are deleted
    first, making repeated calls idempotent.

    The processed / processed_at flag is the caller's responsibility
    (run_pipeline for single-file mode, run_batch for batch mode).

    Args:
        pose_data:  In-memory pose dict produced by track_poses()
                    (or loaded from a --pose-results dev override).
        fight_id:   Primary key of the fights row for this video.
        rounds:     List of (start_frame, end_frame) tuples from segment_fights().
    """
    db = SessionLocal()
    try:
        # ------------------------------------------------------------------
        # Delete existing rows for this fight (idempotent re-processing)
        # ------------------------------------------------------------------
        db.execute(text("DELETE FROM fight_events  WHERE fight_id = :fid"), {"fid": fight_id})
        db.execute(text("DELETE FROM fighter_frames WHERE fight_id = :fid"), {"fid": fight_id})
        db.execute(text("DELETE FROM rounds         WHERE fight_id = :fid"), {"fid": fight_id})

        # ------------------------------------------------------------------
        # Insert rounds
        # ------------------------------------------------------------------
        round_starts: dict[int, int] = {}
        round_ends:   dict[int, int] = {}
        if rounds:
            for i, (start, end) in enumerate(rounds, 1):
                db.execute(
                    text(
                        "INSERT INTO rounds (fight_id, round_number, start_frame, end_frame) "
                        "VALUES (:fid, :rn, :sf, :ef)"
                    ),
                    {"fid": fight_id, "rn": i, "sf": start, "ef": end},
                )
                round_starts[start] = i
                round_ends[end]     = i

        # ------------------------------------------------------------------
        # State machine + fighter_frames collection
        # ------------------------------------------------------------------
        current_fight_state  = FightState.STRIKING
        previous_fight_state = FightState.STRIKING

        grappling_frames      = 0
        striking_frames       = 0
        frames_spent_grappling = 0

        hip_history  = deque(maxlen=TAKEDOWN_LOOKBACK_FRAMES)
        prev_red_kp, prev_blue_kp = None, None

        def _limb_state():
            return {"cooldown": 0, "extension_frames": 0}

        strike_state = {
            "red":  {"left_punch": _limb_state(), "right_punch": _limb_state(),
                     "left_kick":  _limb_state(), "right_kick":  _limb_state()},
            "blue": {"left_punch": _limb_state(), "right_punch": _limb_state(),
                     "left_kick":  _limb_state(), "right_kick":  _limb_state()},
        }

        frame_batch: list[dict] = []

        for index, frame in enumerate(pose_data["frames"]):
            frame_number = index + 1

            if frame_number in round_starts:
                description = f"Round {round_starts[frame_number]} started"
                _insert_event(db, frame_number, description, fight_id)
                print(description + f" at frame {frame_number}")

            if frame_number in round_ends:
                description = f"Round {round_ends[frame_number]} ended"
                _insert_event(db, frame_number, description, fight_id)
                print(description + f" at frame {frame_number}")

            # Collect fighter bboxes (+ keypoints) for fighter_frames table
            for d in frame["detections"]:
                if d["class_id"] in (0, 1):
                    bbox = d.get("bbox_xyxy") or []
                    if len(bbox) == 4:
                        raw_kp = d.get("keypoints")
                        frame_batch.append({
                            "fight_id":   fight_id,
                            "frame":      frame_number,
                            "fighter_id": d["class_id"],
                            "x1": bbox[0], "y1": bbox[1],
                            "x2": bbox[2], "y2": bbox[3],
                            "confidence": d.get("confidence"),
                            "keypoints":  json.dumps(raw_kp),  # [[x,y]*17] or null
                        })

            if len(frame_batch) >= _FRAME_BATCH_SIZE:
                _flush_frame_batch(db, frame_batch)
                frame_batch.clear()

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
                    "red":  get_hip_height(red_kp),
                    "blue": get_hip_height(blue_kp),
                })

                if current_fight_state == FightState.STRIKING and prev_red_kp and prev_blue_kp:
                    for strike in detect_strikes(
                        red_kp, blue_kp, prev_red_kp, prev_blue_kp, strike_state
                    ):
                        description = f"{strike['fighter']} threw a {strike['type']}"
                        _insert_event(db, frame_number, description, fight_id)
                        print(description + f" at frame {frame_number}")

                prev_red_kp  = red_kp
                prev_blue_kp = blue_kp

            current_fight_state, grappling_frames, striking_frames = determine_fight_state(
                frame["detections"],
                grappling_frames,
                striking_frames,
                current_fight_state,
                MIN_GRAPPLING_THRESHOLD,
                DISTANCE_GRAPPLING_THRESHOLD,
            )

            if current_fight_state == FightState.GRAPPLING:
                frames_spent_grappling += 1

            if previous_fight_state != current_fight_state:
                description = f"Fight state changed to {current_fight_state}"

                if current_fight_state == FightState.GRAPPLING:
                    initiator = determine_takedown_initiator(hip_history)
                    if initiator:
                        description += f", takedown initiated by {initiator}"

                _insert_event(db, frame_number, description, fight_id)
                print(description + f" at frame {frame_number}")
                previous_fight_state = current_fight_state

        # Flush remaining fighter_frames
        if frame_batch:
            _flush_frame_batch(db, frame_batch)

        print(f"Frames spent grappling: {frames_spent_grappling}")

        # ------------------------------------------------------------------
        # Single commit — all rows land atomically
        # ------------------------------------------------------------------
        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
