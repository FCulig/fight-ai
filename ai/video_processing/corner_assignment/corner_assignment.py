"""
Per-frame appearance-anchored corner assignment.

Strategy (appearance path):
  Pass 1 — read video sequentially; per fighter detection build a descriptor
  (glove-tape net_red/tape_total + torso HSV hue histogram).  Cache all
  descriptors in memory.  Identify "clean frames" (fighters well-separated,
  both well-posed, sufficient tape visible) and bootstrap per-corner templates
  from those frames.

  If the two templates are too similar (separation < CORNER_TEMPLATE_MIN_SEPARATION),
  the colors cannot be reliably distinguished and we fall back to the legacy global
  tape-vote / model-class-vote path (no regression).

  Pass 2 — iterate over the cached descriptors; assign each detection to a
  template using normalized tape + histogram distance, with hysteresis to absorb
  single-frame noise and a consecutive-frame confirmation gate before committing
  a label flip.

Legacy fallback:
  Preserves the original "aggregate over whole fight → one static corner_map"
  logic exactly, guaranteeing no regression on footage with similar glove colors.
"""

import copy

import cv2
import numpy as np

from models.constants import (
    TAPE_PATCH_HALF,
    WRIST_EDGE_MARGIN,
    TAPE_MIN_SATURATION,
    TAPE_MIN_VALUE,
    RED_HUE_HIGH1,
    RED_HUE_LOW2,
    BLUE_HUE_LOW,
    BLUE_HUE_HIGH,
    CORNER_MIN_TAPE_SAMPLES,
    KEYPOINT_MIN_CONFIDENCE,
    STRIKE_KEYPOINT_INDICES,
    DISTANCE_GRAPPLING_THRESHOLD,
    TORSO_HIST_BINS,
    TORSO_MIN_SATURATION,
    TORSO_MIN_VALUE,
    TORSO_SAMPLE_MIN_PIXELS,
    CORNER_CLEAN_FRAME_MIN_TAPE,
    CORNER_TEMPLATE_MIN_SEPARATION,
    CORNER_TAPE_WEIGHT,
    CORNER_HIST_WEIGHT,
    CORNER_HYSTERESIS_WEIGHT,
    CORNER_SWAP_CONFIRM_FRAMES,
)
from models.geometry import (
    get_fighter_scale,
    get_torso_rectangle,
    calculate_distance_between_fighters,
)

# COCO keypoint index pairs: (wrist, elbow) for left and right arms
_WRIST_PAIRS = [(9, 7), (10, 8)]


# ---------------------------------------------------------------------------
# Tape sampling (unchanged from original)
# ---------------------------------------------------------------------------

def _patch_half(kp: list, wrist_idx: int, elbow_idx: int) -> int:
    """Scale crop half-side by forearm length when elbow is visible."""
    wx, wy = kp[wrist_idx][0], kp[wrist_idx][1]
    ex, ey = kp[elbow_idx][0], kp[elbow_idx][1]
    if ex == 0 and ey == 0:
        return TAPE_PATCH_HALF
    forearm = ((wx - ex) ** 2 + (wy - ey) ** 2) ** 0.5
    scaled = int(forearm * 0.35)
    return max(TAPE_PATCH_HALF // 2, min(TAPE_PATCH_HALF * 2, scaled))


def _sample_tape(frame_bgr: np.ndarray, kp: list, h: int, w: int) -> tuple[int, int]:
    """Count red and blue HSV pixels around both wrists.
    Returns (red_pixels, blue_pixels)."""
    red_total  = 0
    blue_total = 0

    for wrist_idx, elbow_idx in _WRIST_PAIRS:
        wx, wy = kp[wrist_idx][0], kp[wrist_idx][1]

        if wx == 0 and wy == 0:
            continue
        if (wx < WRIST_EDGE_MARGIN or wx > w - WRIST_EDGE_MARGIN or
                wy < WRIST_EDGE_MARGIN or wy > h - WRIST_EDGE_MARGIN):
            continue

        half = _patch_half(kp, wrist_idx, elbow_idx)
        x1 = max(0, int(wx) - half)
        y1 = max(0, int(wy) - half)
        x2 = min(w, int(wx) + half)
        y2 = min(h, int(wy) + half)

        if x2 <= x1 or y2 <= y1:
            continue

        patch = frame_bgr[y1:y2, x1:x2]
        if patch.size == 0:
            continue

        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0]
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]

        quality   = (sat >= TAPE_MIN_SATURATION) & (val >= TAPE_MIN_VALUE)
        red_mask  = ((hue <= RED_HUE_HIGH1) | (hue >= RED_HUE_LOW2)) & quality
        blue_mask = (hue >= BLUE_HUE_LOW) & (hue <= BLUE_HUE_HIGH) & quality

        red_total  += int(red_mask.sum())
        blue_total += int(blue_mask.sum())

    return red_total, blue_total


