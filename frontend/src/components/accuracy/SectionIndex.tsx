import { useEffect, useState, useCallback } from 'react';

const SECTIONS: [string, string][] = [
  ['sec-a', 'Overview'],
  ['sec-b', 'Annotated events'],
  ['sec-d', 'Fights'],
  ['sec-e', 'Pipeline accuracy'],
  ['sec-f', 'Pipeline health'],
];

interface SectionIndexProps {
  narrow: boolean;
}

/** Sticky in-page nav across the section (A/B/D/E/F) anchors — mirrors the
 * Training Lab design's section index. Collapses to a horizontal scroller
 * below ~1100px, same breakpoint the design uses. */
export default function SectionIndex({ narrow }: SectionIndexProps) {
  const [active, setActive] = useState('sec-a');

  const go = useCallback((id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    const y = el.getBoundingClientRect().top + window.pageYOffset - 76;
    window.scrollTo({ top: y, behavior: 'smooth' });
  }, []);

  useEffect(() => {
    const onScroll = () => {
      let cur = 'sec-a';
      SECTIONS.forEach(([id]) => {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top < 160) cur = id;
      });
      setActive(cur);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <nav
      aria-label="Sections"
      style={narrow
        ? { display: 'flex', gap: 4, overflowX: 'auto', paddingBottom: 6, marginBottom: 4 }
        : { position: 'sticky', top: 74 }}
    >
      {!narrow && (
        <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-muted)', padding: '0 0 8px 2px', borderBottom: '1px solid rgba(255,255,255,0.06)', marginBottom: 6 }}>
          Sections
        </div>
      )}
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: narrow ? 'row' : 'column', gap: narrow ? 4 : 1 }}>
        {SECTIONS.map(([id, label]) => (
          <li key={id}>
            <a
              href={`#${id}`}
              onClick={(e) => { e.preventDefault(); go(id); }}
              aria-current={active === id ? 'true' : undefined}
              style={{
                display: 'flex', alignItems: 'center', gap: 9, padding: '8px 12px', borderRadius: 999,
                textDecoration: 'none', whiteSpace: 'nowrap', fontSize: 13, fontWeight: 600,
                color: active === id ? 'var(--text-primary)' : 'var(--text-muted)',
                background: active === id ? 'var(--surface-glass-2)' : 'transparent',
                border: `1px solid ${active === id ? 'var(--border-glass)' : 'transparent'}`,
                transition: 'color .12s, background .12s, border-color .12s',
              }}
            >
              {label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
