import json
import numpy as np
from collections import deque
from typing import Optional

from sqlalchemy import text
from database import SessionLocal

from action_model import inference as strike_model
from fight_processing.fight_processing_util import (
    determine_fight_state,
    determine_takedown_initiator,
    get_fighter_scale,
    get_head_center,
    get_hip_height,
    frame_usable,
    make_keypoint_smoother,
)

from models.FightState import FightState, GRAPPLING_STATES
from models.constants import (
    TAKEDOWN_LOOKBACK_SECS,
    RECOIL_LOOKAHEAD_SECS,
    RECOIL_VELOCITY_RATIO,
)

_FRAME_BATCH_SIZE = 1_000


def _insert_event(
    db,
    frame: int,
    description: Optional[str],
    fight_id: int,
    action: Optional[str] = None,
    fighter_id: Optional[int] = None,
    success: Optional[bool] = None,
    state: Optional[str] = None,
) -> None:
    """`description` is always None from every call site in this module.

    The pipeline can never emit `fight_end` (manual-labelling only), and it's
    the only action the `ck_fight_events_point_has_description` CHECK still
    requires a description for — every prediction is fully reconstructable
    client-side from `action`/`fighter_id`/`success`/`state` plus the `rounds`
    table (for round markers), so nothing here needs the frozen text. The
    parameter stays (rather than being dropped) so a future call site that
    genuinely can't be reconstructed still has somewhere to put one.
    """
    db.execute(
        text(
            "INSERT INTO fight_events "
            "(frame, description, fight_id, action, fighter_id, success, state, source, kind) "
            "VALUES (:frame, :description, :fight_id, :action, :fighter_id, :success, :state, "
            "'prediction', 'point')"
        ),
        {
            "frame": frame,
            "description": description,
            "fight_id": fight_id,
            "action": action,
            "fighter_id": fighter_id,
            "success": success,
            "state": state,
        },
    )


_PUNCH_FAMILIES = ("jab", "cross", "hook", "uppercut")
_KICK_ACTIONS = {"head": "head_kick", "body": "middle_kick", "leg": "low_kick"}

# Loaded on first use and reused for every fight in a batch run.
_strike_net = None


def _strike_action(family: str, target: str, state: FightState) -> str:
    """Model output -> the pipeline's `fight_events.action` vocabulary
    (eval/schema.py PIPELINE_ACTION_MAP), which the frontend and eval read.

    Punches thrown in CLINCH/GROUND keep the non-specific clinch_punch /
    ground_punch actions: no QA-verified label has ever been a grappling
    punch, so a family the model claims there is untrained guesswork."""
    if family in _PUNCH_FAMILIES:
        if state == FightState.CLINCH:
            return "clinch_punch"
        if state == FightState.GROUND:
            return "ground_punch"
        return f"{family}_{'head' if target == 'head' else 'body'}"
    if family == "kick":
        return _KICK_ACTIONS[target]
    return "ground_knee" if state == FightState.GROUND else "clinch_knee"


def _scan_spans(rounds, excluded_ranges) -> list[tuple[int, int]]:
    """Round frame ranges with every excluded (replay) range cut out."""
    spans = []
    for start, end in sorted(rounds or []):
        cursor = start
        for ex_start, ex_end in sorted(excluded_ranges or []):
            if ex_end < cursor or ex_start > end:
                continue
            if ex_start > cursor:
                spans.append((cursor, ex_start - 1))
            cursor = max(cursor, ex_end + 1)
        if cursor <= end:
            spans.append((cursor, end))
    return spans