# ---------------------------------------------------------------------------
# Torso histogram sampling
# ---------------------------------------------------------------------------

def _sample_torso_histogram(
    frame_bgr: np.ndarray, kp: list, h: int, w: int
) -> tuple[np.ndarray | None, int]:
    """Sample a normalised HSV hue histogram from the torso/shorts region.

    The region is the bounding box of shoulder/hip keypoints (COCO 5/6/11/12)
    extended downward by half a fighter scale to capture the shorts.  Pixels
    are gated on TORSO_MIN_SATURATION / TORSO_MIN_VALUE to exclude skin and
    near-black regions.

    Returns:
        (normalized_hist, pixel_count) — hist is None when the region is empty
        or below TORSO_SAMPLE_MIN_PIXELS.
    """
    if kp is None or len(kp) < 13:
        return None, 0

    indices = [5, 6, 11, 12]
    pts = np.array([kp[i][:2] for i in indices], dtype=np.float32)

    x1 = max(0, int(pts[:, 0].min()))
    y1 = max(0, int(pts[:, 1].min()))
    x2 = min(w, int(pts[:, 0].max()))
    # Extend downward by half a fighter scale to include the shorts.
    scale = get_fighter_scale(kp)
    y2 = min(h, int(pts[:, 1].max()) + int(scale * 0.5))

    if x2 <= x1 or y2 <= y1:
        return None, 0

    patch = frame_bgr[y1:y2, x1:x2]
    if patch.size == 0:
        return None, 0

    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    mask = ((sat >= TORSO_MIN_SATURATION) & (val >= TORSO_MIN_VALUE)).astype(np.uint8)
    pixel_count = int(mask.sum())

    if pixel_count < TORSO_SAMPLE_MIN_PIXELS:
        return None, pixel_count

    hue_hist = cv2.calcHist(
        [hsv], [0], mask, [TORSO_HIST_BINS], [0, 180]
    ).flatten().astype(np.float32)

    total = hue_hist.sum()
    if total > 0:
        hue_hist /= total

    return hue_hist, pixel_count


# ---------------------------------------------------------------------------
# Clean-frame check
# ---------------------------------------------------------------------------

def _is_clean_frame(
    dets: list,
    descriptors: list,  # [{track_id, net_red, tape_total, hist, hist_weight}, ...]
) -> bool:
    """A clean frame has exactly 2 detections, both with confident pose joints,
    fighters well-separated, and sufficient tape pixels."""
    if len(dets) != 2 or len(descriptors) != 2:
        return False

    for d in dets:
        kp = d.get("keypoints")
        if kp is None or len(kp) < 17:
            return False
        if not all(kp[i][2] >= KEYPOINT_MIN_CONFIDENCE for i in STRIKE_KEYPOINT_INDICES):
            return False

    for desc in descriptors:
        if desc["tape_total"] < CORNER_CLEAN_FRAME_MIN_TAPE:
            return False

    kp0 = dets[0]["keypoints"]
    kp1 = dets[1]["keypoints"]
    rect0 = get_torso_rectangle(kp0)
    rect1 = get_torso_rectangle(kp1)
    dist  = calculate_distance_between_fighters(rect0, rect1)
    if dist < DISTANCE_GRAPPLING_THRESHOLD:
        return False

    return True


# ---------------------------------------------------------------------------
# Template bootstrap
# ---------------------------------------------------------------------------

