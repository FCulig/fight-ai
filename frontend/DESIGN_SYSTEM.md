# Fight.AI Design System

A dark, glass-morphism UI built for MMA fight analysis. The aesthetic combines deep space backgrounds, ambient glow, and film grain for a cinematic, data-dense feel.

---

## Fonts

### Body — Manrope
```
font-family: 'Manrope', system-ui, sans-serif;
weights: 400, 500, 600, 700, 800
```

### Display — Bebas Neue
```
font-family: 'Bebas Neue', sans-serif;
letter-spacing: 0.02em;
class: .font-display
```
Used exclusively for large numeric stats and the Round counter.

### Icons — Material Symbols Outlined
```
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />

font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
```
Icon sizes in use: `14, 15, 16, 18, 20, 22, 28, 32, 40`

---

## Color Palette

### Background
| Token | Value | Usage |
|---|---|---|
| `bg-base` | `#050709` | Page background |
| `surface-glass` | `rgba(255,255,255,0.04)` | Card / panel fill |
| `surface-inner` | `rgba(0,0,0,0.30)` | Stat tile, filter bar |
| `header-bg` | `rgba(5,7,9,0.72)` | Sticky nav (with blur) |

### Text
| Token | Value | Usage |
|---|---|---|
| `text-primary` | `#f1f5f9` | Headings, values |
| `text-secondary` | `#cbd5e1` | Body text |
| `text-tertiary` | `#94a3b8` | Labels, btn-glass |
| `text-muted` | `#64748b` | Inactive nav, placeholders |
| `text-disabled` | `#475569` | Body copy, time code |
| `text-faint-1` | `rgba(255,255,255,0.35)` | Subtitle copy |
| `text-faint-2` | `rgba(255,255,255,0.28)` | Section labels |
| `text-faint-3` | `rgba(255,255,255,0.22)` | Frame debug info |
| `text-faint-4` | `rgba(255,255,255,0.20)` | Chevron icons |
| `text-faint-5` | `rgba(255,255,255,0.18)` | Fraction denominator |
| `text-faint-6` | `rgba(255,255,255,0.08)` | Empty-state icons |
| `text-faint-7` | `rgba(255,255,255,0.55)` | Back-nav button |

### Brand / Accent
| Token | Value | Usage |
|---|---|---|
| `cyan-400` | `#00daf3` | Primary accent, links, active states |
| `cyan-600` | `#0099b0` | Gradient end, tinted backgrounds |
| `cyan-on` | `#001f24` | Text on cyan buttons |
| `purple-600` | `#7c3aed` | Logo gradient accent, ambient orb |
| `orange-400` | `#ff7043` | Grapple/ground events, stat gradient |
| `orange-600` | `#e64a19` | Grapple gradient end |
| `green-500` | `#a3c900` | Round marker events |
| `red-500` | `#ef4444` | Error states |
| `slate-400` | `#94a3b8` | Block/defense events |

### Borders
| Token | Value | Usage |
|---|---|---|
| `border-glass` | `rgba(255,255,255,0.07)` | Glass card border |
| `border-faint` | `rgba(255,255,255,0.06)` | Header bottom |
| `border-subtle` | `rgba(255,255,255,0.05)` | Dividers, stat tile |
| `border-cyan` | `rgba(0,218,243,0.15–0.18)` | Active/accent borders |
| `border-cyan-glow` | `rgba(0,218,243,0.25)` | Filter pill active |

---

## Gradients

