LABEL_ID = {
    "fighter_red": 0,
    "fighter_blue": 1,
    "referee": 2
}

# --- Fight-state temporal smoothing (determine_fight_state) ---
# Replaces the old 3-/5-consecutive-frame counters, which were 0.06-0.1s at
# 50fps — no real hysteresis at all. A majority vote (the categorical
# equivalent of a median filter — there's no numeric ordering to three state
# names) over this rolling window smooths single-frame misreads; a transition
# is only committed once the smoothed candidate has been different from the
# current state AND at least FIGHT_STATE_MIN_DWELL_SECS has passed since the
# last transition. See plan Stage 1 step 7.
FIGHT_STATE_SMOOTHING_WINDOW_SECS = 0.5
FIGHT_STATE_MIN_DWELL_SECS        = 0.75

# Distance threshold to determine if fighters are grappling (clinch or ground),
# expressed as a fraction of fighter scale rather than an absolute pixel count
# — a camera zoomed out puts fighters' torsos closer together in pixels for
# the same real-world distance. Calibrated against the old 20px threshold at
# JURICvsNOGUEIRA.mp4's measured median torso scale (~178px @ 1280x720). See
# plan Stage 1 step 4 — re-tune via the sweep (step 8) once labels exist.
DISTANCE_GRAPPLING_RATIO = 0.11

# --- Posture: standing (clinch) vs grounded (ground game) ---
# Within grapple distance, posture splits CLINCH from GROUND.
# Torso vector = shoulder-midpoint → hip-midpoint. Tilt from the vertical axis
# (degrees): ~0° standing upright, ~90° lying horizontal. Above this a fighter
# reads as grounded.
TORSO_VERTICAL_ANGLE_THRESHOLD = 50
# Vertical body span (head→ankle y-extent) divided by fighter scale. Collapses
# when a fighter is on the canvas. Below this the body reads as grounded.
GROUND_VERTICAL_SPAN_RATIO = 1.2

# Number of seconds to look back when determining takedown initiator
TAKEDOWN_LOOKBACK_SECS = 0.3   # 15 frames @ 50fps

# Minimum hip drop for a fighter to be considered the one being taken down,
# as a fraction of fighter scale — was an absolute 30px. Calibrated the same
# way as DISTANCE_GRAPPLING_RATIO above. See plan Stage 1 step 4.
MIN_HIP_DROP_RATIO = 0.17

# Strike detection thresholds
# Velocities are expressed as (fraction of attacker scale) per second — fps-invariant.
# Contact distances are expressed as fraction of defender scale — zoom-invariant.
PUNCH_VELOCITY_RATIO = 4.5      # wrist speed (scale/sec) to count as a punch
KICK_VELOCITY_RATIO = 6.0       # ankle speed (scale/sec) to count as a kick
ARM_EXTENSION_THRESHOLD = 140   # minimum elbow angle (degrees) for a straight punch (jab/cross)
# Bent-arm punch (hook/uppercut): elbow angle window — too straight = jab (handled above),
# too bent = not a punch at all.
PUNCH_BENT_ANGLE_MIN = 60      # degrees — below this is too folded to be a punch
PUNCH_BENT_ANGLE_MAX = 139     # degrees — above this falls into the straight path
LEG_EXTENSION_THRESHOLD = 130   # minimum knee angle (degrees) for a kick
STRIKE_COOLDOWN_SECS = 0.3      # 15 frames @ 50fps — time to suppress re-detection after a strike
STRIKE_EXTENSION_SECS = 0.04    # 2 frames @ 50fps — time angle must be held to confirm a strike
# In clinch/grappling the fighters are already in contact so the open-range contact
# gate is replaced by a directional gate (below); use a lower velocity threshold to
# catch short-range strikes (knees, dirty boxing).
GRAPPLING_PUNCH_VELOCITY_RATIO = 2.0
GRAPPLING_KICK_VELOCITY_RATIO  = 2.5