def _bootstrap_templates(
    clean_descriptors: dict[int, list],  # track_id → list of per-frame descriptors
) -> dict | None:
    """Build per-corner appearance templates from clean-frame descriptors.

    Accumulates per-slot (0/1) net-red sum and weighted-mean hue histogram.
    Assigns the red corner by net-red sign (same rule as the legacy path).

    Returns None when template separation is below CORNER_TEMPLATE_MIN_SEPARATION
    (degenerate / indistinguishable colors) → caller must use legacy fallback.
    """
    templates = {}
    for slot in (0, 1):
        descs = clean_descriptors.get(slot, [])
        if not descs:
            return None

        net_red_sum  = sum(d["net_red"] for d in descs)
        net_red_sign = 1 if net_red_sum >= 0 else -1

        # Weighted-mean hue histogram (weight = pixel count).
        hist_acc    = np.zeros(TORSO_HIST_BINS, dtype=np.float64)
        weight_sum  = 0.0
        for d in descs:
            if d["hist"] is not None and d["hist_weight"] > 0:
                hist_acc   += d["hist"].astype(np.float64) * d["hist_weight"]
                weight_sum += d["hist_weight"]

        if weight_sum > 0:
            mean_hist = (hist_acc / weight_sum).astype(np.float32)
            total = mean_hist.sum()
            if total > 0:
                mean_hist /= total
        else:
            mean_hist = None

        templates[slot] = {
            "net_red_sign": net_red_sign,
            "hist":         mean_hist,
            "hist_weight":  weight_sum,
        }

    # Slot → corner: whichever has net_red_sign == +1 is the red corner.
    slot0_sign = templates[0]["net_red_sign"]
    slot1_sign = templates[1]["net_red_sign"]
    if slot0_sign == slot1_sign:
        # Ambiguous tape; fall back.
        return None

    # Measure separation: net-red gap + histogram distance (both [0,1]).
    net_red_counts = {
        slot: sum(abs(d["net_red"]) for d in clean_descriptors[slot])
        for slot in (0, 1)
    }
    total_abs = sum(net_red_counts.values()) or 1
    net_red_gap = abs(net_red_counts[0] - net_red_counts[1]) / total_abs

    hist_dist = 0.0
    h0, h1 = templates[0]["hist"], templates[1]["hist"]
    if h0 is not None and h1 is not None:
        hist_dist = float(cv2.compareHist(h0, h1, cv2.HISTCMP_BHATTACHARYYA))

    separation = 0.5 * net_red_gap + 0.5 * hist_dist

    if separation < CORNER_TEMPLATE_MIN_SEPARATION:
        return None  # colors too similar — use legacy

    # Annotate templates with which corner (0=red, 1=blue) they represent.
    for slot in (0, 1):
        templates[slot]["corner"] = 0 if templates[slot]["net_red_sign"] == 1 else 1

    return templates, separation


# ---------------------------------------------------------------------------
# Per-frame label assignment
# ---------------------------------------------------------------------------

def _tape_distance_term(net_red: int, tape_total: int, net_red_sign: int) -> float:
    """Normalized tape distance term in [0, 1].

    0 = confident match, 1 = confident mismatch.
    Confidence factor pulls the term toward 0.5 when tape evidence is weak.
    """
    # Sign agreement: +1 if signs match, -1 if they disagree.
    det_sign = 1 if net_red >= 0 else -1
    sign_match = (det_sign == net_red_sign)

    # Confidence factor: how much to trust the tape measurement.
    confidence = min(tape_total, CORNER_CLEAN_FRAME_MIN_TAPE) / max(CORNER_CLEAN_FRAME_MIN_TAPE, 1)

    # Interpolate between neutral 0.5 and the definitive 0 (match) or 1 (mismatch).
    if sign_match:
        return 0.5 - 0.5 * confidence   # match → approaches 0
    else:
        return 0.5 + 0.5 * confidence   # mismatch → approaches 1