```css
/* Logo wordmark */
linear-gradient(90deg, #00daf3, #7c3aed)

/* Primary button */
linear-gradient(135deg, #00daf3 0%, #0099b0 100%)

/* Heading text */
linear-gradient(90deg, #f1f5f9, rgba(255,255,255,0.5))

/* Large round display */
linear-gradient(160deg, #f1f5f9 40%, rgba(255,255,255,0.3))

/* Strike stat number */
linear-gradient(135deg, #00daf3, #0099b0)

/* Grapple stat number */
linear-gradient(135deg, #ff7043, #e64a19)

/* Seek bar fill */
linear-gradient(to right, #00daf3 <progress>%, rgba(255,255,255,0.1) <progress>%)

/* Ambient orb A (top-left, cyan) */
radial-gradient(circle, rgba(0,180,255,0.13) 0%, transparent 68%)

/* Ambient orb B (bottom-right, purple) */
radial-gradient(circle, rgba(124,58,237,0.11) 0%, transparent 68%)

/* Ambient orb C (mid, orange) */
radial-gradient(circle, rgba(255,100,50,0.08) 0%, transparent 68%)
```

---

## Typography Scale

| Role | Font | Size | Weight | Extras |
|---|---|---|---|---|
| Display stat | Bebas Neue | 36px | — | tabular-nums |
| Display round | Bebas Neue | 52–64px | — | line-height 1 |
| H1 | Manrope | 22–28px | 800 | letter-spacing -0.02em, gradient fill |
| H2 | Manrope | 18–22px | 800 | letter-spacing -0.02em, gradient fill |
| Body | Manrope | 14px | 500–600 | |
| Body small | Manrope | 13px | 500–700 | |
| Caption | Manrope | 12px | 500–600 | |
| Label/section | Manrope | 10–11px | 700 | uppercase, letter-spacing 0.08–0.12em |
| Frame debug | Manrope | 11px | 400 | tabular-nums |
| Nav item | Manrope | 12–13px | 600 | |

---

## Spacing & Layout

### Breakpoints
| Name | Value |
|---|---|
| Mobile | `< 640px` |
| Tablet | `640–767px` |
| Desktop | `≥ 768px` |

### Max content widths
| Page | Width |
|---|---|
| Fight list | 900px |
| Player | 1440px |
| Library card | 420px |

### Common padding
| Context | Mobile | Desktop |
|---|---|---|
| Page container | 12–20px v / 16px h | 20–40px v / 24–28px h |
| Glass card | 14px v / 16px h | 18px v / 20px h |
| Header | — / 14px h | — / 28px h |

### Header height
`58px` (sticky, `z-index: 100`)

### Sidebar width
`300px` (collapses to full-width on mobile)

---

## Border Radius

| Size | Value | Used on |
|---|---|---|
| `xs` | `7px` | Filter pills |
| `sm` | `8px` | Buttons, nav pills, small controls |
| `md` | `9–10px` | Secondary buttons, upload CTA |
| `lg` | `12px` | Stat tiles, icon badges |
| `xl` | `14px` | Video controls panel |
| `2xl` | `16px` | Glass cards, event feed |
| `3xl` | `20px` | Library card |
| `circle` | `50%` | Ambient orbs |

---

## Surfaces & Glass Morphism

### Glass Card (primary surface)
```css
background: rgba(255,255,255,0.04);
backdrop-filter: blur(20px) saturate(160%);
-webkit-backdrop-filter: blur(20px) saturate(160%);
border: 1px solid rgba(255,255,255,0.07);
border-radius: 16px;
```

### Header / Nav Surface
```css
background: rgba(5,7,9,0.72);
backdrop-filter: blur(24px) saturate(160%);
border-bottom: 1px solid rgba(255,255,255,0.06);
```

### Library Card (elevated glass)
```css
background: rgba(255,255,255,0.04);
backdrop-filter: blur(24px) saturate(160%);
border: 1px solid rgba(255,255,255,0.07);
border-radius: 20px;
box-shadow: 0 8px 40px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06);
```

### Inner tile (nested surface)
```css
background: rgba(0,0,0,0.30);
border: 1px solid rgba(255,255,255,0.05);
border-radius: 12px;
```

### Cyan icon container
```css
background: rgba(0,218,243,0.08);
border: 1px solid rgba(0,218,243,0.15);
border-radius: 12–16px;
```

---

## Button Variants

