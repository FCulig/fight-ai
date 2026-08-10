"""Keyboard-driven video labelling tool.

Opens an OpenCV window with frame-accurate transport controls and a HUD. Strikes
are entered as a three-keystroke chord (fighter → family → target+outcome) so a
full annotation costs three keys and never needs the mouse or a text field.

Deliberately standalone: it does not touch PostgreSQL and does not import the
pipeline. Labelling must be possible before, and independently of, any pipeline
run — otherwise the ground truth is contaminated by what the pipeline predicted.

    python -m eval.cli label fight_videos/BATURvsSTAMATOVIC.mp4
"""

import datetime
from pathlib import Path
from typing import Optional

import cv2

from .schema import (
    Excluded,
    FightLabels,
    LABELS_DIR,
    Round,
    StateSpan,
    Strike,
)

MAX_DISPLAY_WIDTH = 1280
HUD_BG = (24, 24, 28)
WHITE = (240, 240, 240)
DIM = (150, 150, 155)
RED = (80, 80, 235)        # BGR
BLUE = (235, 160, 80)      # BGR
GREEN = (110, 210, 130)
AMBER = (70, 190, 240)

FAMILY_KEYS = {
    ord("j"): "jab",
    ord("k"): "cross",
    ord("h"): "hook",
    ord("u"): "uppercut",
    ord("n"): "knee",
    ord("m"): "elbow",
    ord("i"): "kick",
}
# Unshifted digit = landed, shifted = missed. Encodes target and outcome in one key.
TARGET_KEYS = {
    ord("1"): ("head", True),
    ord("2"): ("body", True),
    ord("3"): ("leg", True),
    ord("!"): ("head", False),
    ord("@"): ("body", False),
    ord("#"): ("leg", False),
}
STATE_KEYS = {ord("1"): "STRIKING", ord("2"): "CLINCH", ord("3"): "GROUND"}

SPEEDS = [0.1, 0.25, 0.5, 1.0]

HELP = [
    ("TRANSPORT", [
        "SPACE  play/pause",
        "a / d  step -1 / +1 frame",
        "A / D  step -10 / +10 frames",
        "z / c  step -1s / +1s",
        "Z / C  step -10s / +10s",
        "- / =  playback speed",
    ]),
    ("STRIKE  (3 keys)", [
        "1. r=red  b=blue",
        "2. j=jab k=cross h=hook u=uppercut",
        "   n=knee m=elbow i=kick",
        "3. 1/2/3 = head/body/leg LANDED",
        "   !/@/# = head/body/leg MISSED",
    ]),
    ("SPANS", [
        "s +1/2/3  state from here",
        "[  /  ]   round start / end",
        "x         exclude start/end",
    ]),
    ("FILE", [
        "u    undo last",
        "o    save",
        "ESC  cancel pending / quit",
    ]),
]