def _hist_distance_term(hist: np.ndarray | None, hist_weight: int,
                        template_hist: np.ndarray | None) -> float:
    """Normalized histogram distance term in [0, 1].

    Uses Bhattacharyya distance (already in [0,1]).  Down-weighted toward the
    neutral 0.5 when the detection histogram is unreliable (too few pixels).
    """
    if hist is None or template_hist is None:
        return 0.5  # no information → neutral

    bhatt = float(cv2.compareHist(hist, template_hist, cv2.HISTCMP_BHATTACHARYYA))
    bhatt = max(0.0, min(1.0, bhatt))

    weight_factor = min(hist_weight, TORSO_SAMPLE_MIN_PIXELS) / max(TORSO_SAMPLE_MIN_PIXELS, 1)
    # Interpolate between neutral 0.5 and the Bhattacharyya reading.
    return 0.5 + (bhatt - 0.5) * weight_factor


def _assign_frame_labels(
    frame_descs: list,          # list of per-detection dicts, indexed by detection order
    templates: dict,            # {slot: {corner, net_red_sign, hist, hist_weight}}
    slot_to_corner: dict,       # {track_id/slot: current corner label 0/1}
    confirm_counters: dict,     # {track_id/slot: consecutive frames pending flip}
    pending_flip: dict,         # {track_id/slot: candidate new label while confirming}
) -> dict:
    """Assign corner labels (0=red, 1=blue) to each detection for this frame.

    Uses a 2-template cost matrix (normalized tape + histogram distance) with
    hysteresis: flips are only committed after CORNER_SWAP_CONFIRM_FRAMES
    consecutive frames of agreement.

    Returns updated slot_to_corner (may be same object mutated in place).
    """
    if not frame_descs:
        return slot_to_corner

    # Build template list ordered by corner (corner 0 = red, corner 1 = blue).
    # Map: corner → template
    corner_to_tmpl = {tmpl["corner"]: tmpl for tmpl in templates.values()}

    def _cost(desc, corner):
        tmpl = corner_to_tmpl.get(corner)
        if tmpl is None:
            return 0.5
        tape_term = _tape_distance_term(
            desc["net_red"], desc["tape_total"], tmpl["net_red_sign"]
        )
        hist_term = _hist_distance_term(
            desc["hist"], desc["hist_weight"], tmpl["hist"]
        )
        base_cost = CORNER_TAPE_WEIGHT * tape_term + CORNER_HIST_WEIGHT * hist_term
        # Hysteresis penalty: add CORNER_HYSTERESIS_WEIGHT if this would flip the
        # current label for this slot.
        slot = desc["slot"]
        if slot_to_corner.get(slot) != corner:
            base_cost += CORNER_HYSTERESIS_WEIGHT
        return base_cost

    if len(frame_descs) == 2:
        d0, d1 = frame_descs[0], frame_descs[1]
        # Direct 2×2 bijective comparison — no scipy needed.
        cost_straight = _cost(d0, 0) + _cost(d1, 1)
        cost_swap     = _cost(d0, 1) + _cost(d1, 0)

        if cost_straight <= cost_swap:
            raw_assign = {d0["slot"]: 0, d1["slot"]: 1}
        else:
            raw_assign = {d0["slot"]: 1, d1["slot"]: 0}

    else:
        # Single detection: assign to closest template.
        d = frame_descs[0]
        c0 = _cost(d, 0)
        c1 = _cost(d, 1)
        raw_assign = {d["slot"]: 0 if c0 <= c1 else 1}

    # Apply hysteresis: a flip must persist for CORNER_SWAP_CONFIRM_FRAMES frames.
    for slot, proposed_corner in raw_assign.items():
        current_corner = slot_to_corner.get(slot)
        if proposed_corner == current_corner:
            # No flip — reset any pending confirmation.
            confirm_counters[slot] = 0
            pending_flip[slot]     = None
        else:
            # Proposed flip.
            if pending_flip.get(slot) == proposed_corner:
                confirm_counters[slot] += 1
            else:
                pending_flip[slot]     = proposed_corner
                confirm_counters[slot] = 1

            if confirm_counters[slot] >= CORNER_SWAP_CONFIRM_FRAMES:
                # Flip confirmed — commit.
                slot_to_corner[slot]   = proposed_corner
                confirm_counters[slot] = 0
                pending_flip[slot]     = None

    return slot_to_corner


# ---------------------------------------------------------------------------
# Legacy global fallback (original logic preserved verbatim)
# ---------------------------------------------------------------------------