# --- Grappling strike gate (clinch / ground) ---
# In a clinch fighters are entangled, so raw proximity no longer discriminates a
# strike from pummeling / hand-fighting / gripping — the hands are near the
# opponent's torso either way. The discriminating signal is DIRECTION: a real short
# strike drives the end-effector toward a target zone (head or torso), whereas
# swimming for underhooks, framing and gripping move it laterally or pull it back.
# A grappling strike must satisfy BOTH a relaxed proximity sanity-check and a
# velocity-alignment-toward-target check.
GRAPPLING_HEAD_CONTACT_RATIO  = 0.60   # relaxed head proximity (fraction of defender scale)
GRAPPLING_TORSO_CONTACT_RATIO = 0.70   # relaxed torso proximity (fraction of defender scale)
# Cosine of the angle between the end-effector velocity and the vector to the target
# zone. 0.5 ≈ within 60° of driving straight at the target. Pummeling / gripping
# motions are lateral or pull away and fall below this.
GRAPPLING_STRIKE_DIRECTION_MIN = 0.5

# Keypoint confidence gating
# Joints below this confidence are treated as unreliable and their limb is skipped.
# Landed-vs-attempted: head recoil check after a candidate strike
# Check the opponent head velocity over this many seconds after contact.
RECOIL_LOOKAHEAD_SECS = 0.08   # 4 frames @ 50fps
# Head must move at least this many (scale/sec) to count as a recoil signal.
RECOIL_VELOCITY_RATIO   = 1.5

# One-Euro filter parameters for keypoint smoothing
ONE_EURO_MIN_CUTOFF = 1.5   # Hz — higher = less lag, more noise
ONE_EURO_BETA       = 0.05  # speed coefficient — higher = less lag on fast motion
ONE_EURO_D_CUTOFF   = 1.0   # Hz — cutoff for derivative low-pass

