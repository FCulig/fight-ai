export type EventSource = 'prediction' | 'label';
export type EventKind = 'point' | 'round' | 'corner_swap' | 'excluded';

export interface Event {
  id: number;
  fight_id: number;
  source: EventSource;
  kind: EventKind;
  frame: number; // point: the frame. range kinds (round/corner_swap/excluded): the start frame.
  end_frame: number | null; // null for kind='point'; for range kinds, null = an open start/end toggle still in progress
  description: string | null; // required for kind='point'; null for range kinds
  fighter_id: number | null; // prediction-only resolved fighter identity
  corner: number | null; // label-only track-slot (0=red/1=blue) — a box index, not a resolved person
  action: string | null;
  target: string | null; // head/body/leg — label-only today
  success: boolean | null;
  state: string | null; // STRIKING/CLINCH/GROUND on a prediction state-change row
  value: string | null; // round number / exclusion reason — range-kind-only
  labeler: string | null;
  created_at: string;
  is_verified: boolean | null; // Training Data QA verdict — label point events only
}