### `.btn-primary`
```css
background: linear-gradient(135deg, #00daf3 0%, #0099b0 100%);
color: #001f24;
font-weight: 700;
font-size: 12–13px;
border-radius: 8–10px;
box-shadow: 0 0 16px rgba(0,218,243,0.2–0.25);

/* hover */
box-shadow: 0 0 24px rgba(0,218,243,0.4);
```

### `.btn-glass`
```css
background: rgba(255,255,255,0.06);
border: 1px solid rgba(255,255,255,0.08);
border-radius: 8px;
color: #94a3b8;

/* hover */
background: rgba(255,255,255,0.1);
color: #e2e8f0;
```

### Nav link — active
```css
color: #00daf3;
background: rgba(0,218,243,0.1);
border: 1px solid rgba(0,218,243,0.18);
border-radius: 8px;
```

### Nav link — inactive
```css
color: #64748b;
background: transparent;
border: 1px solid transparent;
```

### Filter pill — active
```css
background: rgba(0,218,243,0.15);
color: #00daf3;
border: 1px solid rgba(0,218,243,0.25);
box-shadow: 0 0 12px rgba(0,218,243,0.12);
border-radius: 7px;
```

### Filter pill — inactive
```css
background: transparent;
color: #475569;
border: 1px solid transparent;
```

### "View Lab Report" / secondary CTA
```css
color: rgba(0,218,243,0.7);
background: rgba(0,218,243,0.05);
border: 1px solid rgba(0,218,243,0.12);
border-radius: 8px;
```

---

## Interactive States

```css
/* All buttons */
button {
  transition: opacity 0.15s, transform 0.15s, box-shadow 0.15s, background 0.15s;
}

/* Press down */
button:active {
  transform: scale(0.97);
}

/* Keyboard focus ring */
button:focus-visible {
  outline: 2px solid rgba(0,218,243,0.6);
  outline-offset: 2px;
}

/* Hover — event list row */
.event-item:hover {
  background: rgba(255,255,255,0.03);
}

/* Hover — fight card */
border-color: rgba(0,218,243,0.35);
background: rgba(0,218,243,0.06);

/* Accent color for checkboxes */
accent-color: #00daf3;
```

---

## Shadows / Glow

| Usage | Value |
|---|---|
| Primary button | `box-shadow: 0 0 16px rgba(0,218,243,0.2)` |
| Primary button hover | `box-shadow: 0 0 24px rgba(0,218,243,0.4)` |
| Upload button | `box-shadow: 0 0 20px rgba(0,218,243,0.25)` |
| Library card | `box-shadow: 0 8px 40px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06)` |
| Filter pill active | `box-shadow: 0 0 12px rgba(0,218,243,0.12)` |

---

## Divider
```css
height: 1px;
background: rgba(255,255,255,0.05);
```

---

## Scrollbar
```css
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
```

---

## Animations

### Entry — Fade Up
```css
@keyframes fade-up {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
.anim-fade-up { animation: fade-up 0.5s ease-out both; }
.anim-delay-1 { animation-delay: 0.08s; }
.anim-delay-2 { animation-delay: 0.18s; }
.anim-delay-3 { animation-delay: 0.28s; }
```

### Video — Play/Pause Feedback
```css
@keyframes video-feedback {
  0%   { opacity: 0.9; transform: translate(-50%, -50%) scale(0.8); }
  30%  { opacity: 0.9; transform: translate(-50%, -50%) scale(1.15); }
  100% { opacity: 0;   transform: translate(-50%, -50%) scale(1.45); }
}
/* duration: 0.5s ease-out forwards */
```

### Video — Seek Scrub Pulse
```css
@keyframes seek-pulse {
  0%, 100% { opacity: 0.9; transform: translate(-50%, -50%) scale(1); }
  50%       { opacity: 0.9; transform: translate(-50%, -50%) scale(1.18); }
}
/* duration: 0.6s ease-in-out infinite */
```

