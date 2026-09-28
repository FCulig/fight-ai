export interface Fight {
  id: number;
  video_path: string;
  fps: number;
  width: number;
  height: number;
  created_at: string;
  state: string;
  labeled_at: string | null;
  purpose: string;
  reported_frames: number | null;
  decoded_frames: number | null;
  segmentation_needs_review: boolean;
  segmentation_review_reason: string | null;
  red_fighter_id: number | null;
  blue_fighter_id: number | null;
  red_fighter_name: string | null;
  blue_fighter_name: string | null;
}

/**
 * What the video is for. Set once at upload from the Upload dialog and never
 * written again — the AI pipeline does not touch it, so a `reference` fight
 * keeps its identity when it is re-run to produce predictions to score against.
 */
export type FightPurpose = 'training_data' | 'reference' | 'ai_labeled';

export const PURPOSE_LABELS: Record<FightPurpose, string> = {
  training_data: 'Training data',
  reference: 'Reference',
  ai_labeled: 'AI labeled',
};

/**
 * Deliberately avoids --f-red/--f-blue (corner colours — a badge in either
 * would read as "red corner"), --red-500 (error) and #f59e0b (the
 * rounds-unverified warning). Violet is new to the palette. Colour is a
 * redundant channel here anyway: every badge carries its text label.
 */
export const PURPOSE_COLORS: Record<FightPurpose, string> = {
  training_data: 'var(--green-500)',
  reference: '#a78bfa', // violet — no existing semantic
  ai_labeled: 'var(--accent)', // the AI accent
};

export const PURPOSE_ICONS: Record<FightPurpose, string> = {
  training_data: 'model_training',
  reference: 'verified',
  ai_labeled: 'auto_awesome',
};

export const STATE_PROGRESS: Record<string, number> = {
  validating: 0,
  queued: 0,
  detecting: 10,
  tracking: 35,
  pose: 45,
  corners: 70,
  scoreboard: 78,
  segmenting: 85,
  analyzing: 92,
  completed: 100,
  labeling_in_progress: 96,
  labeling_complete: 100,
  failed: 0,
  invalid: 0,
};

export const STATE_LABELS: Record<string, string> = {
  validating: 'Validating video',
  queued: 'Queued',
  detecting: 'Detecting fighters',
  tracking: 'Tracking fighters',
  pose: 'Analyzing poses',
  corners: 'Identifying corners',
  scoreboard: 'Reading scoreboard',
  segmenting: 'Segmenting rounds',
  analyzing: 'Processing fight',
  completed: 'Completed',
  labeling_in_progress: 'Labeling in progress',
  labeling_complete: 'Labeling complete',
  failed: 'Failed',
  invalid: 'Invalid video',
};

/** States where the pipeline has stopped moving on its own — no more live SSE updates expected. */
export const TERMINAL_STATES = new Set([
  'completed',
  'failed',
  'invalid',
  'labeling_in_progress',
  'labeling_complete',
]);

/** Fight has real analysis data (events/frames/rounds) ready to review in the Player. */
export const isFightViewable = (state: string): boolean =>
  state === 'completed' || state === 'labeling_complete';

/** Fight has fighter_frames/rounds written and is waiting for the user to manually tag events. */
export const isLabelingReady = (state: string): boolean =>
  state === 'labeling_in_progress';

/** Source video failed full-decode validation and was never queued for processing. */
export const isInvalid = (state: string): boolean => state === 'invalid';

/**
 * Segmentation could not corroborate its own round list against the scoreboard,
 * so the rounds are a detection-only guess and should be confirmed by hand.
 * The pipeline sets this at segmentation time — see ai/video_processing/
 * fight_segmentation.py `_review_verdict`. Once labeling has been finished,
 * every round has a hand-confirmed label-span (finish-labeling requires it), so
 * the guess has already been confirmed and the warning no longer applies.
 * `labeled_at` covers the re-opened case: editing a labelled fight puts it back
 * in `labeling_in_progress`, but its rounds are still confirmed.
 */
export const needsRoundReview = (fight: Fight): boolean =>
  fight.segmentation_needs_review === true
  && fight.state !== 'labeling_complete'
  && fight.labeled_at === null;

/**
 * A hand-labelled fight that has been finished and can be re-opened in
 * Annotate for editing (POST /fights/{id}/reopen-labeling). `ai_labeled`
 * fights never reach `labeling_complete`, so the state check alone excludes
 * them — their events are predictions, which Annotate can't edit.
 */
export const isLabelEditable = (fight: Fight): boolean =>
  fight.state === 'labeling_complete';

/** A previously finished fight that has been re-opened in Annotate for editing. */
export const isEditingLabels = (fight: Fight): boolean =>
  fight.state === 'labeling_in_progress' && fight.labeled_at !== null;
