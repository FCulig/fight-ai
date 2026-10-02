import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { createUser, fetchUsers, updateUser } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { useWindowWidth } from '../hooks/useWindowWidth';
import { ROLES } from '../types/User';
import type { Role, User } from '../types/User';

const ROLE_HELP: Record<Role, string> = {
  viewer: 'Watch fights and see accuracy',
  labeller: 'Also annotate fights and QA training data',
  admin: 'Also upload, delete fights, run scoring and manage users',
};

const fieldStyle: React.CSSProperties = {
  boxSizing: 'border-box', background: 'rgba(0,0,0,0.35)',
  border: '1px solid var(--border-glass)', borderRadius: 6,
  padding: '9px 11px', color: 'var(--text-primary)', fontSize: 13, fontWeight: 500, outline: 'none',
  fontFamily: 'inherit',
};

const byEmail = (a: User, b: User) => a.email.localeCompare(b.email);

const formatLogin = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'Never';

export default function Users() {
  const { user: me } = useAuth();
  const isMobile = useWindowWidth() < 640;
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<Role>('labeller');
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    fetchUsers()
      .then((list) => setUsers([...list].sort(byEmail)))
      .catch((err) => setError(err instanceof Error ? err.message : 'Unknown error'))
      .finally(() => setLoading(false));
  }, []);

  const change = async (target: User, patch: { role?: Role; is_active?: boolean }) => {
    setError(null);
    setSavingId(target.id);
    try {
      const updated = await updateUser(target.id, patch);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setSavingId(null);
    }
  };

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setAdding(true);
    try {
      const created = await createUser(email.trim(), role);
      setUsers((prev) => [...prev, created].sort(byEmail));
      setEmail('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setAdding(false);
    }
  };

  return (
    <div style={{ position: 'relative', zIndex: 1, maxWidth: 1100, margin: '0 auto', padding: isMobile ? '18px 16px 70px' : '22px 30px 90px', width: '100%' }}>
      <div style={{ marginBottom: 22 }}>
        <span className="eyebrow">Admin</span>
        <h1 className="font-display" style={{ fontSize: isMobile ? 32 : 'clamp(36px, 4.6vw, 60px)', lineHeight: 0.94, margin: '10px 0 0', color: 'var(--text-primary)' }}>
          Users.
        </h1>
        <p style={{ margin: '10px 0 0', fontSize: 13.5, fontWeight: 500, color: 'var(--text-muted)', maxWidth: 640 }}>
          Anyone who signs in with Google joins as a viewer. Raise their role here, or add an email
          before their first sign-in so they land with the right role.
        </p>
      </div>

      {error && <div role="alert" style={{ fontSize: 13, color: 'var(--red-500)', marginBottom: 14 }}>{error}</div>}

      <form onSubmit={add} className="glass" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 12, padding: 18, marginBottom: 18 }}>
        <label style={{ flex: '1 1 260px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="label">Email</span>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@example.com" style={fieldStyle} />
        </label>
        <label style={{ flex: '0 1 180px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="label">Role</span>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)} style={fieldStyle}>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        <button type="submit" className="btn-primary" disabled={adding || !email.trim()} style={{ height: 38, padding: '0 18px', fontSize: 13, fontWeight: 600, opacity: adding || !email.trim() ? 0.5 : 1 }}>
          Add user
        </button>
        <p style={{ flexBasis: '100%', margin: 0, fontSize: 12, fontWeight: 500, color: 'var(--text-muted)' }}>
          {role}: {ROLE_HELP[role]}.
        </p>
      </form>

      <div className="glass" style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: 'left' }}>
              {['Email', 'Name', 'Role', 'Access', 'Last sign-in'].map((h) => (
                <th key={h} className="label" style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-glass)', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={5} style={{ padding: 16, color: 'var(--text-muted)', fontWeight: 500 }}>Loading…</td></tr>
            )}
            {users.map((u) => {
              const isMe = u.id === me.id;
              const busy = savingId === u.id;
              return (
                <tr key={u.id} style={{ borderBottom: '1px solid var(--border-subtle)', opacity: u.is_active ? 1 : 0.55 }}>
                  <td style={{ padding: '12px 16px', fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>
                    {u.email}
                    {isMe && <span className="pill active" style={{ marginLeft: 8, padding: '2px 8px', cursor: 'default' }}>You</span>}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>{u.name ?? '—'}</td>
                  <td style={{ padding: '12px 16px' }}>
                    {isMe ? (
                      <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>{u.role}</span>
                    ) : (
                      <select
                        value={u.role}
                        disabled={busy}
                        onChange={(e) => change(u, { role: e.target.value as Role })}
                        aria-label={`Role for ${u.email}`}
                        style={{ ...fieldStyle, padding: '6px 9px' }}
                      >
                        {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                    {isMe ? (
                      <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>Active</span>
                    ) : (
                      <button
                        type="button"
                        className="btn-glass"
                        disabled={busy}
                        onClick={() => change(u, { is_active: !u.is_active })}
                        style={{ padding: '6px 12px', fontSize: 12, fontWeight: 600 }}
                      >
                        {u.is_active ? 'Disable' : 'Enable'}
                      </button>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{formatLogin(u.last_login_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
