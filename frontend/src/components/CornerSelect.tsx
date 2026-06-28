import { useState, useEffect, useRef, useCallback } from 'react';
import type { Fighter } from '../types/Fighter';
import { fetchFighters, createFighter } from '../services/api';

interface CornerSelectProps {
  corner: string;
  dotColor: string;
  value: Fighter | null;
  exclude: number | null;
  onChange: (fighter: Fighter | null) => void;
  disabled?: boolean;
}

const fighterFull = (f: Fighter) => `${f.first_name} ${f.last_name}`;
const fighterInitials = (f: Fighter) =>
  `${f.first_name[0] ?? ''}${f.last_name[0] ?? ''}`.toUpperCase();

const fieldStyle: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', background: 'rgba(0,0,0,0.35)',
  border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8,
  padding: '9px 11px', color: '#f1f5f9', fontSize: 13, fontWeight: 600, outline: 'none',
  fontFamily: 'inherit',
};

export default function CornerSelect({ corner, dotColor, value, exclude, onChange, disabled }: CornerSelectProps) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [creating, setCreating] = useState(false);
  const [nf, setNf] = useState({ first: '', last: '', nick: '' });
  const [fighters, setFighters] = useState<Fighter[]>([]);
  const [loadingFighters, setLoadingFighters] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
        setCreating(false);
      }
    };
    window.addEventListener('mousedown', onDoc);
    return () => window.removeEventListener('mousedown', onDoc);
  }, [open]);

  useEffect(() => {
    if (open && !creating && searchRef.current) searchRef.current.focus();
  }, [open, creating]);

  const searchFighters = useCallback((query: string) => {
    setLoadingFighters(true);
    fetchFighters(query || undefined)
      .then(setFighters)
      .catch(() => {})
      .finally(() => setLoadingFighters(false));
  }, []);

  useEffect(() => {
    if (!open) return;
    searchFighters('');
  }, [open, searchFighters]);

  const onSearchChange = (val: string) => {
    setQ(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => searchFighters(val.trim()), 250);
  };

  const filtered = fighters.filter(f => f.id !== exclude);

  const pick = (f: Fighter) => {
    onChange(f);
    setOpen(false);
    setCreating(false);
    setQ('');
  };

  const beginCreate = () => {
    const parts = q.trim().split(/\s+/);
    setNf({ first: parts[0] || '', last: parts.slice(1).join(' ') || '', nick: '' });
    setCreating(true);
  };

  const commitCreate = async () => {
    const first = nf.first.trim();
    const last = nf.last.trim();
    if (!first || !last) return;
    try {
      const fighter = await createFighter({
        first_name: first,
        last_name: last,
        nickname: nf.nick.trim() || undefined,
      });
      pick(fighter);
      setNf({ first: '', last: '', nick: '' });
    } catch {
      // stay in create view on error
    }
  };

  return (
    <div ref={wrapRef} style={{ position: 'relative' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8,
        fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'rgba(255,255,255,0.28)',
      }}>
        <span style={{ width: 9, height: 9, borderRadius: '50%', background: dotColor, boxShadow: `0 0 8px ${dotColor}` }} />
        {corner}
      </div>

      <button
        type="button"
        onClick={() => !disabled && setOpen(o => !o)}
        style={{
          width: '100%', textAlign: 'left', cursor: disabled ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', gap: 11, padding: '11px 12px',
          borderRadius: 11, background: 'rgba(0,0,0,0.30)',
          border: `1.5px solid ${open ? 'rgba(0,218,243,0.6)' : 'rgba(255,255,255,0.07)'}`,
          boxShadow: open ? '0 0 0 3px rgba(0,218,243,0.15)' : 'none',
          transition: 'border-color .14s',
          opacity: disabled ? 0.5 : 1,
          fontFamily: 'inherit',
        }}
      >
        <span style={{
          width: 34, height: 34, flexShrink: 0, borderRadius: 9, display: 'grid', placeItems: 'center',
          fontSize: 12, fontWeight: 800,
          background: value ? `color-mix(in srgb, ${dotColor} 22%, transparent)` : 'rgba(255,255,255,0.05)',
          color: value ? dotColor : '#475569',
          border: `1px solid ${value ? `color-mix(in srgb, ${dotColor} 40%, transparent)` : 'rgba(255,255,255,0.07)'}`,
        }}>
          {value ? fighterInitials(value) : (
            <span className="material-symbols-outlined" style={{ fontSize: 19 }}>person_add</span>
          )}
        </span>

        <span style={{ minWidth: 0, flex: 1 }}>
          {value ? (
            <>
              <span style={{ display: 'block', fontSize: 13.5, fontWeight: 700, color: '#f1f5f9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {fighterFull(value)}
              </span>
              {value.nickname && (
                <span style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#64748b', marginTop: 1 }}>
                  "{value.nickname}"
                </span>
              )}
            </>
          ) : (
            <span style={{ fontSize: 13, fontWeight: 600, color: '#64748b' }}>Select fighter</span>
          )}
        </span>

        {value ? (
          <span
            className="material-symbols-outlined"
            onClick={e => { e.stopPropagation(); onChange(null); }}
            title="Clear"
            style={{ fontSize: 18, color: '#64748b', cursor: 'pointer' }}
          >close</span>
        ) : (
          <span className="material-symbols-outlined" style={{
            fontSize: 20, color: '#64748b',
            transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .14s',
          }}>expand_more</span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute', left: 0, right: 0, zIndex: 20,
          marginTop: 8, borderRadius: 12, border: '1px solid rgba(255,255,255,0.07)',
          background: 'rgba(13,18,24,0.98)',
          boxShadow: '0 24px 60px -20px rgba(0,0,0,0.8)', overflow: 'hidden',
        }}>
          {!creating ? (
            <>
              <div style={{ padding: 10, borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="material-symbols-outlined" style={{ fontSize: 18, color: '#64748b' }}>search</span>
                <input
                  ref={searchRef}
                  value={q}
                  onChange={e => onSearchChange(e.target.value)}
                  placeholder="Search fighters…"
                  style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: '#f1f5f9', fontSize: 13, fontWeight: 600, fontFamily: 'inherit' }}
                />
              </div>

              <div style={{ maxHeight: 196, overflowY: 'auto' }}>
                {loadingFighters && filtered.length === 0 && (
                  <div style={{ padding: '16px 12px', fontSize: 12.5, color: '#64748b', fontWeight: 600, textAlign: 'center' }}>
                    Loading…
                  </div>
                )}
                {filtered.map(f => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => pick(f)}
                    style={{
                      width: '100%', textAlign: 'left', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px',
                      background: value?.id === f.id ? 'rgba(0,218,243,0.08)' : 'transparent',
                      border: 'none', borderBottom: '1px solid rgba(255,255,255,0.05)',
                      fontFamily: 'inherit',
                    }}
                  >
                    <span style={{
                      width: 30, height: 30, flexShrink: 0, borderRadius: 8, display: 'grid', placeItems: 'center',
                      fontSize: 11, fontWeight: 800, background: 'rgba(255,255,255,0.05)', color: '#94a3b8',
                      border: '1px solid rgba(255,255,255,0.07)',
                    }}>{fighterInitials(f)}</span>
                    <span style={{ minWidth: 0, flex: 1 }}>
                      <span style={{ display: 'block', fontSize: 13, fontWeight: 700, color: '#cbd5e1' }}>
                        {fighterFull(f)}
                        {f.nickname && <span style={{ color: '#64748b', fontWeight: 600 }}> · "{f.nickname}"</span>}
                      </span>
                    </span>
                  </button>
                ))}
                {!loadingFighters && filtered.length === 0 && (
                  <div style={{ padding: '16px 12px', fontSize: 12.5, color: '#64748b', fontWeight: 600, textAlign: 'center' }}>
                    No fighters match "{q.trim()}"
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={beginCreate}
                style={{
                  width: '100%', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
                  padding: '11px 12px', background: 'rgba(0,218,243,0.06)', border: 'none',
                  borderTop: '1px solid rgba(255,255,255,0.05)', color: '#00daf3',
                  fontSize: 12.5, fontWeight: 700, fontFamily: 'inherit',
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 17 }}>add</span>
                Can't find them? Create new fighter
              </button>
            </>
          ) : (
            <div style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 12 }}>
                <button
                  type="button"
                  onClick={() => setCreating(false)}
                  style={{
                    width: 28, height: 28, borderRadius: 10, display: 'grid', placeItems: 'center',
                    background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
                    color: '#94a3b8', cursor: 'pointer',
                  }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_back</span>
                </button>
                <span style={{ fontSize: 13, fontWeight: 800, color: '#f1f5f9' }}>New fighter</span>
              </div>

              <div style={{ display: 'grid', gap: 9 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 9 }}>
                  <div>
                    <div style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'rgba(255,255,255,0.28)', marginBottom: 5 }}>First name</div>
                    <input value={nf.first} onChange={e => setNf(s => ({ ...s, first: e.target.value }))} placeholder="First" style={fieldStyle} />
                  </div>
                  <div>
                    <div style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'rgba(255,255,255,0.28)', marginBottom: 5 }}>Last name</div>
                    <input value={nf.last} onChange={e => setNf(s => ({ ...s, last: e.target.value }))} placeholder="Last" style={fieldStyle} />
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'rgba(255,255,255,0.28)', marginBottom: 5 }}>
                    Nickname <span style={{ textTransform: 'none', letterSpacing: 0, color: '#475569' }}>· optional</span>
                  </div>
                  <input value={nf.nick} onChange={e => setNf(s => ({ ...s, nick: e.target.value }))} placeholder="e.g. The Hammer" style={fieldStyle} />
                </div>
                <button
                  type="button"
                  onClick={commitCreate}
                  disabled={!nf.first.trim() || !nf.last.trim()}
                  style={{
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                    background: 'linear-gradient(135deg, #00daf3, #0099b0)', color: '#001f24',
                    fontWeight: 700, fontSize: 13, border: 'none', borderRadius: 10,
                    padding: '9px 16px', cursor: !nf.first.trim() || !nf.last.trim() ? 'not-allowed' : 'pointer',
                    boxShadow: '0 0 20px rgba(0,218,243,0.25)', marginTop: 3,
                    opacity: !nf.first.trim() || !nf.last.trim() ? 0.4 : 1,
                    fontFamily: 'inherit',
                  }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 17 }}>person_add</span>
                  Add & assign to {corner.toLowerCase()}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
