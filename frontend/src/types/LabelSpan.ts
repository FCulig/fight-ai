export type SpanKind = 'round' | 'corner_swap' | 'excluded';

export interface LabelSpan {
  id: number;
  fight_id: number;
  kind: SpanKind;
  start_frame: number;
  end_frame: number | null; // null while a start/end toggle span is still open
  value: string | null;
  created_at: string;
}
