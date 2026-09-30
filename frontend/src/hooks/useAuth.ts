import { createContext, useContext } from 'react';
import type { Role, User } from '../types/User';

export interface AuthState {
  user: User;
  can: (minRole: Role) => boolean;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);

/** Only usable under AuthProvider, which renders children only once signed in. */
export function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (auth == null) throw new Error('useAuth must be used inside AuthProvider');
  return auth;
}
