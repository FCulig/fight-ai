import type { CSSProperties, ReactNode } from 'react';

/**
 * The app's page background: off-black `--bg-base` with ink text. In the app,
 * frontend/src/index.css puts this on :root; wrap a design's root in AppSurface so
 * it renders the same on any host page. Fightlytics is dark-only.
 */
export default function AppSurface({ children, padding = 24, style }: {
  children?: ReactNode;
  /** Inner padding in px. Use 0 for full-bleed screens. */
  padding?: number;
  style?: CSSProperties;
}) {
  return (
    <div style={{ background: 'var(--bg-base)', color: 'var(--text-primary)', padding, minHeight: '100%', ...style }}>
      {children}
    </div>
  );
}
