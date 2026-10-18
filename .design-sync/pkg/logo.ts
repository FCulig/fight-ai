// landing/app/logo.jsx is a classic script (in-browser Babel, no modules): it assigns its
// components to window. Import it for that side effect and re-export them, so the brand
// marks ship from the landing page's own source instead of a copy.
import '../../landing/app/logo.jsx';

type Fc<P> = (props: P) => unknown;
const w = window as unknown as Record<string, unknown>;

export const GloveMark = w.GloveMark as Fc<{ size?: number; mono?: boolean }>;
export const GloveGlyph = w.GloveGlyph as Fc<{ size?: number }>;
export const GloveWatermark = w.GloveWatermark as Fc<{ className?: string; style?: Record<string, unknown> | null }>;
export const LogoLockup = w.LogoLockup as Fc<{ size?: number; wordSize?: number; sub?: unknown }>;
export const LogoStack = w.LogoStack as Fc<{ size?: number; wordSize?: number; sub?: unknown }>;
