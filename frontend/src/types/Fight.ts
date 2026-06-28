export interface Fight {
  id: number;
  video_path: string;
  fps: number;
  width: number;
  height: number;
  created_at: string;
  processed: boolean;
  processed_at: string | null;
  red_fighter_id: number | null;
  blue_fighter_id: number | null;
}
