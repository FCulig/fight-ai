import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import type { Role } from '../types/User';

/** Keeps a deep link from opening a page whose every action would 403. */
export default function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { can } = useAuth();
  return can(role) ? children : <Navigate to="/" replace />;
}
