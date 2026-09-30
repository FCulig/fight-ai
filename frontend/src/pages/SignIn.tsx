import { loginUrl } from '../services/api';

// Set by the backend's /api/auth/callback when it can't start a session.
const AUTH_ERRORS: Record<string, string> = {
  failed: "Google sign-in didn't complete. Try again.",
  unverified: "That Google account doesn't have a verified email address.",
  disabled: 'Your access has been disabled. Ask an admin to turn it back on.',
};

interface SignInProps {
  /** /api/auth/me answered 403: the session belongs to a disabled user. */
  disabled?: boolean;
  error?: string;
}

/** Rendered by AuthProvider in place of the app, at whatever URL the visitor
 * opened, so after sign-in they land back on the same page. */
export default function SignIn({ disabled = false, error }: SignInProps) {
  const params = new URLSearchParams(window.location.search);
  const authError = params.get('auth_error');
  params.delete('auth_error');
  const qs = params.toString();
  const next = window.location.pathname + (qs ? `?${qs}` : '');

  const message = error
    ?? (disabled ? AUTH_ERRORS.disabled : null)
    ?? (authError ? AUTH_ERRORS[authError] ?? AUTH_ERRORS.failed : null);

  return (
    <div style={{ position: 'relative', zIndex: 1, minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div className="glass" style={{ width: '100%', maxWidth: 400, padding: '36px 28px', textAlign: 'center' }}>
        {/* height/padding reset App.css's leftover Vite-template `.logo` sizing */}
        <span className="logo" style={{ fontSize: 30, height: 'auto', padding: 0 }}>Fightlytics</span>
        <p style={{ margin: '14px 0 26px', fontSize: 13.5, fontWeight: 600, color: 'var(--text-muted)' }}>
          Sign in to review fights and labels.
        </p>
        {message && (
          <div role="alert" style={{ fontSize: 13, fontWeight: 600, color: 'var(--red-500)', marginBottom: 20 }}>
            {message}
          </div>
        )}
        <a
          className="btn-primary"
          href={loginUrl(next)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, height: 42, padding: '0 22px', fontSize: 13.5, fontWeight: 700, textDecoration: 'none' }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>login</span>
          Sign in with Google
        </a>
      </div>
    </div>
  );
}
