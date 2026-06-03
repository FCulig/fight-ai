export interface Fight {
  id: number;
  video_path: string;
  fps: number;
  width: number;
  height: number;
  created_at: string;
  processed: boolean;
  processed_at: string | null;
}
