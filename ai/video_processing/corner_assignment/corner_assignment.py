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
  A whole-fight static corner_map from a per-frame *paired* tape vote (which of
  the two fighters read redder in this frame), falling back to model-class votes.

Everything colour here is measured as *coverage of the sampled glove crop* and
compared *between the two fighters within one frame*, then aggregated one vote
per frame. Absolute pixel counts summed over a fight do not work: the red HSV
band overlaps skin, so both fighters read overwhelmingly "red" on every fight in
runs/upload_pipeline.log, and the sum then ranks them by how long each spent in
close-up. That is how MILIDRAGOVICvsMOOSMAN was assigned backwards for its whole
length (22.8M vs 28.2M "red" pixels, essentially all skin).
"""

import copy

import cv2
import numpy as np

from models.constants import (
    TAPE_PATCH_RATIO,
    WRIST_EDGE_MARGIN_RATIO,
    TAPE_MIN_SATURATION,
    TAPE_MIN_VALUE,
    RED_HUE_HIGH1,
    RED_HUE_LOW2,
    BLUE_HUE_LOW,
    BLUE_HUE_HIGH,
    CORNER_TAPE_VOTE_MIN_MARGIN,
    CORNER_MIN_TAPE_VOTES,
    CORNER_TAPE_SEPARATION_FULL,
    KEYPOINT_MIN_CONFIDENCE,
    STRIKING_CORE_KEYPOINT_INDICES,
    DISTANCE_GRAPPLING_RATIO,
    TORSO_HIST_BINS,
    TORSO_MIN_SATURATION,
    TORSO_MIN_VALUE,
    TORSO_SAMPLE_MIN_PIXELS,
    CORNER_CLEAN_FRAME_MIN_TAPE,
    CORNER_TEMPLATE_MIN_SEPARATION,
    CORNER_TAPE_WEIGHT,
    CORNER_HIST_WEIGHT,
    CORNER_HYSTERESIS_WEIGHT,
    CORNER_SWAP_CONFIRM_SECS,
)
from models.geometry import (
    get_fighter_scale,
    get_torso_rectangle,
    calculate_distance_between_fighters,
)

# COCO keypoint index pairs: (wrist, elbow) for left and right arms
_WRIST_PAIRS = [(9, 7), (10, 8)]

# Hysteresis state is keyed on the slot→corner mapping as a whole, not per
# slot — the mapping is a bijection, so "slot 0 flips" and "slot 1 flips" are
# the same event and must commit together. See _assign_frame_labels.
_SWAP_KEY = "swap"


# ---------------------------------------------------------------------------
# Tape sampling
# ---------------------------------------------------------------------------

def _patch_half(kp: list, wrist_idx: int, elbow_idx: int, scale: float) -> int:
    """Scale crop half-side by forearm length when elbow is visible, else by
    fighter scale directly (both expressed as a fraction via TAPE_PATCH_RATIO,
    so this stays correct as the camera zooms in/out — see plan Stage 1 step 4).

    The forearm multiplier is deliberately small: the target is the glove, and
    a box that reaches back up the forearm counts skin, which swamps the tape.
    """
    base = TAPE_PATCH_RATIO * scale
    wx, wy = kp[wrist_idx][0], kp[wrist_idx][1]
    ex, ey = kp[elbow_idx][0], kp[elbow_idx][1]
    if ex == 0 and ey == 0:
        return int(base)
    forearm = ((wx - ex) ** 2 + (wy - ey) ** 2) ** 0.5
    scaled = int(forearm * 0.18)
    return max(int(base / 2), min(int(base * 1.5), scaled))


def _sample_tape(frame_bgr: np.ndarray, kp: list, h: int, w: int) -> tuple[int, int, int]:
    """Count red and blue HSV pixels around both wrists.

    Returns (red_pixels, blue_pixels, sampled_pixels). The third value is what
    lets callers work in *coverage fractions* instead of raw counts — without
    it, a fighter shot in close-up contributes proportionally more pixels than
    one shot wide, and summing raw counts over a fight measures camera framing
    rather than glove colour.
    """
    red_total  = 0
    blue_total = 0
    area_total = 0

    scale = get_fighter_scale(kp)
    if scale is None:
        # No confident torso to size the crop against — unusable this frame,
        # rather than falling back to a hallucinated/absolute crop size.
        return red_total, blue_total, area_total

    edge_margin = WRIST_EDGE_MARGIN_RATIO * w

    for wrist_idx, elbow_idx in _WRIST_PAIRS:
        wx, wy = kp[wrist_idx][0], kp[wrist_idx][1]

        if wx == 0 and wy == 0:
            continue
        if (wx < edge_margin or wx > w - edge_margin or
                wy < edge_margin or wy > h - edge_margin):
            continue
        # A wrist the pose model isn't sure about is usually occluded or
        # hallucinated, and the crop then lands on whatever is behind it.
        if kp[wrist_idx][2] < KEYPOINT_MIN_CONFIDENCE:
            continue

        half = _patch_half(kp, wrist_idx, elbow_idx, scale)
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
        area_total += patch.shape[0] * patch.shape[1]

    return red_total, blue_total, area_total


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

    # Extend downward by half a fighter scale to include the shorts. A None
    # scale means the shoulder/hip joints aren't confident enough to trust —
    # the same joints this region's box is built from — so the region itself
    # isn't trustworthy either.
    scale = get_fighter_scale(kp)
    if scale is None:
        return None, 0

    x1 = max(0, int(pts[:, 0].min()))
    y1 = max(0, int(pts[:, 1].min()))
    x2 = min(w, int(pts[:, 0].max()))
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
    fighters well-separated, and sufficient tape pixels.

    The joint bar is the **core trunk** set (head + shoulders + hips), not the
    full strike set. Those five joints are all this check and its callers
    actually consume — the torso rectangle, the fighter scale and the torso
    histogram are built from shoulders/hips alone, and tape presence is gated
    separately below. Requiring all 15 strike joints instead demanded confident
    knees and ankles, which a broadcast camera occludes constantly: it returned
    ZERO clean frames across all 18,518 frames of NAZHANDvsSTAROPOLI, so the
    appearance path never ran and every tracker identity swap went uncorrected.
    This is the same relaxation `frame_validity` already makes, for the same
    reason — see ai/CLAUDE.md "Frame validity".
    """
    if len(dets) != 2 or len(descriptors) != 2:
        return False

    for d in dets:
        kp = d.get("keypoints")
        if kp is None or len(kp) < 17:
            return False
        if not all(kp[i][2] >= KEYPOINT_MIN_CONFIDENCE
                   for i in STRIKING_CORE_KEYPOINT_INDICES):
            return False

    for desc in descriptors:
        if desc["tape_total"] < CORNER_CLEAN_FRAME_MIN_TAPE:
            return False

    kp0 = dets[0]["keypoints"]
    kp1 = dets[1]["keypoints"]
    rect0 = get_torso_rectangle(kp0)
    rect1 = get_torso_rectangle(kp1)
    dist  = calculate_distance_between_fighters(rect0, rect1)
    scale0 = get_fighter_scale(kp0)
    scale1 = get_fighter_scale(kp1)
    # The core joint set required above is exactly the shoulders/hips these
    # three read, so they should never be None in practice — but they are all
    # allowed to return None, so a clean frame must not be declared on an
    # unusable distance rather than a genuinely close one.
    if dist is None or scale0 is None or scale1 is None:
        return False
    if dist < DISTANCE_GRAPPLING_RATIO * (scale0 + scale1) / 2:
        return False

    return True


