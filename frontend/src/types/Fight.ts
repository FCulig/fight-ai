export interface Fight {
  id: number;
  video_path: string;
  fps: number;
  width: number;
  height: number;
  created_at: string;
  state: string;
  labeled_at: string | null;
  reported_frames: number | null;
  decoded_frames: number | null;
  segmentation_needs_review: boolean;
  segmentation_review_reason: string | null;
  red_fighter_id: number | null;
  blue_fighter_id: number | null;
  red_fighter_name: string | null;
  blue_fighter_name: string | null;
}

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
 * fight_segmentation.py `_review_verdict`.
 */
export const needsRoundReview = (fight: Fight): boolean =>
  fight.segmentation_needs_review === true;