KEYPOINT_MIN_CONFIDENCE = 0.4
# Strike-relevant joint indices (COCO): head, shoulders, elbows, wrists, hips, knees, ankles.
# Frame is valid if both fighters have all of these confident, rather than all 17 keypoints.
STRIKE_KEYPOINT_INDICES = [0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
# Core trunk joints (COCO): nose, shoulders, hips. These alone give the torso
# centre (velocity baseline), torso rectangle + head centre (contact gate as the
# defender) and body scale. The relaxed bar for open-range striking requires only
# these confident — the punching arm is gated per-limb inside detect_strikes, so a
# blurred wrist no longer discards the whole frame. Legs/ankles, routinely occluded
# in a standing broadcast view, are not required.
STRIKING_CORE_KEYPOINT_INDICES = [0, 5, 6, 11, 12]

# Contact distance ratios (fraction of defender torso-length scale)
# These gate ACCEPTANCE — whether a strike landed near the opponent at all.
HEAD_CONTACT_RATIO = 0.45
TORSO_CONTACT_RATIO = 0.55
LEG_CONTACT_RATIO = 0.45

# --- Head zone geometry (head-vs-body classification) ---
# Once a punch is accepted, head-vs-body is decided by the nearest anatomical
# REGION: distance outside the head circle vs distance outside the torso
# rectangle (0 when inside either). The head circle is centred on the confident
# head keypoints; its radius is derived from the ear-to-ear span when both ears
# are confident, else from body scale, then clamped to a sane band of the scale.
HEAD_RADIUS_EAR_FACTOR   = 0.80   # head radius ≈ ear-to-ear span × this
HEAD_RADIUS_SCALE_RATIO  = 0.25   # fallback head radius as fraction of torso scale
HEAD_RADIUS_MIN_RATIO    = 0.15   # clamp: min head radius (fraction of scale)
HEAD_RADIUS_MAX_RATIO    = 0.35   # clamp: max head radius (fraction of scale)
# When no head keypoint is confident, estimate the head centre this far above the
# shoulder midpoint (fraction of torso scale).
HEAD_ABOVE_SHOULDER_RATIO = 0.45

# Fight segmentation thresholds (in seconds — converted to frames at runtime using detected fps)
MIN_FIGHT_END_GAP_SECS    = 45.0   # seconds of low fighter presence to end fight
MIN_ROUND_GAP_SECS        = 20.0   # seconds of low engagement to split rounds
# Horizontal center distance threshold for engagement, as a fraction of frame
# width rather than an absolute pixel count — a wider/narrower crop or
# resolution shouldn't change what counts as "engaged". Calibrated against the
# old 800px threshold at JURICvsNOGUEIRA.mp4's 1280px width. See plan Stage 1
# step 4 — re-tune via the sweep (step 8) once labels exist.
ROUND_ENGAGEMENT_RATIO    = 0.625
MIN_ROUND_LENGTH_SECS     = 1.2    # minimum round duration in seconds
MIN_VALID_FRAME_RATIO     = 0.2    # minimum fraction of valid frames (ratio, not time)
MIN_FIGHT_DURATION_SECS   = 2.4    # minimum total fight duration in seconds

# Hysteresis windows for fight/round state machines (in seconds — converted at runtime)
FIGHT_PRESENCE_WINDOW_SECS  = 5.0  # sliding window for fight presence ratio
FIGHT_ENTER_RATIO           = 0.7  # ratio of both-present frames in window to enter fight
FIGHT_EXIT_RATIO            = 0.3  # ratio below which we begin counting fight-end gap
ROUND_ENGAGEMENT_WINDOW_SECS = 3.0 # sliding window for round engagement ratio
ROUND_ENGAGED_RATIO         = 0.6  # ratio of engaged frames in window to be in a round
ROUND_DISENGAGED_RATIO      = 0.2  # ratio below which we begin counting round-break gap

# Scoreboard overlay — ROI calibration (bottom-strip OCR)
SCOREBOARD_STRIP_Y_START = 0.62          # top of the bottom search strip (fraction of frame height)
# Broadcast overlays are intermittent — they vanish during replays, corner shots
# and ground close-ups, so a large fraction of any sample lands on frames with
# no overlay at all. Sampling has to be generous enough that a handful of hits
# is still enough to locate the ROI.
SCOREBOARD_STRIP_SEARCH_FRAMES = 40      # frames sampled during strip OCR calibration
SCOREBOARD_CAL_EDGE_SKIP_RATIO = 0.10    # skip this fraction at each end (walkout / post-fight graphics)
SCOREBOARD_CAL_VALIDATE_FRAMES = 8       # frames re-OCR'd to validate the candidate ROI
SCOREBOARD_CAL_MIN_MATCH_RATE  = 0.2     # candidate rejected below this hit rate
SCOREBOARD_ROI_PADDING = 20             # padding added around the detected ROI (px)

# Scoreboard overlay — OCR extraction
SCOREBOARD_OCR_SAMPLE_RATE_HZ = 2        # OCR samples per second
# EasyOCR line-level confidence floor. Deliberately low: EasyOCR's confidence
# on a scoreboard crop is not stable enough to carry a tight gate. Re-OCRing
# the same digits under a <=1px change to the calibrated ROI moves confidence
# by a median of 0.117 (max 0.433) — more than the gap between any two
# candidate values here — and 30% of correct readings straddle 0.7, so the old
# floor accepted or rejected a correct clock read based on where calibration
# happened to land the crop. Worse, the floor feeds back into that crop:
# calibration only unions boxes that clear it, so raising it shifts the ROI,
# which shifts the confidences again.
#
# What actually rejects a bad timer read is structural, not per-line: the
# seconds>59/minutes>59 range check in parsers.py, then the clock-intercept fit
# in fight_segmentation.py, which only trusts a round whose readings agree on a
# single intercept. Measured over 3529 sampled frames on the 3 videos with a
# readable overlay, dropping 0.7 -> 0.5 raised timer coverage 45%->68%,
# 18%->31% and 15%->28%; of the 696 newly admitted readings, ZERO were
# inconsistent with that fit.
SCOREBOARD_OCR_MIN_CONFIDENCE = 0.5      # EasyOCR line-level confidence floor
SCOREBOARD_OCR_UPSCALE = 3               # crop upscale factor before OCR
SCOREBOARD_SMOOTHING_WINDOW = 5          # sample window for round-number mode smoothing
SCOREBOARD_TIMER_MAX_BACKWARD_JUMP = 2   # max allowed timer increase (s) before rejection
SCOREBOARD_DEBUG_CROP_INTERVAL = 20      # save a debug crop every Nth sample

# Mid-round replay exclusion (plan Stage 1 step 3). A run of consecutive OCR
# samples rejected by the SCOREBOARD_TIMER_MAX_BACKWARD_JUMP check above is
# evidence the on-screen timer just jumped backward — i.e. a slow-motion
# replay, where velocity-based strike thresholds are meaningless. Require at
# least this many consecutive rejections (not a single one) before treating
# it as a replay rather than one noisy OCR read — at SCOREBOARD_OCR_SAMPLE_RATE_HZ,
# 3 samples ≈ 1.5s, short of what a real replay clip runs.
MIN_REPLAY_SAMPLES = 3

# Signal fusion weights (must sum to 1.0)
FUSION_WEIGHT_OCR = 0.70
FUSION_WEIGHT_DETECTION = 0.20
FUSION_WEIGHT_ENGAGEMENT = 0.10

# OCR signal snap: snap round boundary if within this many seconds of an OCR transition
OCR_BOUNDARY_SNAP_SECS = 1.5   # converted to frames at runtime using detected fps

# --- Round clock (scoreboard timer → round boundaries) ---------------------
# The on-screen round clock is deterministic: it moves one second per second of
# video, so its slope against frame number is known a priori (-1/fps counting
# down). Only the intercept has to be fitted, which is why a single clean
# reading already places a round and two verify it — far cheaper than the
# round *number*, which many overlays render as a bare digit or omit entirely.
ROUND_CLOCK_STANDARD_LENGTHS_SECS = (180.0, 300.0)  # 3-minute and 5-minute rounds
ROUND_CLOCK_MIN_SAMPLES           = 3     # timer readings needed to trust a fitted round
ROUND_CLOCK_MAX_RESIDUAL_SECS     = 4.0   # reading discarded when it deviates from the fit by more
ROUND_CLOCK_RESET_MIN_JUMP_SECS   = 30.0  # upward clock jump that starts a new round
ROUND_CLOCK_LENGTH_TOLERANCE_SECS = 20.0  # slack when snapping observed max to a standard length
# A round backed by this many mutually-consistent clock readings is solidly
# corroborated and needs no human confirmation. This, not raw sample coverage,
# is what makes a fit trustworthy: an overlay visible for only 8% of a fight
# still pins its round exactly when every one of those readings agrees.
ROUND_CLOCK_HEALTHY_SUPPORT = 10

# Round digit sits in its own box beside the timer on essentially every MMA
# overlay (e.g. "NAZHAND | 1 | 03:50 | STAROPOLI"), so it is found by position
# relative to the timer box rather than by a text prefix. Bands are expressed
# relative to the timer box so they hold at any resolution or overlay scale.
ROUND_BOX_MAX_VERTICAL_OFFSET_RATIO = 0.6  # centre offset, as a fraction of timer box height
ROUND_BOX_MAX_HORIZONTAL_GAP_RATIO  = 1.5  # edge gap, as a multiple of timer box width

# --- Round structure plausibility -----------------------------------------
# Applied after segmentation as a physical backstop: these describe how MMA
# actually behaves, so they hold even when OCR contributed nothing. A non-final
# round below MIN_INTERIOR_ROUND_SECS is a walkout or a detection dropout, not a
# round — only the *last* round may be short, because only the last round can
# end in a finish.
MIN_INTERIOR_ROUND_SECS = 60.0   # shortest believable non-final round
MIN_ROUND_BREAK_SECS    = 30.0   # real between-round breaks run ~60s

# Round numbers only ever increase, and never skip. A change that does not hold
# for this many consecutive samples is OCR flapping, not a round boundary.
MIN_ROUND_NUMBER_RUN_SAMPLES = 3

# --- Segmentation confidence ----------------------------------------------
# Whether a round list needs human confirmation is decided by ROUND_CLOCK_
# HEALTHY_SUPPORT above (how many mutually-consistent readings back each round),
# not by how often the overlay happened to be on screen. OCR coverage is still
# reported in the quality block as a diagnostic.

# --- Fighter tracking (FighterTracker) ---
TRACK_MAX_FIGHTERS       = 2
TRACK_IOU_WEIGHT         = 0.6   # fraction of cost matrix from IoU term
TRACK_DISTANCE_WEIGHT    = 0.4   # fraction of cost matrix from centroid-distance term
TRACK_MAX_MISSING_SECS   = 0.6   # 30 frames @ 50fps — time a slot coasts before being pruned
CLINCH_IOU_THRESHOLD     = 0.3   # inter-fighter IoU above which velocity is frozen

# --- Glove-tape corner assignment ---
# Both were absolute pixels — a camera zoomed further from the cage shrinks a
# fighter's apparent glove/frame-edge geometry in pixels for the same
# real-world size, same class of bug as DISTANCE_GRAPPLING_RATIO etc. above.
# See plan Stage 1 step 4. Calibrated against JURICvsNOGUEIRA.mp4's measured
# median torso scale (~178px) and frame width (1280px) to preserve the old
# constants' apparent behaviour as a starting point — re-tune via the sweep
# (Stage 1 step 8) once labels exist, not by eyeballing one video.
TAPE_PATCH_RATIO          = 0.10   # base wrist-crop half-side as a fraction of fighter scale (≈18px at 178px scale)
WRIST_EDGE_MARGIN_RATIO   = 0.008  # skip wrist within this fraction of frame width of the border (≈10px at 1280px width)
# The crop must sit on the glove, not the forearm. At 0.225 the box spanned the
# whole forearm plus background, so what it actually counted was skin and canvas:
# on every fight in runs/upload_pipeline.log BOTH tracks came back overwhelmingly
# "red", and 29% of a whole JURICvsNOGUEIRA frame classified as red tape. The
# floors below are what make the difference — skin sits at roughly S 30-140 and
# hue 0-25, so an S floor of 80 with a red band reaching hue 10 admits it wholesale.
TAPE_MIN_SATURATION      = 150   # HSV S floor (0-255) — above the skin band, keeps saturated tape
TAPE_MIN_VALUE           = 60    # HSV V floor (0-255) — drops black / dark pixels
RED_HUE_HIGH1            = 6     # red band 1: 0 .. HIGH1  (OpenCV hue 0-180)
RED_HUE_LOW2             = 174   # red band 2: LOW2 .. 180
BLUE_HUE_LOW             = 100
BLUE_HUE_HIGH            = 132
# Tape counts are compared BETWEEN the two fighters within a single frame and
# aggregated as one vote per frame (see _paired_tape_vote). Never sum raw pixel
# counts over a fight: a fighter who spends longer in close-up contributes more
# pixels for reasons that have nothing to do with colour, which is exactly how
# fight 42 was assigned backwards (22.8M vs 28.2M "red" pixels, both skin).
CORNER_TAPE_VOTE_MIN_MARGIN = 0.010  # min |Δ net coverage| between fighters for a frame to vote
CORNER_MIN_TAPE_VOTES       = 25     # min voting frames before the paired tape vote is trusted

# --- Appearance-anchored per-frame corner assignment ---
# Torso / shorts histogram sampling
TORSO_HIST_BINS               = 16    # hue histogram bins (OpenCV hue 0–180)
TORSO_MIN_SATURATION          = 50    # HSV S floor for torso pixels
TORSO_MIN_VALUE               = 40    # HSV V floor for torso pixels
TORSO_SAMPLE_MIN_PIXELS       = 150   # min pixels to trust a torso histogram

# Template bootstrap + per-frame assignment
CORNER_CLEAN_FRAME_MIN_TAPE   = 8     # per-frame combined tape px to qualify as a clean frame
CORNER_TEMPLATE_MIN_SEPARATION = 0.15 # separation below this → distrust appearance, use legacy
# Net tape coverage gap (as a fraction of the sampled glove crop) at which the
# two fighters' colours are considered fully diagnostic. The separation score
# saturates here, so it reads as "how far apart are these two, in units of a
# decisive split" rather than the old magnitude comparison — which scored a
# perfect red-vs-blue split as ZERO separation and a no-evidence slot as 0.49.
# Set near the low end of the measured range (0.187 NAZHAND, 0.415 JURIC, 0.464
# MILIDRAGOVIC) so the term still discriminates instead of saturating on every
# fight, which is what a smaller value did — leaving the threshold inert.
CORNER_TAPE_SEPARATION_FULL   = 0.30
CORNER_TAPE_WEIGHT            = 0.6   # tape-cue weight in combined distance (sums to 1 with hist)
CORNER_HIST_WEIGHT            = 0.4   # torso-histogram weight
CORNER_HYSTERESIS_WEIGHT      = 0.5   # penalty added to any assignment that flips a slot's label
CORNER_SWAP_CONFIRM_SECS      = 0.08  # 4 frames @ 50fps — a flip must persist this long to be confirmed

# --- Body-scale geometry (models/geometry.py) ---
# get_fighter_scale's foreshortening fallback: below this fraction of shoulder
# width, the shoulder→hip torso length is treated as degenerate (camera angle
# compresses it) rather than genuinely short, and the shoulder-width fallback
# is used instead. Was an absolute `torso_len < 20px` — see plan Stage 1 step 4.
TORSO_SCALE_MIN_RATIO = 0.5

# --- Grappling frame-validity relaxation ---
GRAPPLING_MIN_VISIBLE_KEYPOINTS = 6   # min confident strike-relevant joints for PARTIAL validity