# ---------------------------------------------------------------------------
# Template bootstrap
# ---------------------------------------------------------------------------

def _bootstrap_templates(
    clean_descriptors: dict[int, list],  # track_id → list of per-frame descriptors
) -> tuple[dict, float] | str:
    """Build per-corner appearance templates from clean-frame descriptors.

    Accumulates per-slot (0/1) mean net-red *coverage* and weighted-mean hue
    histogram. Assigns the red corner by net-red sign (same rule as the legacy
    path).

    Returns (templates, separation, detail) on success, or a short string naming
    the reason the appearance path cannot be used → caller falls back to legacy.
    The reason is returned rather than a bare None because the three failures
    are not interchangeable: "no clean frames" points at the pose/joint gate,
    "ambiguous tape" at the colour sampler, and "low separation" at genuinely
    similar kit. The old code collapsed all three into None and the caller
    then guessed, reporting "low separation margin" for fights that had in
    fact failed the ambiguous-sign check.
    """
    templates = {}
    for slot in (0, 1):
        descs = clean_descriptors.get(slot, [])
        if not descs:
            return "no clean frames for slot %d" % slot

        # Mean coverage, not sum: clean frames are not equally framed, and a
        # sum lets a handful of close-ups outvote the rest of the fight.
        net_red_sum  = sum(d["net_red"] for d in descs) / len(descs)
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
            "net_red_mean": net_red_sum,
            "hist":         mean_hist,
            "hist_weight":  weight_sum,
        }

    # Slot → corner: whichever has net_red_sign == +1 is the red corner.
    slot0_sign = templates[0]["net_red_sign"]
    slot1_sign = templates[1]["net_red_sign"]
    if slot0_sign == slot1_sign:
        # Both fighters read the same colour — the sampler found nothing that
        # distinguishes them, so there is no basis for a template.
        return "ambiguous tape (both slots read %s)" % (
            "red" if slot0_sign == 1 else "blue")

    # Measure separation: how far apart the two slots' mean net-red coverages
    # actually are, saturating at CORNER_TAPE_SEPARATION_FULL, plus histogram
    # distance. Both terms are in [0, 1] and larger means more distinguishable.
    #
    # This replaces a comparison of sum(abs(net_red)) between the slots, which
    # measured magnitude rather than difference and was therefore inverted: a
    # textbook red-vs-blue split scored 0.0 and got rejected, while a slot with
    # essentially no evidence scored 0.49 and got accepted.
    gap = abs(templates[0]["net_red_mean"] - templates[1]["net_red_mean"])
    net_red_gap = min(1.0, gap / CORNER_TAPE_SEPARATION_FULL)

    hist_dist = 0.0
    h0, h1 = templates[0]["hist"], templates[1]["hist"]
    if h0 is not None and h1 is not None:
        hist_dist = float(cv2.compareHist(h0, h1, cv2.HISTCMP_BHATTACHARYYA))

    separation = 0.5 * net_red_gap + 0.5 * hist_dist

    if separation < CORNER_TEMPLATE_MIN_SEPARATION:
        return "low separation margin (%.3f < %.3f)" % (
            separation, CORNER_TEMPLATE_MIN_SEPARATION)

    # Kept for tuning: shows whether the tape term is actually discriminating
    # or has saturated at CORNER_TAPE_SEPARATION_FULL and gone inert.
    detail = (f"tape gap {gap:.4f} (→{net_red_gap:.2f} of "
              f"{CORNER_TAPE_SEPARATION_FULL}) · hist dist {hist_dist:.3f}")

    # Annotate templates with which corner (0=red, 1=blue) they represent.
    for slot in (0, 1):
        templates[slot]["corner"] = 0 if templates[slot]["net_red_sign"] == 1 else 1

    return templates, separation, detail


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
    confirm_counters: dict,     # {_SWAP_KEY: consecutive frames pending the swap}
    pending_flip: dict,         # {_SWAP_KEY: candidate mapping while confirming}
    confirm_frames: int,        # CORNER_SWAP_CONFIRM_SECS converted to frames at the caller
) -> dict:
    """Assign corner labels (0=red, 1=blue) to each detection for this frame.

    Uses a 2-template cost matrix (normalized tape + histogram distance) with
    hysteresis: flips are only committed after `confirm_frames` consecutive
    frames of agreement.

    `slot_to_corner` is a bijection and stays one — two slots, two corners.
    Hysteresis therefore confirms the mapping as a whole rather than each slot
    on its own; see the comment at the commit step.

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

    if len(frame_descs) == 2 and frame_descs[0]["slot"] != frame_descs[1]["slot"]:
        d0, d1 = frame_descs[0], frame_descs[1]
        # Direct 2×2 bijective comparison — no scipy needed.
        cost_straight = _cost(d0, 0) + _cost(d1, 1)
        cost_swap     = _cost(d0, 1) + _cost(d1, 0)

        if cost_straight <= cost_swap:
            candidate = {d0["slot"]: 0, d1["slot"]: 1}
        else:
            candidate = {d0["slot"]: 1, d1["slot"]: 0}

    else:
        # Single detection: assign to the closest template and give the absent
        # slot the other corner. With two slots and two corners a proposal
        # about one slot is equally a proposal about the other, so writing the
        # complement keeps the mapping a bijection instead of letting the two
        # slots drift onto the same corner while one of them is unobserved.
        d      = frame_descs[0]
        slot   = d["slot"]
        corner = 0 if _cost(d, 0) <= _cost(d, 1) else 1
        candidate = {slot: corner, 1 - slot: 1 - corner}

    # Apply hysteresis: a flip must persist for `confirm_frames` frames.
    #
    # The whole mapping is confirmed as ONE event. Confirming each slot on its
    # own counter let one slot's flip commit while the other's was still
    # pending, so for the frames in between both slots carried the same corner
    # — the "duplicate corner ids" the invariant check at the end reports.
    if candidate == slot_to_corner:
        # No flip — reset any pending confirmation.
        confirm_counters[_SWAP_KEY] = 0
        pending_flip[_SWAP_KEY]     = None
    else:
        # Proposed flip.
        if pending_flip.get(_SWAP_KEY) == candidate:
            confirm_counters[_SWAP_KEY] += 1
        else:
            pending_flip[_SWAP_KEY]     = candidate
            confirm_counters[_SWAP_KEY] = 1

        if confirm_counters[_SWAP_KEY] >= confirm_frames:
            # Flip confirmed — commit both slots together.
            slot_to_corner.update(candidate)
            confirm_counters[_SWAP_KEY] = 0
            pending_flip[_SWAP_KEY]     = None

    return slot_to_corner


# ---------------------------------------------------------------------------
# Legacy global fallback (original logic preserved verbatim)
# ---------------------------------------------------------------------------

def _legacy_global_corner_map(
    tape_votes: dict, model_votes: dict
) -> dict:
    """Whole-fight fallback: paired per-frame tape vote, then model-class vote.
    Returns corner_map {0:x,1:y}.

    `tape_votes[slot]` counts frames in which that slot read *redder than the
    other fighter in the same frame*. Comparing the two within a frame cancels
    the lighting, exposure and skin baseline they share, and one vote per frame
    stops close-ups from outweighing the rest of the fight — the previous
    version summed raw red/blue pixel counts across the whole video and so
    decided the corner on framing rather than colour.
    """
    total_votes = tape_votes[0] + tape_votes[1]

    if total_votes >= CORNER_MIN_TAPE_VOTES:
        corner_map = {0: 0, 1: 1} if tape_votes[0] >= tape_votes[1] else {0: 1, 1: 0}
        margin = abs(tape_votes[0] - tape_votes[1]) / total_votes
        print(f"  Decision: paired tape vote {tape_votes[0]}/{tape_votes[1]} "
              f"(margin {margin:.0%}) → {corner_map}")
    else:
        print(
            f"  WARNING: insufficient tape votes ({total_votes} < "
            f"{CORNER_MIN_TAPE_VOTES}) — falling back to model class votes"
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
    confirm_frames = max(1, round(pose_data.get("fps", 50.0) * CORNER_SWAP_CONFIRM_SECS))

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

    # Legacy accumulators (kept alongside so legacy fallback is free).
    # tape_votes counts frames in which a slot read redder than the *other*
    # fighter in that same frame — see _legacy_global_corner_map. red/blue_px
    # are diagnostics only; nothing decides on them.
    tape_votes:  dict[int, int] = {0: 0, 1: 0}
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
                    continue

                red_px, blue_px, area_px = _sample_tape(frame_bgr, kp, frame_h, frame_w)
                red_scores[slot]  += red_px
                blue_scores[slot] += blue_px

                hist, hist_weight = _sample_torso_histogram(frame_bgr, kp, frame_h, frame_w)

                desc = {
                    "slot":        slot,
                    # Coverage fraction of the sampled glove crop, not a raw
                    # pixel count — comparable between fighters and between
                    # frames regardless of how close the camera is.
                    "net_red":     (red_px - blue_px) / area_px if area_px else 0.0,
                    "tape_total":  red_px + blue_px,
                    "hist":        hist,
                    "hist_weight": hist_weight,
                    "det_ref":     det,   # reference into data for Pass 2 rewrite
                }
                frame_descriptors.append(desc)

        descriptor_cache.append(frame_descriptors)

        # Paired tape vote: both fighters seen in the same frame under the same
        # light, so the difference between them is the part that carries colour.
        if len(frame_descriptors) == 2:
            d0, d1 = frame_descriptors
            if (d0["slot"] != d1["slot"]
                    and abs(d0["net_red"] - d1["net_red"]) >= CORNER_TAPE_VOTE_MIN_MARGIN):
                redder = d0 if d0["net_red"] > d1["net_red"] else d1
                tape_votes[redder["slot"]] += 1

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
    print(f"  Paired tape votes (redder-in-frame): "
          f"slot0={tape_votes[0]}  slot1={tape_votes[1]}")

    clean_count = sum(len(v) for v in clean_descs.values())
    print(f"  Clean frames (per slot): slot0={len(clean_descs[0])}  "
          f"slot1={len(clean_descs[1])}  total={clean_count}")

    # -----------------------------------------------------------------------
    # Attempt to bootstrap appearance templates
    # -----------------------------------------------------------------------
    bootstrap_result = (
        _bootstrap_templates(clean_descs) if clean_count > 0
        else "insufficient clean frames"
    )

    use_appearance = not isinstance(bootstrap_result, str)
    if use_appearance:
        templates, separation, detail = bootstrap_result
        print(f"  Appearance templates built — separation margin: {separation:.3f}")
        print(f"    {detail}")
        print(f"  Red corner template: slot "
              f"{next(s for s,t in templates.items() if t['corner']==0)}")
    else:
        print(f"  WARNING: appearance path skipped ({bootstrap_result}) "
              f"— using legacy fallback")

    # -----------------------------------------------------------------------
    # Pass 2: assign final corner labels
    # -----------------------------------------------------------------------
    if use_appearance:
        # Initial labels: use templates' corner assignment as the starting state.
        slot_to_corner  = {s: templates[s]["corner"] for s in (0, 1)}
        confirm_counters = {_SWAP_KEY: 0}
        pending_flip     = {_SWAP_KEY: None}
        confirmed_swaps  = 0

        # descriptor_cache is built one entry per frame in Pass 1, so it lines
        # up with data["frames"] index-for-index.
        for frame, frame_descs in zip(data["frames"], descriptor_cache):
            if frame_descs:
                old_labels = dict(slot_to_corner)
                _assign_frame_labels(
                    frame_descs, templates, slot_to_corner, confirm_counters,
                    pending_flip, confirm_frames,
                )
                if slot_to_corner != old_labels:
                    confirmed_swaps += 1

            # Relabel EVERY fighter detection in the frame, not just the ones
            # that produced a descriptor. A detection whose keypoints were
            # unusable (occluded, low confidence) yields no descriptor, and
            # leaving it alone left it carrying a raw tracker slot id while its
            # opponent carried an appearance corner — the two then collide on
            # the same value, which is the rest of the duplicate corner ids.
            # Frames with no descriptors at all simply carry the last confirmed
            # mapping forward, which is the best available estimate.
            for det in frame.get("detections", []):
                slot = det.get("class_id")
                if slot in (0, 1):
                    det["class_id"] = slot_to_corner[slot]

        print(f"  Appearance path: {confirmed_swaps} confirmed corner swap(s)")

    else:
        # Legacy: build static corner_map and apply uniformly.
        corner_map = _legacy_global_corner_map(tape_votes, model_votes)
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