class Labeler:
    def __init__(self, video: str, labeler_name: str = ""):
        self.video_path = Path(video)
        self.cap = cv2.VideoCapture(str(video))
        if not self.cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video}")

        self.fps = round(self.cap.get(cv2.CAP_PROP_FPS)) or 30
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))

        self.frame_index = 1          # 1-based, matching the pipeline contract
        self.playing = False
        self.speed_idx = len(SPEEDS) - 1
        self._image = None
        self._image_at = -1

        self.labels = self._load_or_create(labeler_name)

        # Transient chord state and span-in-progress markers.
        self.pending_fighter: Optional[str] = None
        self.pending_family: Optional[str] = None
        self.awaiting_state = False
        self.open_round_start: Optional[int] = None
        self.open_exclude_start: Optional[int] = None

        # State marks are (frame, state); spans are materialised on save so
        # marks can be inserted out of order without bookkeeping.
        self.state_marks: list[tuple[int, str]] = [
            (s.start, s.state) for s in self.labels.states
        ]

        self.history: list[tuple[str, object]] = []
        self.message = "Ready. Press ESC to quit, o to save."

    # -- persistence -------------------------------------------------------

    def _load_or_create(self, labeler_name: str) -> FightLabels:
        path = LABELS_DIR / f"{self.video_path.stem}.json"
        if path.exists():
            labels = FightLabels.load(path)
            print(f"Resuming existing labels: {path}")
            print(labels.summary())
            return labels
        return FightLabels(
            video=self.video_path.name,
            fps=self.fps,
            frame_count=self.frame_count,
            labeler=labeler_name,
            labeled_at=datetime.date.today().isoformat(),
        )

    def save(self) -> None:
        self.labels.states = self._materialise_states()
        self.labels.frame_count = self.frame_count
        try:
            self.labels.validate()
        except Exception as e:
            self.message = f"NOT SAVED — {e}"
            return
        path = self.labels.save()
        self.message = f"Saved {len(self.labels.strikes)} strikes → {path.name}"
        print(f"\n{self.labels.summary()}\nSaved to {path}")

    def _materialise_states(self) -> list[StateSpan]:
        """Turn (frame, state) marks into contiguous non-overlapping spans.

        Each mark runs until the next mark, or to the end of the video for the
        last one. Marks are the natural thing to enter while scrubbing; spans
        are the natural thing to score against.
        """
        marks = sorted(set(self.state_marks))
        spans: list[StateSpan] = []
        for i, (frame, state) in enumerate(marks):
            end = marks[i + 1][0] - 1 if i + 1 < len(marks) else self.frame_count
            if end >= frame:
                spans.append(StateSpan(start=frame, end=end, state=state))
        return spans

    # -- frame access ------------------------------------------------------

    def _read_frame(self):
        """Decode the current frame, seeking only when not already positioned."""
        if self._image is not None and self._image_at == self.frame_index:
            return self._image

        target = self.frame_index
        pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
        if pos != target - 1:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, target - 1)

        ok, img = self.cap.read()
        if not ok:
            return self._image
        self._image, self._image_at = img, target
        return img

    def _seek(self, delta: int) -> None:
        self.frame_index = max(1, min(self.frame_count, self.frame_index + delta))

    # -- annotation --------------------------------------------------------

    def _commit_strike(self, target: str, landed: bool) -> None:
        strike = Strike(
            frame=self.frame_index,
            fighter=self.pending_fighter,
            family=self.pending_family,
            target=target,
            landed=landed,
        )
        self.labels.strikes.append(strike)
        self.history.append(("strike", strike))
        outcome = "landed" if landed else "missed"
        self.message = (f"+ {strike.fighter} {strike.family} {target} ({outcome}) "
                        f"@ f{strike.frame}")
        self.pending_fighter = self.pending_family = None

    def _undo(self) -> None:
        if not self.history:
            self.message = "Nothing to undo"
            return
        kind, obj = self.history.pop()
        if kind == "strike":
            self.labels.strikes.remove(obj)
        elif kind == "state":
            self.state_marks.remove(obj)
        elif kind == "round":
            self.labels.rounds.remove(obj)
        elif kind == "exclude":
            self.labels.excluded.remove(obj)
        self.message = f"Undid {kind}"

    # -- key handling ------------------------------------------------------

    def _handle_key(self, key: int) -> bool:
        """Returns False to quit."""
        # A chord in progress consumes keys before transport controls, so `1`
        # means "head" rather than anything else while a strike is half-entered.
        if self.pending_fighter and not self.pending_family:
            if key in FAMILY_KEYS:
                self.pending_family = FAMILY_KEYS[key]
                return True
            if key == 27:
                self.pending_fighter = None
                self.message = "Cancelled"
                return True

        elif self.pending_fighter and self.pending_family:
            if key in TARGET_KEYS:
                target, landed = TARGET_KEYS[key]
                self._commit_strike(target, landed)
                return True
            if key == 27:
                self.pending_fighter = self.pending_family = None
                self.message = "Cancelled"
                return True

        elif self.awaiting_state:
            self.awaiting_state = False
            if key in STATE_KEYS:
                mark = (self.frame_index, STATE_KEYS[key])
                self.state_marks.append(mark)
                self.history.append(("state", mark))
                self.message = f"State {mark[1]} from f{mark[0]}"
            return True

        # --- transport ---
        if key == ord(" "):
            self.playing = not self.playing
        elif key == ord("a"):
            self._seek(-1); self.playing = False
        elif key == ord("d"):
            self._seek(1); self.playing = False
        elif key == ord("A"):
            self._seek(-10); self.playing = False
        elif key == ord("D"):
            self._seek(10); self.playing = False
        elif key == ord("z"):
            self._seek(-self.fps); self.playing = False
        elif key == ord("c"):
            self._seek(self.fps); self.playing = False
        elif key == ord("Z"):
            self._seek(-10 * self.fps); self.playing = False
        elif key == ord("C"):
            self._seek(10 * self.fps); self.playing = False
        elif key == ord("-"):
            self.speed_idx = max(0, self.speed_idx - 1)
        elif key == ord("="):
            self.speed_idx = min(len(SPEEDS) - 1, self.speed_idx + 1)

        # --- annotation entry points ---
        elif key == ord("r"):
            self.pending_fighter, self.playing = "red", False
        elif key == ord("b"):
            self.pending_fighter, self.playing = "blue", False
        elif key == ord("s"):
            self.awaiting_state, self.playing = True, False

        elif key == ord("["):
            self.open_round_start = self.frame_index
            self.message = f"Round start at f{self.frame_index} — press ] to close"
        elif key == ord("]"):
            if self.open_round_start is None:
                self.message = "Press [ first to set the round start"
            else:
                rnd = Round(start=self.open_round_start, end=self.frame_index,
                            round=len(self.labels.rounds) + 1)
                self.labels.rounds.append(rnd)
                self.history.append(("round", rnd))
                self.message = f"Round {rnd.round}: f{rnd.start}–f{rnd.end}"
                self.open_round_start = None

        elif key == ord("x"):
            if self.open_exclude_start is None:
                self.open_exclude_start = self.frame_index
                self.message = f"Exclusion from f{self.frame_index} — press x to close"
            else:
                exc = Excluded(start=self.open_exclude_start, end=self.frame_index,
                               reason="")
                self.labels.excluded.append(exc)
                self.history.append(("exclude", exc))
                self.message = f"Excluded f{exc.start}–f{exc.end}"
                self.open_exclude_start = None

        elif key == ord("u"):
            self._undo()
        elif key == ord("o"):
            self.save()
        elif key == 27:
            return False

        return True

    # -- rendering ---------------------------------------------------------

    def _hud_lines(self) -> list[tuple[str, tuple[int, int, int]]]:
        t = self.frame_index / self.fps
        state = next((s for f, s in sorted(self.state_marks, reverse=True)
                      if f <= self.frame_index), "—")
        in_round = next((r.round for r in self.labels.rounds
                         if r.start <= self.frame_index <= r.end), None)
        excluded = self.labels.is_excluded(self.frame_index)

        lines = [
            (f"f{self.frame_index}/{self.frame_count}   "
             f"{int(t // 60)}:{t % 60:05.2f}   "
             f"{'PLAY' if self.playing else 'PAUSE'} x{SPEEDS[self.speed_idx]}",
             WHITE),
            (f"state {state}   round {in_round or '—'}"
             f"{'   EXCLUDED' if excluded else ''}", DIM),
            (f"strikes {len(self.labels.strikes)}   "
             f"rounds {len(self.labels.rounds)}   "
             f"states {len(self.state_marks)}", DIM),
        ]

        if self.pending_fighter and not self.pending_family:
            lines.append((f"{self.pending_fighter.upper()} → pick family "
                          f"(j k h u n m i)",
                          RED if self.pending_fighter == "red" else BLUE))
        elif self.pending_fighter and self.pending_family:
            lines.append((f"{self.pending_fighter.upper()} {self.pending_family} → "
                          f"1/2/3 landed, !/@/# missed",
                          RED if self.pending_fighter == "red" else BLUE))
        elif self.awaiting_state:
            lines.append(("STATE → 1 striking  2 clinch  3 ground", AMBER))
        else:
            lines.append((self.message, GREEN))

        return lines

    def _render(self, img):
        scale = min(1.0, MAX_DISPLAY_WIDTH / img.shape[1])
        if scale < 1.0:
            img = cv2.resize(img, None, fx=scale, fy=scale)
        canvas = img.copy()
        h, w = canvas.shape[:2]

        # Transport HUD across the top.
        lines = self._hud_lines()
        pad = 10
        box_h = pad * 2 + 22 * len(lines)
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (w, box_h), HUD_BG, -1)
        cv2.addWeighted(overlay, 0.78, canvas, 0.22, 0, canvas)
        for i, (text, colour) in enumerate(lines):
            cv2.putText(canvas, text, (pad, pad + 16 + 22 * i),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 1, cv2.LINE_AA)

        # Round / exclusion timeline strip along the bottom.
        strip_h = 8
        y0 = h - strip_h
        cv2.rectangle(canvas, (0, y0), (w, h), (40, 40, 44), -1)
        for r in self.labels.rounds:
            x1 = int(w * r.start / self.frame_count)
            x2 = int(w * r.end / self.frame_count)
            cv2.rectangle(canvas, (x1, y0), (x2, h), (90, 140, 90), -1)
        for e in self.labels.excluded:
            x1 = int(w * e.start / self.frame_count)
            x2 = int(w * e.end / self.frame_count)
            cv2.rectangle(canvas, (x1, y0), (x2, h), (60, 60, 140), -1)
        for s in self.labels.strikes:
            x = int(w * s.frame / self.frame_count)
            cv2.line(canvas, (x, y0), (x, h), RED if s.fighter == "red" else BLUE, 1)
        x = int(w * self.frame_index / self.frame_count)
        cv2.line(canvas, (x, y0 - 4), (x, h), WHITE, 2)

        return canvas

    # -- main loop ---------------------------------------------------------

    def run(self) -> None:
        print(_help_text())
        win = f"label — {self.video_path.name}"
        cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)

        while True:
            img = self._read_frame()
            if img is None:
                break
            cv2.imshow(win, self._render(img))

            if self.playing:
                delay = max(1, int(1000 / (self.fps * SPEEDS[self.speed_idx])))
            else:
                delay = 20

            key = cv2.waitKey(delay) & 0xFF
            if key != 255:
                if not self._handle_key(key):
                    break
            elif self.playing:
                if self.frame_index >= self.frame_count:
                    self.playing = False
                else:
                    self.frame_index += 1

        cv2.destroyAllWindows()
        self.cap.release()

        if self.labels.strikes or self.state_marks or self.labels.rounds:
            answer = input("\nSave before quitting? [Y/n] ").strip().lower()
            if answer in ("", "y", "yes"):
                self.save()


def _help_text() -> str:
    L = ["", "=" * 62, "LABELLING CONTROLS", "=" * 62]
    for section, keys in HELP:
        L.append(f"\n{section}")
        L.extend(f"  {k}" for k in keys)
    L.append("")
    L.append("Label every strike THROWN, not just those that land — the model")
    L.append("needs negatives. Mark the frame of peak extension / impact.")
    L.append("=" * 62)
    return "\n".join(L)


def run_labeler(video: str, labeler_name: str = "") -> None:
    Labeler(video, labeler_name).run()
