import { useState } from 'react';
import type { FormEvent } from 'react';
import { joinWaitlist, loginUrl } from '../services/api';

// Set by the backend's /api/auth/callback when it can't start a session.
const AUTH_ERRORS: Record<string, string> = {
  failed: "Google sign-in didn't complete. Try again.",
  unverified: "That Google account doesn't have a verified email address.",
  disabled: 'Your access has been disabled. Ask an admin to turn it back on.',
  not_invited: "That Google account isn't invited yet. Join the waitlist below and we'll email you when Fightlytics opens to everyone.",
};

interface SignInProps {
  /** /api/auth/me answered 403: the session belongs to a disabled user. */
  disabled?: boolean;
  error?: string;
}

/** Rendered by AuthProvider in place of the app, at whatever URL the visitor
 * opened, so after sign-in they land back on the same page. Sign-in is
 * invite-only, so it also offers everyone else the waitlist. */
export default function SignIn({ disabled = false, error }: SignInProps) {
  const params = new URLSearchParams(window.location.search);
  const authError = params.get('auth_error');
  params.delete('auth_error');
  const qs = params.toString();
  const next = window.location.pathname + (qs ? `?${qs}` : '');

  const message = error
    ?? (disabled ? AUTH_ERRORS.disabled : null)
    ?? (authError ? AUTH_ERRORS[authError] ?? AUTH_ERRORS.failed : null);
  // Not being invited is the expected answer for most visitors, not a failure.
  const isError = authError !== 'not_invited' || error != null || disabled;

  return (
    <div style={{ position: 'relative', zIndex: 1, minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div className="glass" style={{ width: '100%', maxWidth: 400, padding: '36px 28px', textAlign: 'center' }}>
        {/* height/padding reset App.css's leftover Vite-template `.logo` sizing */}
        <span className="logo" style={{ fontSize: 30, height: 'auto', padding: 0 }}>Fightlytics</span>
        <p style={{ margin: '14px 0 26px', fontSize: 13.5, fontWeight: 500, color: 'var(--text-muted)' }}>
          Sign in to review fights and labels.
        </p>
        {message && (
          <div role="alert" style={{ fontSize: 13, fontWeight: 500, color: isError ? 'var(--red-500)' : 'var(--text-secondary)', marginBottom: 20 }}>
            {message}
          </div>
        )}
        <a
          className="btn-primary"
          href={loginUrl(next)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, height: 42, padding: '0 22px', fontSize: 13.5, fontWeight: 600, textDecoration: 'none' }}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>login</span>
          Sign in with Google
        </a>
        {!disabled && <Waitlist />}
      </div>
    </div>
  );
}

// How long the form's `wl-out` fade runs before the success state replaces it.
const FORM_EXIT_MS = 200;

type Phase = 'form' | 'leaving' | 'joined';

function Waitlist() {
  const [email, setEmail] = useState('');
  const [sending, setSending] = useState(false);
  const [phase, setPhase] = useState<Phase>('form');
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      await joinWaitlist(email.trim());
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reduced) {
        setPhase('joined');
      } else {
        setPhase('leaving');
        setTimeout(() => setPhase('joined'), FORM_EXIT_MS);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSending(false);
    }
  };

  const blocked = sending || phase !== 'form' || !email.trim();

  return (
    <div style={{ marginTop: 28, paddingTop: 24, borderTop: '1px solid var(--border-subtle)', textAlign: 'left' }}>
      {phase === 'joined' ? (
        <div role="status" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '4px 0 2px' }}>
          <span className="wl-badge" aria-hidden="true">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="var(--green-500)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="24" cy="24" r="22" pathLength={1} />
              <path d="M15 24.5l6 6 12-13" pathLength={1} />
            </svg>
          </span>
          <div className="font-display anim-fade-up anim-delay-3" style={{ marginTop: 14, fontSize: 20, color: 'var(--text-primary)' }}>
            You're on the list
          </div>
          <p className="anim-fade-up anim-delay-3" style={{ margin: '6px 0 0', fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)', overflowWrap: 'anywhere', animationDelay: '0.38s' }}>
            We'll email {email.trim()} when Fightlytics opens to everyone.
          </p>
        </div>
      ) : (
        <div className={phase === 'leaving' ? 'wl-out' : undefined}>
          <span className="label">Not invited yet?</span>
          <p style={{ margin: '8px 0 12px', fontSize: 13, fontWeight: 500, color: 'var(--text-muted)' }}>
            Fightlytics is invite-only for now. Leave your email and we'll let you know when it opens to everyone.
          </p>
          <form onSubmit={submit} style={{ display: 'flex', gap: 8 }}>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              aria-label="Email for the waitlist"
              style={{
                flex: 1, minWidth: 0, boxSizing: 'border-box', background: 'rgba(0,0,0,0.35)',
                border: '1px solid var(--border-glass)', borderRadius: 'var(--r-ctl)', padding: '9px 11px',
                color: 'var(--text-primary)', fontSize: 13, fontWeight: 500, outline: 'none', fontFamily: 'inherit',
              }}
            />
            <button
              type="submit"
              className="btn-glass"
              disabled={blocked}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0 14px', fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', opacity: blocked && !sending ? 0.5 : 1 }}
            >
              {sending && <span className="material-symbols-outlined wl-spin" aria-hidden="true" style={{ fontSize: 16 }}>progress_activity</span>}
              {sending ? 'Adding…' : 'Notify me'}
            </button>
          </form>
          {error && <div role="alert" style={{ marginTop: 8, fontSize: 12.5, fontWeight: 500, color: 'var(--red-500)' }}>{error}</div>}
        </div>
      )}
    </div>
  );
}
