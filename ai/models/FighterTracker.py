import numpy as np
from scipy.optimize import linear_sum_assignment

from fight_processing.fight_processing_util import compute_iou
from models.constants import (
    TRACK_MAX_FIGHTERS,
    TRACK_IOU_WEIGHT,
    TRACK_DISTANCE_WEIGHT,
    TRACK_MAX_FRAMES_MISSING,
    CLINCH_IOU_THRESHOLD,
)


def _centroid(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


class _Slot:
    __slots__ = (
        "slot_id", "bbox", "centroid", "velocity",
        "frames_since_seen", "total_frames_seen", "model_class_counts",
    )

    def __init__(self, slot_id: int, bbox: list, model_class: int) -> None:
        self.slot_id = slot_id
        self.bbox = list(bbox)
        self.centroid = _centroid(bbox)
        self.velocity = (0.0, 0.0)
        self.frames_since_seen = 0
        self.total_frames_seen = 1
        self.model_class_counts: dict[int, int] = {model_class: 1}

    def predicted_bbox(self) -> list:
        x1, y1, x2, y2 = self.bbox
        vx, vy = self.velocity
        return [x1 + vx, y1 + vy, x2 + vx, y2 + vy]

    def predicted_centroid(self) -> tuple:
        cx, cy = self.centroid
        vx, vy = self.velocity
        return (cx + vx, cy + vy)

    def update(self, bbox: list, model_class: int) -> None:
        """Full update: advance position and refresh velocity."""
        new_cx, new_cy = _centroid(bbox)
        old_cx, old_cy = self.centroid
        self.velocity = (new_cx - old_cx, new_cy - old_cy)
        self.centroid = (new_cx, new_cy)
        self.bbox = list(bbox)
        self.frames_since_seen = 0
        self.total_frames_seen += 1
        self.model_class_counts[model_class] = (
            self.model_class_counts.get(model_class, 0) + 1
        )

    def update_position_only(self, bbox: list) -> None:
        """Update position from detection but freeze velocity (used during clinch)."""
        self.centroid = _centroid(bbox)
        self.bbox = list(bbox)
        self.frames_since_seen = 0
        self.total_frames_seen += 1

    def coast(self) -> None:
        """Advance predicted position by last velocity without a matching detection."""
        cx, cy = self.centroid
        vx, vy = self.velocity
        self.centroid = (cx + vx, cy + vy)
        x1, y1, x2, y2 = self.bbox
        self.bbox = [x1 + vx, y1 + vy, x2 + vx, y2 + vy]
        self.frames_since_seen += 1

    @property
    def majority_model_class(self) -> int:
        return max(self.model_class_counts, key=self.model_class_counts.get)


class FighterTracker:
    """
    Constrained 2-slot online tracker: IoU + centroid distance + Hungarian assignment.

    Assigns a stable provisional track_id (0 or 1) to at most TRACK_MAX_FIGHTERS
    fighter detections per frame.  Red/blue corner labelling is NOT done here —
    that is assign_corners()'s responsibility.

    Each output detection gets a 'model_class_id' field that preserves the
    original YOLO model class so assign_corners() can use it as a fallback.
    """

    def __init__(self) -> None:
        self.slots: dict[int, _Slot] = {}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _cost(self, slot: _Slot, bbox: list) -> float:
        iou = compute_iou(slot.predicted_bbox(), bbox)
        pred_cx, pred_cy = slot.predicted_centroid()
        det_cx, det_cy = _centroid(bbox)
        x1, y1, x2, y2 = bbox
        diag = max(1.0, ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
        dist_cost = ((pred_cx - det_cx) ** 2 + (pred_cy - det_cy) ** 2) ** 0.5 / diag
        return TRACK_IOU_WEIGHT * (1.0 - iou) + TRACK_DISTANCE_WEIGHT * dist_cost

    def _cold_start(self, dets: list[dict]) -> list[dict]:
        """Initialise slots from the very first frame that contains fighters."""
        used_ids: set[int] = set()
        out = []
        for det in dets[:TRACK_MAX_FIGHTERS]:
            # Seed slot_id from model class where possible (better initial map)
            preferred = det["class_id"]
            sid = preferred if preferred not in used_ids else next(
                i for i in range(TRACK_MAX_FIGHTERS) if i not in used_ids
            )
            used_ids.add(sid)
            self.slots[sid] = _Slot(sid, det["bbox_xyxy"], det["class_id"])
            out.append({
                "bbox_xyxy":      det["bbox_xyxy"],
                "confidence":     det["confidence"],
                "class_id":       sid,
                "model_class_id": det["class_id"],
            })
        return out

    def _assign(self, dets: list[dict], freeze_velocity: bool = False) -> list[dict]:
        """Run Hungarian matching and return output detections."""
        slot_ids = list(self.slots.keys())
        n_slots  = len(slot_ids)
        n_dets   = len(dets)
        size     = max(n_slots, n_dets)

        cost = np.full((size, size), 1e6)
        for i, sid in enumerate(slot_ids):
            for j, det in enumerate(dets):
                cost[i, j] = self._cost(self.slots[sid], det["bbox_xyxy"])

        row_ind, col_ind = linear_sum_assignment(cost)

        assigned_slots: set[int] = set()
        out: list = [None] * n_dets

        for r, c in zip(row_ind, col_ind):
            if r >= n_slots or c >= n_dets:
                continue
            if cost[r, c] >= 1e6:
                continue
            sid = slot_ids[r]
            det = dets[c]
            if freeze_velocity:
                self.slots[sid].update_position_only(det["bbox_xyxy"])
            else:
                self.slots[sid].update(det["bbox_xyxy"], det["class_id"])
            assigned_slots.add(sid)
            out[c] = {
                "bbox_xyxy":      det["bbox_xyxy"],
                "confidence":     det["confidence"],
                "class_id":       sid,
                "model_class_id": det["class_id"],
            }

        # Initialise a new slot for any unmatched detection (if under cap)
        for c, det in enumerate(dets):
            if out[c] is not None:
                continue
            if len(self.slots) < TRACK_MAX_FIGHTERS:
                new_id = next(i for i in range(TRACK_MAX_FIGHTERS) if i not in self.slots)
                self.slots[new_id] = _Slot(new_id, det["bbox_xyxy"], det["class_id"])
                out[c] = {
                    "bbox_xyxy":      det["bbox_xyxy"],
                    "confidence":     det["confidence"],
                    "class_id":       new_id,
                    "model_class_id": det["class_id"],
                }
            # 3rd+ detection with slots full → drop (mis-detected referee, etc.)

        # Coast any slot that had no match this frame; prune if too stale
        stale: list[int] = []
        for sid in slot_ids:
            if sid not in assigned_slots:
                self.slots[sid].coast()
                if self.slots[sid].frames_since_seen > TRACK_MAX_FRAMES_MISSING:
                    stale.append(sid)
        for sid in stale:
            del self.slots[sid]

        return [d for d in out if d is not None]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, fighter_dets: list[dict]) -> list[dict]:
        """
        Assign provisional track_id (0 or 1) to each fighter detection.

        Args:
            fighter_dets: Detections with class_id ∈ {0, 1} from the custom
                          YOLO model.  Referee detections (class_id=2) must be
                          filtered out by the caller.

        Returns:
            List of dicts with:
              class_id       — provisional track_id (0 or 1), stable across frames
              model_class_id — original YOLO class (0 or 1), preserved for fallback
              bbox_xyxy, confidence — unchanged from input
        """
        if not fighter_dets:
            for slot in list(self.slots.values()):
                slot.coast()
            stale = [
                sid for sid, s in self.slots.items()
                if s.frames_since_seen > TRACK_MAX_FRAMES_MISSING
            ]
            for sid in stale:
                del self.slots[sid]
            return []

        if not self.slots:
            return self._cold_start(fighter_dets)

        # Clinch: when the two detected boxes overlap heavily, freeze velocity
        # to prevent identity swaps while fighters are tangled.
        freeze = False
        if len(fighter_dets) == 2:
            iou = compute_iou(fighter_dets[0]["bbox_xyxy"], fighter_dets[1]["bbox_xyxy"])
            freeze = iou > CLINCH_IOU_THRESHOLD

        return self._assign(fighter_dets, freeze_velocity=freeze)

    @property
    def model_class_votes(self) -> dict[int, int]:
        """Majority model-class vote per slot — used as corner-assignment fallback."""
        return {sid: slot.majority_model_class for sid, slot in self.slots.items()}
