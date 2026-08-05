export interface Fight {
  id: number;
  video_path: string;
  fps: number;
  width: number;
  height: number;
  created_at: string;
  state: string;
  red_fighter_id: number | null;
  blue_fighter_id: number | null;
  red_fighter_name: string | null;
  blue_fighter_name: string | null;
}

export const STATE_PROGRESS: Record<string, number> = {
  queued: 0,
  detecting: 10,
  tracking: 35,
  pose: 45,
  corners: 70,
  scoreboard: 78,
  segmenting: 85,
  analyzing: 92,
  completed: 100,
  failed: 0,
};

export const STATE_LABELS: Record<string, string> = {
  queued: 'Queued',
  detecting: 'Detecting fighters',
  tracking: 'Tracking fighters',
  pose: 'Analyzing poses',
  corners: 'Identifying corners',
  scoreboard: 'Reading scoreboard',
  segmenting: 'Segmenting rounds',
  analyzing: 'Processing fight',
  completed: 'Completed',
  failed: 'Failed',
};
