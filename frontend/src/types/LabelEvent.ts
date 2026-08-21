export interface LabelEvent {
  id: number;
  frame: number;
  description: string;
  fight_id: number;
  corner: number | null; // 0=red 1=blue; null for state marks
  action: string | null;
  target: string | null;
  success: boolean | null;
  labeler: string | null;
  created_at: string;
}