### Video — Seek Scrub Fade Out
```css
@keyframes seek-fade {
  from { opacity: 0.9; transform: translate(-50%, -50%) scale(1); }
  to   { opacity: 0;   transform: translate(-50%, -50%) scale(1.35); }
}
/* duration: 0.3s ease-out forwards */
```

### Background — Ambient Orb Drift
```css
@keyframes orb-drift-a {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50%       { transform: translate(40px, 60px) scale(1.08); }
}
/* 18s ease-in-out infinite — cyan orb top-left */

@keyframes orb-drift-b {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50%       { transform: translate(-50px, -40px) scale(1.05); }
}
/* 22s ease-in-out infinite — purple orb bottom-right */

@keyframes orb-drift-c {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50%       { transform: translate(30px, -50px) scale(1.06); }
}
/* 26s ease-in-out infinite — orange orb center-right */
```

### Background — Film Grain
```css
@keyframes grain-shift {
  0%, 100% { transform: translate(0, 0); }
  10%       { transform: translate(-2%, -3%); }
  30%       { transform: translate(3%, 2%); }
  50%       { transform: translate(-1%, 3%); }
  70%       { transform: translate(2%, -2%); }
  90%       { transform: translate(-3%, 1%); }
}
.grain-overlay {
  position: fixed;
  inset: -50%;
  width: 200%; height: 200%;
  opacity: 0.032;
  pointer-events: none;
  background-image: url("data:image/svg+xml,<SVG noise filter>");
  background-size: 200px 200px;
  animation: grain-shift 0.5s steps(1) infinite;
  z-index: 2;
}
```

---

## Background Layer

The app renders a fixed full-screen background behind all content:

```
z-index 0 — #050709 base
  ├── Orb A: 700×700px, top: -180, left: -150, cyan radial, orb-drift-a 18s
  ├── Orb B: 600×600px, bottom: -120, right: -100, purple radial, orb-drift-b 22s
  ├── Orb C: 400×400px, top: 40%, right: 20%, orange radial, orb-drift-c 26s
  └── .grain-overlay: film noise at 3.2% opacity, 0.5s steps animation

z-index 1 — app shell (Header + page content)
z-index 2 — grain-overlay (above bg, below content via pointer-events: none)
z-index 100 — sticky header
```

---

## Event Color System

Used for left-border accents and icon badge colors in the event timeline:

| Event Category | Color | Icon |
|---|---|---|
| Punch / Strike / Hit | `#00daf3` (cyan) | `bolt` |
| Kick / Knee | `#00daf3` (cyan) | `sports_martial_arts` |
| Block / Check | `#94a3b8` (slate) | `shield` |
| Grapple / Takedown / Ground | `#ff7043` (orange) | `sports_kabaddi` |
| Round marker | `#a3c900` (green) | `timer` |
| Default | `#64748b` (muted slate) | `radio_button_checked` |

Icon badge: `background: <color>18`, `border: 1px solid <color>28`, border-radius `7px`, size `28×28px`.

---

## Fighter Overlay (Canvas)

| Fighter | Box Color |
|---|---|
| Fighter 0 | Red |
| Fighter 1 | Blue |

The canvas is `position: absolute` over the video, `pointer-events: none`. Boxes are scaled from the fight's native resolution to the canvas display size.

---

## Responsive Behavior

| Component | Mobile (`< 640px`) | Desktop |
|---|---|---|
| Header padding | 14px | 28px |
| Logo size | 15px | 17px |
| Nav item padding | 5px 10px | 5px 14px |
| Upload button | Icon only | Icon + "Upload Video" |
| Icon buttons | Hidden | Visible |
| Page padding | 12–20px / 16px | 20–40px / 24px |
| Fight list grid | 1 column | `repeat(auto-fill, minmax(280px, 1fr))` |
| Player layout | Column | Row (video + 300px sidebar) |
| Event feed max-height | 360px | 540px |
| Seek bar height | 5px | 3px |
| Touch target min | 44×44px | auto |
| Round display | 52px | 64px |
