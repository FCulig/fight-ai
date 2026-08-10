export interface Event {
  id: number;
  frame: number;
  description: string;
  fight_id: number;
  fighter_id: number | null;
  action: string | null;
  success: boolean | null;
}