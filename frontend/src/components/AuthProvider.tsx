import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { fetchMe, logout } from '../services/api';
import type { MeResult } from '../services/api';
import { AuthContext } from '../hooks/useAuth';
import type { AuthState } from '../hooks/useAuth';
import { hasRole } from '../types/User';
import SignIn from '../pages/SignIn';

/** Gates the whole app on /api/auth/me: children render only when signed in. */
export default function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<MeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMe()
      .then(setMe)
      .catch((err) => setError(err instanceof Error ? err.message : 'Unknown error'));
  }, []);

  const auth = useMemo<AuthState | null>(() => {
    if (me?.status !== 'signed_in') return null;
    return {
      user: me.user,
      can: (minRole) => hasRole(me.user, minRole),
      signOut: async () => {
        await logout();
        setMe({ status: 'signed_out' });
      },
    };
  }, [me]);

  if (error) return <SignIn error={error} />;
  if (me == null) return null;
  if (auth == null) return <SignIn disabled={me.status === 'disabled'} />;
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}