def _legacy_global_corner_map(
    red_scores: dict, blue_scores: dict, model_votes: dict
) -> dict:
    """Original tape-vote / model-class-vote logic.  Returns corner_map {0:x,1:y}."""
    total_samples = sum(red_scores.values()) + sum(blue_scores.values())

    if total_samples >= CORNER_MIN_TAPE_SAMPLES:
        net = {t: red_scores[t] - blue_scores[t] for t in (0, 1)}
        corner_map = {0: 0, 1: 1} if net[0] >= net[1] else {0: 1, 1: 0}
        print(f"  Decision: tape vote → {corner_map}")
    else:
        print(
            f"  WARNING: insufficient tape samples ({total_samples} < "
            f"{CORNER_MIN_TAPE_SAMPLES}) — falling back to model class votes"
        )
        corner_map = {}
        for track_id in (0, 1):
            votes  = model_votes[track_id]
            winner = max(votes, key=votes.get) if any(votes.values()) else track_id
            corner_map[track_id] = winner

        if corner_map.get(0) == corner_map.get(1):
            print("  WARNING: model vote tie — using identity mapping as last resort")
            corner_map = {0: 0, 1: 1}

        print(f"  Decision: model vote → {corner_map}")

    return corner_map


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def assign_corners(pose_data: dict, video_path: str) -> dict:
    """
    Determine red/blue corner for each provisional track_id (0/1) and rewrite
    class_id in pose_data so that red=0, blue=1 matches the competition convention.

    Appearance path (default):
      Pass 1 — read the video sequentially; per detection build a descriptor
      (glove-tape counts + torso hue histogram); cache them in memory; identify
      clean frames (fighters separated, well-posed, tape present) and bootstrap
      per-corner appearance templates from those frames.

      Pass 2 — iterate over cached descriptors (no second cap.read); assign each
      detection to a template with normalized tape + histogram distance and
      hysteresis-gated flip confirmation.

    Legacy fallback:
      When the template separation is below CORNER_TEMPLATE_MIN_SEPARATION (colors
      too similar to distinguish) the original whole-fight tape-vote / model-class-
      vote logic is used, guaranteeing no regression.

    Args:
        pose_data:  In-memory pose dict from track_poses().
        video_path: Source video — read sequentially once; no seeking.

    Returns:
        Deep copy of pose_data with class_id rewritten to final corner labels.
    """
    data   = copy.deepcopy(pose_data)
    frames = data["frames"]
    total  = len(frames)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    # -----------------------------------------------------------------------
    # Pass 1: read video, build descriptors, accumulate legacy vote tallies
    # -----------------------------------------------------------------------
    # descriptor_cache[frame_idx] = list of per-detection dicts
    descriptor_cache: list[list[dict]] = []

    # Legacy accumulators (kept alongside so legacy fallback is free)
    red_scores:  dict[int, int] = {0: 0, 1: 0}
    blue_scores: dict[int, int] = {0: 0, 1: 0}
    model_votes: dict[int, dict[int, int]] = {0: {0: 0, 1: 0}, 1: {0: 0, 1: 0}}

    # Clean-frame descriptor buckets: slot → list of descriptors
    clean_descs: dict[int, list] = {0: [], 1: []}

    for idx, frame in enumerate(frames):
        fighter_dets = [
            d for d in frame.get("detections", [])
            if d.get("class_id") in (0, 1)
        ]

        if fighter_dets:
            ret, frame_bgr = cap.read()
            frame_bgr = frame_bgr if ret else None
        else:
            cap.grab()
            frame_bgr = None

        frame_descriptors = []

        if frame_bgr is not None:
            for det in fighter_dets:
                slot = det["class_id"]  # provisional track_id (0 or 1)

                orig = det.get("model_class_id")
                if orig in (0, 1):
                    model_votes[slot][orig] += 1

                kp = det.get("keypoints")
                if not kp or len(kp) < 11:
                    descriptor_cache.append([])
                    continue

                red_px, blue_px = _sample_tape(frame_bgr, kp, frame_h, frame_w)
                red_scores[slot]  += red_px
                blue_scores[slot] += blue_px

                hist, hist_weight = _sample_torso_histogram(frame_bgr, kp, frame_h, frame_w)

                desc = {
                    "slot":        slot,
                    "net_red":     red_px - blue_px,
                    "tape_total":  red_px + blue_px,
                    "hist":        hist,
                    "hist_weight": hist_weight,
                    "det_ref":     det,   # reference into data for Pass 2 rewrite
                }
                frame_descriptors.append(desc)

        descriptor_cache.append(frame_descriptors)

        # Accumulate clean-frame descriptors for template bootstrap.
        if len(frame_descriptors) == 2:
            dets_this = [d["det_ref"] for d in frame_descriptors]
            if _is_clean_frame(dets_this, frame_descriptors):
                for desc in frame_descriptors:
                    clean_descs[desc["slot"]].append(desc)

        if (idx + 1) % 500 == 0:
            print(f"  Corner assignment: {idx + 1}/{total} frames sampled")

    cap.release()

    total_tape = sum(red_scores.values()) + sum(blue_scores.values())
    print(f"Corner assignment — total tape pixels sampled: {total_tape}")
    print(f"  Track 0: red={red_scores[0]}  blue={blue_scores[0]}")
    print(f"  Track 1: red={red_scores[1]}  blue={blue_scores[1]}")

    clean_count = sum(len(v) for v in clean_descs.values())
    print(f"  Clean frames (per slot): slot0={len(clean_descs[0])}  "
          f"slot1={len(clean_descs[1])}  total={clean_count}")

    # -----------------------------------------------------------------------
    # Attempt to bootstrap appearance templates
    # -----------------------------------------------------------------------
    bootstrap_result = _bootstrap_templates(clean_descs) if clean_count > 0 else None

    use_appearance = bootstrap_result is not None
    if use_appearance:
        templates, separation = bootstrap_result
        print(f"  Appearance templates built — separation margin: {separation:.3f}")
        print(f"  Red corner template: slot "
              f"{next(s for s,t in templates.items() if t['corner']==0)}")
    else:
        reason = "insufficient clean frames" if clean_count == 0 else "low separation margin"
        print(f"  WARNING: appearance path skipped ({reason}) — using legacy fallback")

    # -----------------------------------------------------------------------
    # Pass 2: assign final corner labels
    # -----------------------------------------------------------------------
    if use_appearance:
        # Initial labels: use templates' corner assignment as the starting state.
        slot_to_corner  = {s: templates[s]["corner"] for s in (0, 1)}
        confirm_counters = {0: 0, 1: 0}
        pending_flip     = {0: None, 1: None}
        confirmed_swaps  = 0
        prev_labels      = dict(slot_to_corner)

        for frame_descs in descriptor_cache:
            if not frame_descs:
                continue

            old_labels = dict(slot_to_corner)
            _assign_frame_labels(
                frame_descs, templates, slot_to_corner, confirm_counters, pending_flip
            )

            for desc in frame_descs:
                slot = desc["slot"]
                new_corner = slot_to_corner[slot]
                if old_labels.get(slot) != new_corner:
                    confirmed_swaps += 1
                desc["det_ref"]["class_id"] = new_corner

            prev_labels = dict(slot_to_corner)

        print(f"  Appearance path: {confirmed_swaps} confirmed corner swap(s)")

    else:
        # Legacy: build static corner_map and apply uniformly.
        corner_map = _legacy_global_corner_map(red_scores, blue_scores, model_votes)
        swaps = 0
        for frame in data["frames"]:
            for det in frame.get("detections", []):
                old_id = det.get("class_id")
                if old_id in corner_map:
                    new_id = corner_map[old_id]
                    if new_id != old_id:
                        swaps += 1
                    det["class_id"] = new_id
        print(f"  Legacy path: remapped {swaps} detections")

    # -----------------------------------------------------------------------
    # Invariant check: no frame should have two fighters with the same id
    # -----------------------------------------------------------------------
    violations = 0
    for frame in data["frames"]:
        ids = [
            d["class_id"] for d in frame.get("detections", [])
            if d.get("class_id") in (0, 1)
        ]
        if len(ids) == 2 and ids[0] == ids[1]:
            violations += 1
    if violations:
        print(f"  WARNING: {violations} frame(s) still have duplicate corner ids")
    else:
        print("  Invariant OK: no duplicate corner ids in any frame")

    return data
