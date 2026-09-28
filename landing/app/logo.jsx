// app/logo.jsx — Fightlytics glove mark + wordmark lockup
const GLOVE_PAD = 'M38 18h32c8 0 14 6 14 14v24c0 8-6 14-14 14H38c-8 0-14-6-14-14V32c0-8 6-14 14-14z';
const GLOVE_THUMB = 'M24 34h-8c-6 0-11 5-11 11 0 6 5 10 11 10h8z';
const GLOVE_CUFF = 'M26 70h56v10c0 4-4 8-8 8H34c-4 0-8-4-8-8z';
const GLOVE_STRAP_A = 'M38 76h32';
const GLOVE_STRAP_B = 'M38 83h32';
const GLOVE_GROOVES = ['M40 24v18', 'M54 24v18', 'M68 24v18'];

function GloveMark({ size = 34, mono = false }) {
  const cyan = mono ? 'currentColor' : '#ff4d1c';
  const fill = mono ? 'none' : 'rgba(255,77,28,.12)';
  const w = size < 36 ? 6.5 : 5.5;
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true" style={{ flex: 'none', display: 'block' }}>
      <path d={GLOVE_CUFF} fill={mono ? 'none' : 'rgba(255,77,28,.06)'} stroke={cyan} strokeWidth={w} strokeLinejoin="round" />
      <path d={GLOVE_THUMB} fill={fill} stroke={cyan} strokeWidth={w} strokeLinejoin="round" />
      <path d={GLOVE_PAD} fill={fill} stroke={cyan} strokeWidth={w} strokeLinejoin="round" />
      {GLOVE_GROOVES.map((d, i) => (
        <path key={i} d={d} stroke={cyan} strokeWidth={size < 36 ? 5.5 : 5} strokeLinecap="round" />
      ))}
      <path d={GLOVE_STRAP_A} stroke={cyan} strokeWidth="4.5" strokeLinecap="round" />
      <path d={GLOVE_STRAP_B} stroke={cyan} strokeWidth="4.5" strokeLinecap="round" />
    </svg>
  );
}

// small single-ink glove for eyebrows / section labels — inherits currentColor
function GloveGlyph({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true" style={{ flex: 'none', display: 'block' }}>
      <path d={GLOVE_CUFF} fill="none" stroke="currentColor" strokeWidth="7" strokeLinejoin="round" />
      <path d={GLOVE_THUMB} fill="none" stroke="currentColor" strokeWidth="7" strokeLinejoin="round" />
      <path d={GLOVE_PAD} fill="none" stroke="currentColor" strokeWidth="7" strokeLinejoin="round" />
      {GLOVE_GROOVES.map((d, i) => (
        <path key={i} d={d} stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
      ))}
    </svg>
  );
}

// oversized outline glove used as a background motif
function GloveWatermark({ className = '', style = null }) {
  return (
    <svg className={'glove-wm ' + className} style={style} viewBox="0 0 100 100" aria-hidden="true">
      <path d={GLOVE_CUFF} fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
      <path d={GLOVE_THUMB} fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
      <path d={GLOVE_PAD} fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
      {GLOVE_GROOVES.map((d, i) => (
        <path key={i} d={d} stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      ))}
      <path d={GLOVE_STRAP_A} stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d={GLOVE_STRAP_B} stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function LogoStack({ size = 64, wordSize = 34, sub = null }) {
  return (
    <div className="brand stack">
      <GloveMark size={size} />
      <div className="brand-word" style={{ fontSize: wordSize }}>fightlytics</div>
      {sub && <div className="brand-sub">{sub}</div>}
    </div>
  );
}

function LogoLockup({ size = 34, wordSize = 26, sub = null }) {
  return (
    <div className="brand">
      <GloveMark size={size} />
      <div>
        <div className="brand-word" style={{ fontSize: wordSize }}>fightlytics</div>
        {sub && <div className="brand-sub">{sub}</div>}
      </div>
    </div>
  );
}

Object.assign(window, { GloveMark, GloveGlyph, GloveWatermark, LogoLockup, LogoStack });
