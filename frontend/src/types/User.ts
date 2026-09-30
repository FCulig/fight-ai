/** Mirrors ROLES in backend/app/models/user.py, lowest to highest. The backend
 * enforces every role check; the frontend only hides controls. */
export const ROLES = ['viewer', 'labeller', 'admin'] as const;
export type Role = typeof ROLES[number];

export interface User {
  id: number;
  email: string;
  name: string | null;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export const hasRole = (user: User | null, minRole: Role): boolean =>
  user != null && ROLES.indexOf(user.role) >= ROLES.indexOf(minRole);
