import json
import numpy as np
from collections import deque
from typing import Optional

from sqlalchemy import text
from database import SessionLocal

from fight_processing.fight_processing_util import (
    detect_strikes,
    determine_fight_state,
    determine_takedown_initiator,
    get_fighter_scale,
    get_head_center,
    get_hip_height,
    is_frame_valid,
    frame_validity,
    make_keypoint_smoother,
)

from models.FightState import FightState, GRAPPLING_STATES
from models.constants import (
    TAKEDOWN_LOOKBACK_SECS,
    RECOIL_LOOKAHEAD_SECS,
    RECOIL_VELOCITY_RATIO,
    HEAD_CONTACT_RATIO,
    TORSO_CONTACT_RATIO,
    PUNCH_VELOCITY_RATIO,
)

_FRAME_BATCH_SIZE = 1_000


def _insert_event(
    db,
    frame: int,
    description: str,
    fight_id: int,
    action: Optional[str] = None,
    fighter_id: Optional[int] = None,
    success: Optional[bool] = None,
    state: Optional[str] = None,
) -> None:
    db.execute(
        text(
            "INSERT INTO fight_events "
            "(frame, description, fight_id, action, fighter_id, success, state) "
            "VALUES (:frame, :description, :fight_id, :action, :fighter_id, :success, :state)"
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


def _percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile (q in 0..100) of a non-empty list."""
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((q / 100.0) * (len(s) - 1)))))
    return s[k]


def _print_standing_punch_diag(validity_counts, striking_eval_frames, diag,
                               invalid_breakdown=None, missing_detcount=None,
                               striking_both_visible=None) -> None:
    """Temporary diagnostic: explains why standing punches are/aren't firing.

    A standing punch must clear: (1) a FULL-validity frame, (2) angle+velocity,
    (3) the contact-proximity gate. `diag` holds every candidate that already
    cleared (1) and (2); `hit` records whether (3) accepted it. If many candidates
    exist but few `hit`, the contact gate is the bottleneck — and the distance
    distribution tells us how far the threshold would need to move.
    """
    total = sum(validity_counts.values())
    print("\n--- Standing-punch diagnostics ---")
    print(f"Frame validity: FULL={validity_counts['FULL']} "
          f"PARTIAL={validity_counts['PARTIAL']} "
          f"INVALID={validity_counts['INVALID']} (total {total})")
    if invalid_breakdown:
        print(f"INVALID breakdown: both_present_low_joints="
              f"{invalid_breakdown['both_present_low_joints']} "
              f"missing_red={invalid_breakdown['missing_red']} "
              f"missing_blue={invalid_breakdown['missing_blue']} "
              f"missing_both={invalid_breakdown['missing_both']}")
    if missing_detcount:
        print(f"  missing-fighter frames by raw detection count: "
              f"two_dets(label collision)={missing_detcount['two_dets']} "
              f"one_det={missing_detcount['one_det']} "
              f"zero_dets={missing_detcount['zero_dets']}")
    if striking_both_visible:
        sbv_full    = striking_both_visible["full"]
        sbv_partial = striking_both_visible["partial"]
        sbv_invalid = striking_both_visible["invalid"]
        sbv_tot     = sbv_full + sbv_partial + sbv_invalid
        print(f"STRIKING + both fighters visible: {sbv_tot} frames "
              f"(FULL={sbv_full}, PARTIAL/relaxed-bar={sbv_partial}, "
              f"INVALID/dropped={sbv_invalid})")
        if sbv_tot:
            ran = sbv_full + sbv_partial
            print(f"  => {ran/sbv_tot:.0%} of both-visible standing frames run "
                  f"detect_strikes (FULL or PARTIAL); "
                  f"{sbv_invalid/sbv_tot:.0%} are genuinely dropped.")
    print(f"STRIKING frames evaluated by detect_strikes: {striking_eval_frames}")

    extended   = (diag or {}).get("extended", [])
    candidates = (diag or {}).get("candidates", [])

    # Velocity distribution of all arm extensions (angle ok) — where to set the
    # PUNCH_VELOCITY_RATIO threshold relative to real punch motions.
    if extended:
        print(f"Arm extensions (angle ok): {len(extended)}; "
              f"scale/sec speed p50/p75/p90/p95 = "
              f"{_percentile(extended, 50):.2f} / {_percentile(extended, 75):.2f} "
              f"/ {_percentile(extended, 90):.2f} / {_percentile(extended, 95):.2f} "
              f"(PUNCH_VELOCITY_RATIO threshold = {PUNCH_VELOCITY_RATIO})")

    if not candidates:
        print("Standing punch candidates (passed angle+velocity): 0")
        print("=> Nothing cleared the velocity gate. Compare the arm-extension speed "
              "percentiles above against PUNCH_VELOCITY_RATIO — if real punches sit "
              "below it, lower the threshold.")
        print("--- end diagnostics ---\n")
        return

    hits   = [d for d in candidates if d["hit"]]
    misses = [d for d in candidates if not d["hit"]]
    print(f"Standing punch candidates (passed angle+velocity): {len(candidates)} "
          f"-> contact gate accepted {len(hits)}, rejected {len(misses)}")
    print(f"Contact thresholds: HEAD_CONTACT_RATIO={HEAD_CONTACT_RATIO} "
          f"TORSO_CONTACT_RATIO={TORSO_CONTACT_RATIO}")

    if misses:
        head_d  = [d["head"] for d in misses]
        torso_d = [d["torso"] for d in misses]
        print("Rejected candidates' normalised contact distance "
              "(min / p25 / median):")
        print(f"  head : {min(head_d):.2f} / {_percentile(head_d, 25):.2f} "
              f"/ {_percentile(head_d, 50):.2f}")
        print(f"  torso: {min(torso_d):.2f} / {_percentile(torso_d, 25):.2f} "
              f"/ {_percentile(torso_d, 50):.2f}")
        print("=> If these medians sit just above the thresholds, the contact gate "
              "is the bottleneck and loosening the ratios (or a windowed check) "
              "would recover these punches.")
    print("--- end diagnostics ---\n")


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
    those by hand on the Annotate screen instead. Still writes "Round N
    started/ended" fight_events from the real segmentation boundaries, since
    round detection isn't part of what's being manually replaced.

    Same idempotent delete-then-insert-then-commit shape as process_fight().
    """
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM fight_events   WHERE fight_id = :fid"), {"fid": fight_id})
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
                _insert_event(db, frame_number, description, fight_id, action="round_start")
                print(description + f" at frame {frame_number}")

            if frame_number in round_ends:
                description = f"Round {round_ends[frame_number]} ended"
                _insert_event(db, frame_number, description, fight_id, action="round_end")
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
    Run the fight state machine and persist all events, rounds, and fighter
    bounding boxes to the database.

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

        # Sorted round bounds for the in-round gate below (plan Stage 1 step
        # 3) — replays, walkouts and the post-fight broadcast wrapper are not
        # inside any round, and running strike/state detection over them is
        # where most spurious events came from (80% of strikes fell outside
        # every detected round). `_round_idx` only ever advances, so the
        # membership check below is a single O(n) pass over the frame loop.
        _round_bounds = sorted(rounds) if rounds else []
        _round_idx = 0

        # Same pattern for mid-round replays (plan Stage 1 step 3, second
        # half): a replay is inside a round's frame range but its footage is
        # slow-motion, so velocity-based strike detection is meaningless
        # there. `_excl_idx` only ever advances alongside frame_number.
        _excl_bounds = sorted(excluded_ranges) if excluded_ranges else []
        _excl_idx = 0

        # ------------------------------------------------------------------
        # State machine + fighter_frames collection
        # ------------------------------------------------------------------
        current_fight_state  = FightState.STRIKING
        previous_fight_state = FightState.STRIKING

        state_counters: dict = {}
        frames_spent_grappling = 0
        frames_spent_ground    = 0

        # --- Standing-punch diagnostics (temporary) ---
        # validity_counts: how many frames hit each validity grade.
        # striking_eval_frames: STRIKING frames that actually reached detect_strikes
        #   (both fighters present, prev frame available) — the only frames a
        #   standing punch can fire in.
        # standing_punch_diag: per-candidate contact records from detect_strikes.
        validity_counts      = {"FULL": 0, "PARTIAL": 0, "INVALID": 0}
        striking_eval_frames = 0
        # "extended": speed of every standing arm extension (angle ok), for tuning
        # the velocity threshold. "candidates": post-velocity-gate contact records.
        standing_punch_diag: dict = {"extended": [], "candidates": []}
        # INVALID breakdown: which frames lacked a fighter vs had both but too
        # few confident joints. Distinguishes an upstream detection/labelling
        # gap from the validity bar being too strict.
        invalid_breakdown = {"missing_red": 0, "missing_blue": 0,
                             "missing_both": 0, "both_present_low_joints": 0}
        # When a fighter is "missing", how many fighter-class (0/1) detections did
        # the frame actually carry? 2 detections but a corner missing => corner
        # assignment collapsed both onto one label (labelling bug). 0-1 detections
        # => the detector/tracker genuinely produced fewer than two fighters.
        missing_detcount = {"two_dets": 0, "one_det": 0, "zero_dets": 0}
        # The cohort you actually care about: STRIKING state with BOTH fighters
        # visible. "full" = passed the strict all-15-joints bar; "partial" =
        # missed that bar but still cleared the relaxed STRIKING_CORE bar, so
        # detect_strikes still ran; "invalid" = below even the relaxed bar,
        # genuinely dropped.
        striking_both_visible = {"full": 0, "partial": 0, "invalid": 0}

        hip_history  = deque(maxlen=max(1, round(fps * TAKEDOWN_LOOKBACK_SECS)))
        recoil_lookahead_frames = max(1, round(fps * RECOIL_LOOKAHEAD_SECS))
        prev_red_kp, prev_blue_kp = None, None

        smooth_red  = make_keypoint_smoother()
        smooth_blue = make_keypoint_smoother()

        # Pending strikes waiting for recoil confirmation.
        # Each entry: {"emit_at": frame, "description": str, "defender": "red"|"blue",
        #              "head_at_contact": np.array, "def_scale": float}
        # Clinch strikes are emitted immediately (no recoil expected).
        pending_strikes: list[dict] = []

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
                _insert_event(db, frame_number, description, fight_id, action="round_start")
                print(description + f" at frame {frame_number}")

            if frame_number in round_ends:
                description = f"Round {round_ends[frame_number]} ended"
                _insert_event(db, frame_number, description, fight_id, action="round_end")
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

            # Strike/state detection only runs inside a detected round —
            # replays, walkouts, between-round rest and the post-fight
            # broadcast wrapper are not training data and should not produce
            # events. fighter_frames above are written for the whole video
            # regardless (the frontend overlay needs them).
            while _round_idx < len(_round_bounds) and frame_number > _round_bounds[_round_idx][1]:
                _round_idx += 1
            in_round = (_round_idx < len(_round_bounds) and
                        _round_bounds[_round_idx][0] <= frame_number <= _round_bounds[_round_idx][1])
            if not in_round:
                continue

            # Mid-round replay exclusion (plan Stage 1 step 3, second half) —
            # same skip as the round gate above, but for a slow-motion replay
            # shown inside a round's frame range rather than outside it.
            while _excl_idx < len(_excl_bounds) and frame_number > _excl_bounds[_excl_idx][1]:
                _excl_idx += 1
            in_replay = (_excl_idx < len(_excl_bounds) and
                         _excl_bounds[_excl_idx][0] <= frame_number <= _excl_bounds[_excl_idx][1])
            if in_replay:
                continue

            validity = frame_validity(frame["detections"], current_fight_state)
            validity_counts[validity] += 1

            _has_red  = any(d.get("class_id") == 0 for d in frame["detections"])
            _has_blue = any(d.get("class_id") == 1 for d in frame["detections"])
            if (current_fight_state == FightState.STRIKING and _has_red and _has_blue):
                if validity == "FULL":
                    striking_both_visible["full"] += 1
                elif validity == "PARTIAL":
                    # Still runs detect_strikes via the relaxed core-joint bar
                    # (STRIKING_CORE_KEYPOINT_INDICES) — not dropped.
                    striking_both_visible["partial"] += 1
                else:
                    striking_both_visible["invalid"] += 1

            if validity == "INVALID":
                if _has_red and _has_blue:
                    invalid_breakdown["both_present_low_joints"] += 1
                else:
                    if _has_red:
                        invalid_breakdown["missing_blue"] += 1
                    elif _has_blue:
                        invalid_breakdown["missing_red"] += 1
                    else:
                        invalid_breakdown["missing_both"] += 1
                    # How many fighter-class detections did this frame actually carry?
                    _ndet = sum(1 for d in frame["detections"]
                                if d.get("class_id") in (0, 1))
                    if _ndet >= 2:
                        missing_detcount["two_dets"] += 1
                    elif _ndet == 1:
                        missing_detcount["one_det"] += 1
                    else:
                        missing_detcount["zero_dets"] += 1

                if current_fight_state in GRAPPLING_STATES:
                    frames_spent_grappling += 1
                if current_fight_state == FightState.GROUND:
                    frames_spent_ground += 1
                continue

            red_kp, blue_kp = None, None
            for d in frame["detections"]:
                if d["class_id"] == 0:
                    red_kp = smooth_red(d["keypoints"], frame_number)
                elif d["class_id"] == 1:
                    blue_kp = smooth_blue(d["keypoints"], frame_number)

            if red_kp and blue_kp:
                red_head  = get_head_center(red_kp)
                blue_head = get_head_center(blue_kp)

                hip_history.append({
                    "red":  get_hip_height(red_kp),
                    "blue": get_hip_height(blue_kp),
                    "red_scale":  get_fighter_scale(red_kp),
                    "blue_scale": get_fighter_scale(blue_kp),
                })

                # Resolve pending strikes that have now accumulated enough lookahead.
                still_pending = []
                for ps in pending_strikes:
                    if frame_number < ps["emit_at"]:
                        still_pending.append(ps)
                        continue
                    # Check head recoil of the defender over the lookahead window.
                    cur_head = red_head if ps["defender"] == "red" else blue_head
                    head_disp = np.linalg.norm(cur_head - ps["head_at_contact"])
                    head_speed = (head_disp / recoil_lookahead_frames) * fps
                    landed = head_speed >= (RECOIL_VELOCITY_RATIO * ps["def_scale"])
                    desc = ps["description"] + (" (landed)" if landed else " (missed)")
                    _insert_event(db, ps["contact_frame"], desc, fight_id,
                                  action=ps["action"], fighter_id=ps["fighter_id"],
                                  success=bool(landed))
                    print(desc + f" at frame {ps['contact_frame']}")
                pending_strikes = still_pending

                is_grappling = current_fight_state in GRAPPLING_STATES
                is_ground    = current_fight_state == FightState.GROUND

                if prev_red_kp is not None and prev_blue_kp is not None:
                    if not is_grappling:
                        striking_eval_frames += 1
                    for strike in detect_strikes(
                        red_kp, blue_kp, prev_red_kp, prev_blue_kp, strike_state, fps,
                        frame_idx=frame_number,
                        grappling=is_grappling, ground=is_ground,
                        diag=None if is_grappling else standing_punch_diag,
                    ):
                        description = f"{strike['fighter']} threw a {strike['type']}"
                        attacker_id = _fighter_id_for(strike["fighter"])
                        if is_grappling:
                            # Clinch/ground strikes emitted immediately — no recoil,
                            # so landed/missed is unknown (success=None).
                            _insert_event(db, frame_number, description, fight_id,
                                          action=strike["type"], fighter_id=attacker_id)
                            print(description + f" at frame {frame_number}")
                        else:
                            defender_key = "red" if strike["defender"] == "fighter_red" else "blue"
                            def_kp = red_kp if defender_key == "red" else blue_kp
                            pending_strikes.append({
                                "contact_frame":   frame_number,
                                "emit_at":         frame_number + recoil_lookahead_frames,
                                "description":     description,
                                "action":          strike["type"],
                                "fighter_id":      attacker_id,
                                "defender":        defender_key,
                                "head_at_contact": red_head if defender_key == "red" else blue_head,
                                "def_scale":       get_fighter_scale(def_kp),
                            })

                prev_red_kp   = red_kp
                prev_blue_kp  = blue_kp

                # PARTIAL frames count toward grappling totals; full detect_strikes
                # already ran above (grappling=True suppresses the contact gate so
                # occluded joints are handled by the per-limb confidence check).
                if validity == "PARTIAL":
                    if current_fight_state in GRAPPLING_STATES:
                        frames_spent_grappling += 1
                    if current_fight_state == FightState.GROUND:
                        frames_spent_ground += 1

            current_fight_state, state_counters = determine_fight_state(
                frame["detections"],
                state_counters,
                current_fight_state,
                fps,
            )

            # Only FULL frames count here; PARTIAL frames already incremented
            # inside the `if red_kp and blue_kp:` block above.
            if validity == "FULL":
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

                _insert_event(db, frame_number, description, fight_id,
                              action=action, fighter_id=_fighter_id_for(initiator),
                              state=current_fight_state.name)
                print(description + f" at frame {frame_number}")
                previous_fight_state = current_fight_state

        # Flush remaining fighter_frames
        if frame_batch:
            _flush_frame_batch(db, frame_batch)

        # Flush any strikes still pending at end of video — emit without recoil confirmation.
        for ps in pending_strikes:
            desc = ps["description"] + " (unconfirmed)"
            # Recoil never confirmed — success unknown (None).
            _insert_event(db, ps["contact_frame"], desc, fight_id,
                          action=ps["action"], fighter_id=ps["fighter_id"])
            print(desc + f" at frame {ps['contact_frame']}")

        print(f"Frames spent grappling: {frames_spent_grappling} "
              f"(of which on the ground: {frames_spent_ground})")

        _print_standing_punch_diag(
            validity_counts, striking_eval_frames, standing_punch_diag,
            invalid_breakdown, missing_detcount, striking_both_visible,
        )

        # ------------------------------------------------------------------
        # Single commit — all rows land atomically
        # ------------------------------------------------------------------
        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
