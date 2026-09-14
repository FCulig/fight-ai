export interface CornerSwapSpan {
  frame: number;
  end_frame: number | null;
}

/** Is `frame` inside one of these confirmed (or still-open) corner_swap spans?
 * `end_frame == null` means the span is still open — treated as running to
 * the end of the video. Shared by FighterOverlay (box/skeleton colour) and
 * describeEvent (fighter-name reconstruction) so both apply the same
 * correction to the same stretch of frames. */
export function isFrameSwapped(frame: number, spans: CornerSwapSpan[]): boolean {
  return spans.some(s => frame >= s.frame && (s.end_frame == null || frame <= s.end_frame));
}