def _landed(contact_frame: int, defender: str, heads: dict, fps: int) -> Optional[bool]:
    """Head-recoil proxy for landed vs missed: did the defender's head move
    faster than RECOIL_VELOCITY_RATIO x their scale over the
    RECOIL_LOOKAHEAD_SECS after contact? None when the defender's head isn't
    readable at contact or at any later frame (unconfirmed)."""
    lookahead = max(1, round(fps * RECOIL_LOOKAHEAD_SECS))
    at_contact = heads.get(contact_frame)
    if at_contact is None or at_contact[defender][1] is None:
        return None
    head0, scale = at_contact[defender]
    later = next((f for f in range(contact_frame + lookahead, contact_frame + 4 * lookahead + 1)
                  if f in heads), None)
    if later is None:
        return None
    head_speed = (np.linalg.norm(heads[later][defender][0] - head0) / lookahead) * fps
    return bool(head_speed >= RECOIL_VELOCITY_RATIO * scale)


def _flush_frame_batch(db, batch: list[dict]) -> None:
    """Bulk-insert fighter_frames rows and flush (without committing)."""
    db.execute(
        text(
            "INSERT INTO fighter_frames "
            "(fight_id, frame, corner, x1, y1, x2, y2, confidence, keypoints) "
            "VALUES (:fight_id, :frame, :corner, :x1, :y1, :x2, :y2, :confidence, "
            "CAST(:keypoints AS JSONB))"
        ),
        batch,
    )
    db.flush()   # release memory; does NOT end the transaction


def write_frames_and_rounds(
    pose_data: dict,
    fight_id: int,
    fps: int,
    rounds: Optional[list[tuple[int, int]]] = None,
) -> None:
    """
    Lightweight counterpart to process_fight() for manually-labeled fights.

    Writes fighter_frames (boxes + keypoints) and rounds only — skips the
    strike/fight-state detection state machine entirely, since the user tags
    those by hand on the Annotate screen instead. Still writes round_start/
    round_end fight_events from the real segmentation boundaries (description
    NULL — the round number is reconstructed client-side from `rounds`),
    since round detection isn't part of what's being manually replaced.

    Same idempotent delete-then-insert-then-commit shape as process_fight().
    """
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM fight_events   WHERE fight_id = :fid AND source = 'prediction'"), {"fid": fight_id})
        db.execute(text("DELETE FROM fighter_frames WHERE fight_id = :fid"), {"fid": fight_id})
        db.execute(text("DELETE FROM rounds         WHERE fight_id = :fid"), {"fid": fight_id})

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

        frame_batch: list[dict] = []

        for index, frame in enumerate(pose_data["frames"]):
            frame_number = index + 1

            if frame_number in round_starts:
                description = f"Round {round_starts[frame_number]} started"
                _insert_event(db, frame_number, None, fight_id, action="round_start")
                print(description + f" at frame {frame_number}")

            if frame_number in round_ends:
                description = f"Round {round_ends[frame_number]} ended"
                _insert_event(db, frame_number, None, fight_id, action="round_end")
                print(description + f" at frame {frame_number}")

            for d in frame["detections"]:
                if d["class_id"] in (0, 1):
                    bbox = d.get("bbox_xyxy") or []
                    if len(bbox) == 4:
                        raw_kp = d.get("keypoints")
                        frame_batch.append({
                            "fight_id":   fight_id,
                            "frame":      frame_number,
                            "corner":     d["class_id"],
                            "x1": float(bbox[0]), "y1": float(bbox[1]),
                            "x2": float(bbox[2]), "y2": float(bbox[3]),
                            "confidence": d.get("confidence"),
                            "keypoints":  json.dumps(raw_kp),
                        })

            if len(frame_batch) >= _FRAME_BATCH_SIZE:
                _flush_frame_batch(db, frame_batch)
                frame_batch.clear()

        if frame_batch:
            _flush_frame_batch(db, frame_batch)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_fight(
    pose_data: dict,
    fight_id: int,
    fps: int,
    rounds: Optional[list[tuple[int, int]]] = None,
    excluded_ranges: Optional[list[tuple[int, int]]] = None,
    red_fighter_id: Optional[int] = None,
    blue_fighter_id: Optional[int] = None,
) -> None:
    """
    Run the fight state machine and the strike model, and persist all events,
    rounds, and fighter bounding boxes to the database.

    Everything is written inside a single transaction so either every row for
    the fight lands or none does.  Existing rows for `fight_id` are deleted
    first, making repeated calls idempotent.

    The state='completed' transition is the caller's responsibility
    (run_pipeline for single-file mode, run_batch for batch mode).

    Args:
        pose_data:  In-memory corner-assigned dict from assign_corners()
                    (or loaded from a --pose-results dev override).
        fight_id:   Primary key of the fights row for this video.
        fps:        Frames per second of the source video (from fights row).
        rounds:     List of (start_frame, end_frame) tuples from segment_fights().
        excluded_ranges: List of (start_frame, end_frame) tuples — mid-round
                    replays detected from the scoreboard timer jumping
                    backward (segment_fights()'s detect_replay_ranges()).
                    Strike/state detection is skipped inside these ranges,
                    same as outside every round — see plan Stage 1 step 3.
        red_fighter_id:  fighters.id assigned to the red corner (or None).
        blue_fighter_id: fighters.id assigned to the blue corner (or None).
    """
    global _strike_net
    if _strike_net is None:
        _strike_net = strike_model.load_model()

    db = SessionLocal()

    def _fighter_id_for(label: Optional[str]) -> Optional[int]:
        """Map an appearance corner label to the assigned fighters.id.

        ``red_fighter_id`` / ``blue_fighter_id`` come from the fights row
        (corner assignment done in the UI). Either may be ``None`` when corners
        have not been assigned yet, in which case the event's ``fighter_id`` is
        written as NULL.
        """
        if label == "fighter_red":
            return red_fighter_id
        if label == "fighter_blue":
            return blue_fighter_id
        return None

    try:
        # ------------------------------------------------------------------
        # Delete existing rows for this fight (idempotent re-processing)
        # ------------------------------------------------------------------
        db.execute(text("DELETE FROM fight_events  WHERE fight_id = :fid AND source = 'prediction'"), {"fid": fight_id})
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

        # State and strikes are only read inside rounds and outside mid-round
        # replays (plan Stage 1 step 3): walkouts, rest periods, the
        # post-fight wrapper and slow-motion replays are where most spurious
        # events used to come from.
        scan_spans = _scan_spans(rounds, excluded_ranges)
        _span_idx = 0

        # ------------------------------------------------------------------
        # State machine + fighter_frames collection
        # ------------------------------------------------------------------
        current_fight_state  = FightState.STRIKING
        previous_fight_state = FightState.STRIKING
        state_counters: dict = {}
        frames_spent_grappling = 0
        frames_spent_ground    = 0

        # Per-frame context the strike pass needs after the loop: the fight
        # state in effect at each scanned frame (picks clinch_/ground_
        # actions) and each fighter's head + scale on usable frames (recoil).
        state_at: dict[int, FightState] = {}
        heads: dict[int, dict] = {}

        hip_history = deque(maxlen=max(1, round(fps * TAKEDOWN_LOOKBACK_SECS)))
        smooth_red  = make_keypoint_smoother()
        smooth_blue = make_keypoint_smoother()

        frame_batch: list[dict] = []

        for index, frame in enumerate(pose_data["frames"]):
            frame_number = index + 1

            if frame_number in round_starts:
                description = f"Round {round_starts[frame_number]} started"
                _insert_event(db, frame_number, None, fight_id, action="round_start")
                print(description + f" at frame {frame_number}")

            if frame_number in round_ends:
                description = f"Round {round_ends[frame_number]} ended"
                _insert_event(db, frame_number, None, fight_id, action="round_end")
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
                            "corner":     d["class_id"],
                            "x1": float(bbox[0]), "y1": float(bbox[1]),
                            "x2": float(bbox[2]), "y2": float(bbox[3]),
                            "confidence": d.get("confidence"),
                            "keypoints":  json.dumps(raw_kp),  # [[x,y]*17] or null
                        })

            if len(frame_batch) >= _FRAME_BATCH_SIZE:
                _flush_frame_batch(db, frame_batch)
                frame_batch.clear()

            # fighter_frames above are written for the whole video (the
            # frontend overlay needs them); everything below is scanned
            # frames only.
            while _span_idx < len(scan_spans) and frame_number > scan_spans[_span_idx][1]:
                _span_idx += 1
            if not (_span_idx < len(scan_spans) and scan_spans[_span_idx][0] <= frame_number):
                continue

            state_at[frame_number] = current_fight_state

            if not frame_usable(frame["detections"], current_fight_state):
                if current_fight_state in GRAPPLING_STATES:
                    frames_spent_grappling += 1
                if current_fight_state == FightState.GROUND:
                    frames_spent_ground += 1
                continue

            red_kp = blue_kp = None
            for d in frame["detections"]:
                if d["class_id"] == 0:
                    red_kp = smooth_red(d["keypoints"], frame_number)
                elif d["class_id"] == 1:
                    blue_kp = smooth_blue(d["keypoints"], frame_number)

            red_scale, blue_scale = get_fighter_scale(red_kp), get_fighter_scale(blue_kp)
            heads[frame_number] = {
                "red":  (get_head_center(red_kp), red_scale),
                "blue": (get_head_center(blue_kp), blue_scale),
            }
            hip_history.append({
                "red":  get_hip_height(red_kp),
                "blue": get_hip_height(blue_kp),
                "red_scale":  red_scale,
                "blue_scale": blue_scale,
            })

            current_fight_state, state_counters = determine_fight_state(
                frame["detections"],
                state_counters,
                current_fight_state,
                fps,
            )

            if current_fight_state in GRAPPLING_STATES:
                frames_spent_grappling += 1
            if current_fight_state == FightState.GROUND:
                frames_spent_ground += 1

            if previous_fight_state != current_fight_state:
                description = f"Fight state changed to {current_fight_state}"

                # Attribute the engagement to a fighter. The fight hitting the
                # floor (entering GROUND) is a takedown; locking up while still
                # standing (entering CLINCH) is a clinch.
                initiator = determine_takedown_initiator(hip_history)
                action: Optional[str] = None
                if current_fight_state == FightState.GROUND and initiator:
                    description += f", takedown initiated by {initiator}"
                    action = "takedown_initiated"
                elif current_fight_state == FightState.CLINCH and initiator:
                    description += f", clinch initiated by {initiator}"
                    action = "clinch_initiated"

                _insert_event(db, frame_number, None, fight_id,
                              action=action, fighter_id=_fighter_id_for(initiator),
                              state=current_fight_state.name)
                print(description + f" at frame {frame_number}")
                previous_fight_state = current_fight_state

        if frame_batch:
            _flush_frame_batch(db, frame_batch)

        # ------------------------------------------------------------------
        # Strikes — the action model scans every span for both fighters.
        # Grappling strikes carry no landed/missed (no recoil to read in a
        # tangle); open-range strikes get the head-recoil proxy.
        # ------------------------------------------------------------------
        tracks = strike_model.tracks_from_pose_data(pose_data)
        for strike in strike_model.detect_strikes(tracks, fps, scan_spans, _strike_net):
            state = state_at.get(strike.frame, FightState.STRIKING)
            action = _strike_action(strike.family, strike.target, state)
            attacker = "fighter_red" if strike.corner == 0 else "fighter_blue"
            defender = "blue" if strike.corner == 0 else "red"
            landed = None if state in GRAPPLING_STATES else _landed(strike.frame, defender, heads, fps)
            _insert_event(db, strike.frame, None, fight_id,
                          action=action, fighter_id=_fighter_id_for(attacker), success=landed)
            outcome = {True: " (landed)", False: " (missed)", None: " (unconfirmed)"}[landed]
            print(f"{attacker} threw a {action}{outcome if state not in GRAPPLING_STATES else ''} "
                  f"at frame {strike.frame} (p={strike.prob:.2f})")

        print(f"Frames spent grappling: {frames_spent_grappling} "
              f"(of which on the ground: {frames_spent_ground})")

        # ------------------------------------------------------------------
        # Single commit — all rows land atomically
        # ------------------------------------------------------------------
        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
