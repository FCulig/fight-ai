# Design System Reference — Liquid Glass Edition

UI design philosophy built around a **liquid glass** aesthetic: translucent layered
surfaces, luminous gradient accents, frosted depth, and fluid motion. Every component
feels like light passing through tinted crystal — refracting, glowing, alive.

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [The Liquid Glass Aesthetic](#the-liquid-glass-aesthetic)
3. [Design Tokens](#design-tokens)
4. [Gradient System](#gradient-system)
5. [Glass Surface System](#glass-surface-system)
6. [Typography](#typography)
7. [Color System](#color-system)
8. [Spacing & Layout](#spacing--layout)
9. [Component Design Patterns](#component-design-patterns)
10. [Motion & Transitions](#motion--transitions)
11. [Responsive Design](#responsive-design)
12. [Accessibility](#accessibility)
13. [Dark Mode](#dark-mode)
14. [Visual Polish Checklist](#visual-polish-checklist)

---

## Design Philosophy

The UI is the product. Code architecture enables it; the UI delivers it. Every visual
decision communicates something to the user — clarity, trust, competence, delight.

### Principles

1. **Depth through translucency** — Surfaces are not opaque walls; they are layers of
   tinted glass stacked in space. The user perceives depth because content behind a
   panel bleeds through softly. This creates a natural spatial hierarchy without heavy
   shadows.

2. **Light as a material** — Gradients, glows, and refractive highlights are not
   decoration — they are the primary visual language. Light flows across surfaces,
   pools in corners, and catches edges. The interface feels illuminated from within.

3. **Consistency builds trust** — The same glass treatment, the same blur radius, the
   same gradient angle. A glass card in the sidebar and a glass card in the main content
   area should feel like the same material under different lighting.

4. **Hierarchy through opacity and luminance** — Primary elements are more opaque and
   more luminous. Secondary elements are more transparent and more subdued. The eye
   naturally moves from bright to dim, from solid to ethereal.

5. **Feedback is immediate** — Every interaction gets a response. Glass surfaces brighten
   on hover. Buttons gain a sharper glow on press. Focus rings emit a soft halo.
   Transitions are smooth and organic — nothing snaps.

### Anti-Patterns to Avoid

- **Frosted Soup**: Applying `backdrop-filter: blur()` to everything makes the entire
  page feel unfocused and muddy. Use glass selectively — panels, cards, modals, toolbars.
  Content areas that display text or data should have enough opacity to be clearly readable.
- **Gradient Overload**: Too many competing gradient directions and hue shifts create
  visual chaos. Establish one primary gradient direction (typically top-left to
  bottom-right) and one accent gradient. Everything else derives from these.
- **The Rainbow Explosion**: Liquid glass should feel cohesive — a limited palette of
  2-3 hues that shift and blend, not a full spectrum.
- **Invisible Boundaries**: When everything is translucent, elements can bleed into each
  other. Subtle borders (1px with low opacity white or colored tint) and precise shadow
  layers restore separation.
- **Ignoring Readability**: Glass is beautiful but text on glass must still meet contrast
  requirements. Layer a semi-opaque fill behind text zones or use text-shadow for legibility.

---

## The Liquid Glass Aesthetic

This section defines the core visual language. Every component in the system should
feel like it belongs to this material family.

### What Makes It "Liquid Glass"

The effect combines several CSS techniques layered together:

1. **Backdrop blur** — `backdrop-filter: blur()` creates the frosted glass translucency.
   This is the foundation.
2. **Semi-transparent backgrounds** — `rgba()` or `hsla()` fills with 5–30% opacity
   let the environment bleed through while tinting the surface.
3. **Gradient overlays** — Subtle linear or radial gradients across the surface simulate
   light hitting glass at an angle. These gradients use very low opacity white or
   colored values.
4. **Border highlights** — A 1px border with `rgba(255, 255, 255, 0.15–0.3)` simulates
   the light-catching edge of a glass pane.
5. **Inner glow / highlight** — A subtle `inset` box-shadow with white at low opacity
   creates the impression of light pooling on the inner surface.
6. **Soft outer shadow** — A colored or neutral shadow with significant blur radius
   and spread creates the impression of the glass floating above its environment.

### The Glass Mixin (CSS)

This is the foundational glass treatment. Apply it to cards, panels, modals, dropdowns,
tooltips, and navigation surfaces:

```css
/* --- Base glass surface --- */
.glass {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--glass-radius);
  box-shadow:
    /* Outer glow — the colored ambient shadow */
    0 8px 32px var(--glass-shadow),
    /* Inner highlight — light pooling on the top edge */
    inset 0 1px 0 var(--glass-highlight);
}

/* --- Glass with gradient sheen --- */
.glass-sheen {
  composes: glass;
  background:
    linear-gradient(
      135deg,
      var(--glass-sheen-from) 0%,
      var(--glass-sheen-to) 100%
    ),
    var(--glass-bg);
}
```

### Glass Intensity Levels

Not every surface needs the same amount of glass. Define levels:

| Level        | Blur   | BG Opacity | Use Case                              |
|------------- |--------|------------|---------------------------------------|
| `glass-subtle`  | 8px    | 3–6%       | Page backgrounds, large area fills    |
| `glass-light`   | 12px   | 8–12%      | Secondary panels, sidebars            |
| `glass-medium`  | 16px   | 15–20%     | Cards, toolbars, navigation bars      |
| `glass-heavy`   | 24px   | 25–35%     | Modals, dialogs, focused overlays     |
| `glass-solid`   | 24px   | 50–70%     | Tooltips, toasts, dropdowns (need readability) |

```css
:root {
  /* Glass levels — light theme */
  --glass-subtle-bg: rgba(255, 255, 255, 0.04);
  --glass-subtle-blur: 8px;

  --glass-light-bg: rgba(255, 255, 255, 0.08);
  --glass-light-blur: 12px;

  --glass-medium-bg: rgba(255, 255, 255, 0.15);
  --glass-medium-blur: 16px;

  --glass-heavy-bg: rgba(255, 255, 255, 0.25);
  --glass-heavy-blur: 24px;

  --glass-solid-bg: rgba(255, 255, 255, 0.55);
  --glass-solid-blur: 24px;
}
```

### The Environment Layer

Glass only looks like glass when there's something behind it to blur. The page
background is critical — it provides the "environment" that glass refracts.

**Best backgrounds for liquid glass:**
- Mesh gradients (multiple radial gradients overlapping with different hues)
- Large soft blobs of color positioned with absolute/fixed elements
- Subtle animated gradient shifts (slow, 10-20 second cycles)
- Photography or illustration with a pre-applied blur as a base layer

```css
/* Example mesh gradient background */
.app-environment {
  background-color: var(--env-base);
  background-image:
    radial-gradient(ellipse at 20% 50%, var(--env-blob-1) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, var(--env-blob-2) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 80%, var(--env-blob-3) 0%, transparent 50%);
  min-height: 100dvh;
}

:root {
  --env-base: #0a0a1a;
  --env-blob-1: rgba(99, 102, 241, 0.15);   /* Indigo */
  --env-blob-2: rgba(168, 85, 247, 0.12);   /* Purple */
  --env-blob-3: rgba(59, 130, 246, 0.10);   /* Blue */
}
```

---

## Design Tokens

Tokens are the atomic values of the design system. Every visual property comes from
a token. The liquid glass system adds glass-specific and gradient-specific tokens
alongside the standard set.

### Token Structure

```typescript
// design-system/tokens.ts

export const tokens = {
  colors: {
    // Semantic tokens
    primary: 'var(--color-primary)',
    primaryHover: 'var(--color-primary-hover)',
    primaryActive: 'var(--color-primary-active)',
    primarySubtle: 'var(--color-primary-subtle)',
    primaryGlow: 'var(--color-primary-glow)',

    secondary: 'var(--color-secondary)',

    accent: 'var(--color-accent)',
    accentGlow: 'var(--color-accent-glow)',

    success: 'var(--color-success)',
    warning: 'var(--color-warning)',
    error: 'var(--color-error)',
    info: 'var(--color-info)',

    // Surface tokens — glass-aware
    background: 'var(--color-bg)',
    surface: 'var(--color-surface)',
    surfaceGlass: 'var(--glass-medium-bg)',
    surfaceRaised: 'var(--color-surface-raised)',
    surfaceOverlay: 'var(--color-surface-overlay)',

    // Border tokens — glass-aware
    border: 'var(--color-border)',
    borderGlass: 'var(--glass-border)',
    borderSubtle: 'var(--color-border-subtle)',
    borderFocus: 'var(--color-border-focus)',

    // Text tokens
    textPrimary: 'var(--color-text-primary)',
    textSecondary: 'var(--color-text-secondary)',
    textTertiary: 'var(--color-text-tertiary)',
    textInverse: 'var(--color-text-inverse)',
    textLink: 'var(--color-text-link)',
    textOnGlass: 'var(--color-text-on-glass)',
  },

  glass: {
    blur: {
      subtle: 'var(--glass-subtle-blur)',
      light: 'var(--glass-light-blur)',
      medium: 'var(--glass-medium-blur)',
      heavy: 'var(--glass-heavy-blur)',
    },
    bg: {
      subtle: 'var(--glass-subtle-bg)',
      light: 'var(--glass-light-bg)',
      medium: 'var(--glass-medium-bg)',
      heavy: 'var(--glass-heavy-bg)',
      solid: 'var(--glass-solid-bg)',
    },
    border: 'var(--glass-border)',
    highlight: 'var(--glass-highlight)',
    shadow: 'var(--glass-shadow)',
  },

  gradients: {
    primary: 'var(--gradient-primary)',
    accent: 'var(--gradient-accent)',
    surface: 'var(--gradient-surface)',
    shimmer: 'var(--gradient-shimmer)',
    glow: 'var(--gradient-glow)',
  },

  spacing: {
    '0': '0',
    '1': '0.25rem',    // 4px
    '2': '0.5rem',     // 8px
    '3': '0.75rem',    // 12px
    '4': '1rem',       // 16px — base unit
    '5': '1.25rem',    // 20px
    '6': '1.5rem',     // 24px
    '8': '2rem',       // 32px
    '10': '2.5rem',    // 40px
    '12': '3rem',      // 48px
    '16': '4rem',      // 64px
    '20': '5rem',      // 80px
    '24': '6rem',      // 96px
  },

  radii: {
    none: '0',
    sm: '0.375rem',    // 6px — slightly softer for glass
    md: '0.75rem',     // 12px — standard glass card
    lg: '1rem',        // 16px — prominent panels
    xl: '1.25rem',     // 20px — modals, hero cards
    '2xl': '1.5rem',   // 24px — large feature surfaces
    full: '9999px',    // pills, avatars, orbs
  },

  shadows: {
    // Standard shadows with colored tinting
    sm: '0 2px 8px var(--shadow-color-sm)',
    md: '0 4px 16px var(--shadow-color-md)',
    lg: '0 8px 32px var(--shadow-color-lg)',
    xl: '0 16px 48px var(--shadow-color-xl)',

    // Glow shadows — colored light emission
    glowSm: '0 0 12px var(--color-primary-glow)',
    glowMd: '0 0 24px var(--color-primary-glow)',
    glowLg: '0 0 48px var(--color-primary-glow)',
    glowAccent: '0 0 24px var(--color-accent-glow)',

    // Glass-specific compound shadow
    glass: '0 8px 32px var(--glass-shadow), inset 0 1px 0 var(--glass-highlight)',

    focus: '0 0 0 3px var(--color-primary-glow)',
  },

  typography: {
    fontFamily: {
      sans: "'Plus Jakarta Sans', 'General Sans', -apple-system, BlinkMacSystemFont, system-ui, sans-serif",
      display: "'Outfit', 'Satoshi', 'Plus Jakarta Sans', system-ui, sans-serif",
      mono: "'JetBrains Mono', 'Fira Code', monospace",
    },
    fontSize: {
      xs: '0.75rem',
      sm: '0.875rem',
      base: '1rem',
      lg: '1.125rem',
      xl: '1.25rem',
      '2xl': '1.5rem',
      '3xl': '1.875rem',
      '4xl': '2.25rem',
      '5xl': '3rem',
      '6xl': '3.75rem',
    },
    fontWeight: {
      normal: '400',
      medium: '500',
      semibold: '600',
      bold: '700',
      extrabold: '800',
    },
    lineHeight: {
      tight: '1.2',
      snug: '1.35',
      normal: '1.5',
      relaxed: '1.625',
    },
    letterSpacing: {
      tight: '-0.03em',
      snug: '-0.015em',
      normal: '0',
      wide: '0.025em',
      wider: '0.05em',
      widest: '0.1em',
    },
  },

  transitions: {
    fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
    normal: '250ms cubic-bezier(0.4, 0, 0.2, 1)',
    slow: '400ms cubic-bezier(0.4, 0, 0.2, 1)',
    spring: '500ms cubic-bezier(0.34, 1.56, 0.64, 1)',
    glass: '300ms cubic-bezier(0.16, 1, 0.3, 1)',      // Smooth for glass hover
    glow: '600ms cubic-bezier(0.4, 0, 0.2, 1)',        // Slow for glow effects
  },

  zIndex: {
    dropdown: 10,
    sticky: 20,
    overlay: 30,
    modal: 40,
    toast: 50,
    tooltip: 60,
  },
} as const;
```

### CSS Custom Properties

```css
:root {
  /* ——— Primary palette ——— */
  --color-primary: #6366f1;                          /* Indigo 500 */
  --color-primary-hover: #818cf8;                    /* Indigo 400 */
  --color-primary-active: #4f46e5;                   /* Indigo 600 */
  --color-primary-subtle: rgba(99, 102, 241, 0.12);
  --color-primary-glow: rgba(99, 102, 241, 0.35);

  /* ——— Accent ——— */
  --color-accent: #a855f7;                           /* Purple 500 */
  --color-accent-glow: rgba(168, 85, 247, 0.3);

  /* ——— Neutrals ——— */
  --color-bg: #06060f;
  --color-surface: rgba(255, 255, 255, 0.03);
  --color-surface-raised: rgba(255, 255, 255, 0.06);
  --color-surface-overlay: rgba(0, 0, 0, 0.6);

  --color-border: rgba(255, 255, 255, 0.08);
  --color-border-subtle: rgba(255, 255, 255, 0.04);
  --color-border-focus: rgba(99, 102, 241, 0.6);

  --color-text-primary: rgba(255, 255, 255, 0.95);
  --color-text-secondary: rgba(255, 255, 255, 0.6);
  --color-text-tertiary: rgba(255, 255, 255, 0.35);
  --color-text-inverse: #06060f;
  --color-text-on-glass: rgba(255, 255, 255, 0.9);
  --color-text-link: #818cf8;

  /* ——— Status ——— */
  --color-success: #34d399;
  --color-success-glow: rgba(52, 211, 153, 0.3);
  --color-warning: #fbbf24;
  --color-warning-glow: rgba(251, 191, 36, 0.3);
  --color-error: #f87171;
  --color-error-glow: rgba(248, 113, 113, 0.3);
  --color-info: #60a5fa;

  /* ——— Glass system ——— */
  --glass-border: rgba(255, 255, 255, 0.12);
  --glass-highlight: rgba(255, 255, 255, 0.06);
  --glass-shadow: rgba(0, 0, 0, 0.25);

  --glass-subtle-bg: rgba(255, 255, 255, 0.03);
  --glass-subtle-blur: 8px;
  --glass-light-bg: rgba(255, 255, 255, 0.06);
  --glass-light-blur: 12px;
  --glass-medium-bg: rgba(255, 255, 255, 0.10);
  --glass-medium-blur: 16px;
  --glass-heavy-bg: rgba(255, 255, 255, 0.18);
  --glass-heavy-blur: 24px;
  --glass-solid-bg: rgba(255, 255, 255, 0.45);
  --glass-solid-blur: 24px;

  /* ——— Shadows ——— */
  --shadow-color-sm: rgba(0, 0, 0, 0.15);
  --shadow-color-md: rgba(0, 0, 0, 0.2);
  --shadow-color-lg: rgba(0, 0, 0, 0.3);
  --shadow-color-xl: rgba(0, 0, 0, 0.4);

  /* ——— Gradients ——— */
  --gradient-primary: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
  --gradient-accent: linear-gradient(135deg, #a855f7 0%, #ec4899 100%);
  --gradient-surface: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 100%);
  --gradient-shimmer: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.06) 50%, transparent 100%);
  --gradient-glow: radial-gradient(ellipse at 50% 0%, var(--color-primary-glow) 0%, transparent 60%);

  /* ——— Environment blobs ——— */
  --env-base: #06060f;
  --env-blob-1: rgba(99, 102, 241, 0.12);
  --env-blob-2: rgba(168, 85, 247, 0.10);
  --env-blob-3: rgba(236, 72, 153, 0.08);
}
```

---

## Gradient System

Gradients are the lifeblood of the liquid glass look. They provide color, energy, and
the sense that light is moving through the interface.

### Gradient Roles

| Role            | Use Case                                     | Character                       |
|-----------------|----------------------------------------------|---------------------------------|
| **Primary**     | CTA buttons, active states, hero accents     | Vivid, 2-3 stops, 135deg       |
| **Accent**      | Badges, highlights, selected items           | Vibrant, 2 stops, complements primary |
| **Surface**     | Card backgrounds, glass sheen overlays       | Ultra-subtle, white-to-transparent |
| **Shimmer**     | Loading skeletons, hover micro-effects       | Horizontal sweep, animated      |
| **Glow**        | Behind hero elements, ambient lighting       | Radial, soft, large, low opacity |
| **Border**      | Gradient borders on featured elements        | Matches primary, via `border-image` or pseudo |
| **Text**        | Hero headings, feature titles                | `background-clip: text` effect  |

### Gradient Text

```css
.gradient-text {
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

Use gradient text sparingly — only on hero headings, feature titles, or key stats.
Never on body text or secondary labels.

### Gradient Borders

Glass surfaces sometimes need a more vivid border than a plain `rgba` edge. Use a
pseudo-element or `border-image`:

```css
/* Gradient border via pseudo-element (allows border-radius) */
.glass-gradient-border {
  position: relative;
  border-radius: var(--glass-radius);
  padding: 1px; /* This IS the border width */
  background: var(--gradient-primary);
}

.glass-gradient-border > .inner {
  background: var(--glass-heavy-bg);
  backdrop-filter: blur(var(--glass-heavy-blur));
  border-radius: calc(var(--glass-radius) - 1px);
  padding: 1.5rem;
}
```

A simpler approach when the container has a solid-ish background:

```css
.gradient-border-simple {
  border: 1px solid transparent;
  background-image:
    linear-gradient(var(--glass-heavy-bg), var(--glass-heavy-bg)),
    var(--gradient-primary);
  background-origin: border-box;
  background-clip: padding-box, border-box;
}
```

### Animated Gradients

For hero sections or ambient effects, slowly shifting gradients add life:

```css
@keyframes gradient-shift {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}

.animated-gradient {
  background: linear-gradient(
    -45deg,
    #6366f1, #a855f7, #ec4899, #6366f1
  );
  background-size: 300% 300%;
  animation: gradient-shift 12s ease infinite;
}
```

Keep animated gradients to backgrounds or large decorative areas — never on text
or small interactive elements where the motion would be distracting.

---

## Glass Surface System

### Composing Glass Components in React

Create a reusable `Glass` wrapper that applies the surface treatment:

```typescript
interface GlassProps {
  readonly level?: 'subtle' | 'light' | 'medium' | 'heavy' | 'solid';
  readonly glow?: boolean;
  readonly gradientBorder?: boolean;
  readonly className?: string;
  readonly children: ReactNode;
}

/**
 * Glass surface wrapper. Applies backdrop blur, translucent fill,
 * border highlight, and optional glow/gradient border.
 *
 * Usage:
 *   <Glass level="medium" glow>
 *     <CardContent />
 *   </Glass>
 */
function Glass({
  level = 'medium',
  glow = false,
  gradientBorder = false,
  className,
  children,
}: GlassProps) {
  return (
    <div
      className={cn(
        styles.glass,
        styles[`glass-${level}`],
        glow && styles.glassGlow,
        gradientBorder && styles.glassGradientBorder,
        className
      )}
    >
      {children}
    </div>
  );
}
```

### When to Use Each Level

- **subtle** — Background panels, page-level container fills, sidebar backgrounds.
  The user shouldn't consciously notice the glass — it's just atmosphere.
- **light** — Secondary cards, navigation rails, inactive tab backgrounds.
- **medium** — Primary cards, toolbar, header bar, sidebar panels. The main
  workhorse level.
- **heavy** — Modals, dialog overlays, focused panels, feature highlights.
  Draws the eye.
- **solid** — Tooltips, toast notifications, dropdown menus. Needs to be highly
  readable even over busy backgrounds.

### Glass + Content Readability

The biggest risk with glass surfaces is that text becomes hard to read when the
background behind it is busy or bright. Mitigate this:

1. **Add a solid-ish inner layer** for text-heavy areas within a glass card:
   ```css
   .glass-text-zone {
     background: rgba(0, 0, 0, 0.3); /* Or white in light theme */
     border-radius: 8px;
     padding: 1rem;
   }
   ```

2. **Use text-shadow** for light-on-glass text:
   ```css
   .text-on-glass {
     text-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
   }
   ```

3. **Increase font weight** slightly — medium (500) instead of regular (400)
   improves legibility on translucent surfaces.

4. **Test against different environment states** — scroll the page so different
   background colors sit behind the glass, and verify text remains readable.

---

## Typography

Typography on glass surfaces requires extra attention to legibility. The translucency
means contrast shifts as the user scrolls. Choose fonts and weights that hold up.

### Font Selection for Liquid Glass

**Display / Headings**: Choose fonts that look stunning with gradient fills and at
large sizes against translucent surfaces:
- Modern geometric sans (Outfit, Satoshi, Plus Jakarta Sans)
- Clean variable-weight sans (Inter Variable, but only at heavier weights)
- Elegant sans with personality (Syne, Cabinet Grotesk, Switzer)

**Body text**: Prioritize clarity on glass:
- Medium weight (500) as the default body weight — regular (400) can feel too thin.
- Minimum 16px on desktop, 15px on mobile.
- Line height between 1.5 and 1.65.
- `max-width: 65ch` for reading comfort.
- Consider a subtle text-shadow on glass surfaces for anchoring.

### Type Scale

```css
/* Heading hierarchy — tighter tracking for that premium feel */
h1 { font-size: 3rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; }
h2 { font-size: 2.25rem; font-weight: 700; letter-spacing: -0.025em; line-height: 1.2; }
h3 { font-size: 1.5rem; font-weight: 600; letter-spacing: -0.015em; line-height: 1.3; }
h4 { font-size: 1.25rem; font-weight: 600; line-height: 1.35; }

/* Body */
body { font-size: 1rem; font-weight: 500; line-height: 1.5; color: var(--color-text-primary); }
.text-sm { font-size: 0.875rem; line-height: 1.5; }
.text-xs { font-size: 0.75rem; line-height: 1.5; letter-spacing: 0.03em; }

/* Gradient heading — use on hero titles and key stats */
.heading-gradient {
  font-weight: 800;
  letter-spacing: -0.03em;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* Uppercase label — for subtle section labels, stat labels, metadata */
.label-caps {
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-tertiary);
}
```

---

## Color System

### Palette Construction for Liquid Glass

The liquid glass aesthetic works best with a **cool-toned, dark-first** palette.
Deep navy/charcoal backgrounds let glass surfaces glow. Accent colors should be
vivid and slightly neon — they need to punch through translucent layers.

**Recommended palette families:**
- Indigo → Purple → Pink (the default — luxurious and modern)
- Cyan → Blue → Violet (techy, futuristic)
- Emerald → Teal → Cyan (organic, fresh)
- Amber → Orange → Rose (warm, energetic — less common for glass but striking)

### Color Usage Rules

- **Background**: Very dark — nearly black with a slight color tint. `#06060f` (blue-black),
  `#0a0f0d` (green-black), `#0f0a0a` (warm-black). Pure black (#000) is acceptable for
  glass aesthetics but a tinted black gives more depth.
- **Glass surfaces**: White at very low opacity in dark themes. In light themes (see
  Dark Mode section), use the same approach but inverted — dark glass on light.
- **Primary color**: Vivid and slightly luminous. It appears in CTA buttons (as gradient
  fills), active states, focus rings, and key accents. One primary hue only.
- **Accent color**: A complementary or analogous hue that appears in secondary highlights,
  badges, and gradient endpoints. Used to add richness without competing with primary.
- **Glow effects**: Every primary and accent color has a `*-glow` variant — the same hue
  at 25-40% opacity, used in box-shadows and radial gradients to simulate light emission.
- **Status colors**: Softer than in traditional UIs — the glass aesthetic calls for pastel-ish
  success/warning/error that won't clash with the overall palette. Use muted versions
  (e.g., `#34d399` green instead of `#16a34a`).

### Contrast on Glass

Because glass surfaces shift in effective lightness based on what's behind them,
design for the worst case:
- Keep text at `rgba(255, 255, 255, 0.9)` minimum on dark themes.
- Test text over both dark and light background areas.
- When in doubt, increase the glass surface opacity or add a `text-shadow`.

---

## Spacing & Layout

### The 4px Grid

All spacing is based on a 4px unit. This is unchanged from standard design systems —
glass aesthetics don't change spatial rhythm.

### Layout Patterns for Glass

**Page-level layout** — The environment gradient is full-bleed. Glass panels float on top:

```css
.app-layout {
  display: grid;
  grid-template-columns: var(--sidebar-width, 280px) 1fr;
  grid-template-rows: var(--header-height, 64px) 1fr;
  min-height: 100dvh;
  position: relative;
}

/* The environment lives behind everything */
.app-environment {
  position: fixed;
  inset: 0;
  z-index: -1;
  background-color: var(--env-base);
  background-image:
    radial-gradient(ellipse at 20% 50%, var(--env-blob-1) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, var(--env-blob-2) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 80%, var(--env-blob-3) 0%, transparent 50%);
}

/* Sidebar as glass panel */
.sidebar {
  background: var(--glass-light-bg);
  backdrop-filter: blur(var(--glass-light-blur));
  border-right: 1px solid var(--glass-border);
}

/* Header as glass toolbar */
.header {
  background: var(--glass-medium-bg);
  backdrop-filter: blur(var(--glass-medium-blur));
  border-bottom: 1px solid var(--glass-border);
  box-shadow: inset 0 -1px 0 var(--glass-highlight);
}
```

**Content spacing** — More generous padding inside glass cards than traditional cards.
The translucency means elements at the edges bleed into the border — extra padding
creates breathing room:

```css
.glass-card {
  padding: 1.75rem;     /* 28px — slightly more than standard 24px */
  gap: 1.25rem;         /* 20px — between card elements */
  border-radius: 1rem;  /* 16px — softer corners for glass */
}
```

---

## Component Design Patterns

### Button Hierarchy — Glass Edition

```css
/* Primary — gradient fill, glow shadow */
.btn-primary {
  background: var(--gradient-primary);
  color: white;
  border: none;
  border-radius: 10px;
  padding: 0.625rem 1.25rem;
  font-weight: 600;
  box-shadow: 0 4px 16px var(--color-primary-glow);
  transition:
    box-shadow var(--transition-glass),
    transform var(--transition-fast),
    filter var(--transition-fast);
}

.btn-primary:hover {
  box-shadow: 0 6px 24px var(--color-primary-glow);
  transform: translateY(-1px);
  filter: brightness(1.1);
}

.btn-primary:active {
  transform: translateY(0);
  filter: brightness(0.95);
  box-shadow: 0 2px 8px var(--color-primary-glow);
}

/* Secondary — glass surface */
.btn-secondary {
  background: var(--glass-medium-bg);
  backdrop-filter: blur(var(--glass-medium-blur));
  color: var(--color-text-primary);
  border: 1px solid var(--glass-border);
  border-radius: 10px;
  padding: 0.625rem 1.25rem;
  font-weight: 500;
  transition:
    background var(--transition-glass),
    border-color var(--transition-fast);
}

.btn-secondary:hover {
  background: var(--glass-heavy-bg);
  border-color: rgba(255, 255, 255, 0.2);
}

/* Ghost / Tertiary — minimal, text-only with subtle hover */
.btn-ghost {
  background: transparent;
  color: var(--color-text-secondary);
  border: none;
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  font-weight: 500;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.btn-ghost:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--color-text-primary);
}

/* Destructive — red glow instead of primary */
.btn-destructive {
  background: linear-gradient(135deg, #ef4444 0%, #f87171 100%);
  color: white;
  border: none;
  border-radius: 10px;
  box-shadow: 0 4px 16px var(--color-error-glow);
}
```

### Input Fields — Glass Edition

```css
.input {
  height: 44px;
  padding: 0 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1.5px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  color: var(--color-text-primary);
  font-size: 0.9375rem;
  font-weight: 500;
  transition:
    border-color 200ms,
    box-shadow 200ms,
    background 200ms;
}

.input::placeholder {
  color: var(--color-text-tertiary);
}

.input:hover {
  border-color: rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.07);
}

.input:focus {
  outline: none;
  border-color: var(--color-border-focus);
  box-shadow: 0 0 0 3px var(--color-primary-glow);
  background: rgba(255, 255, 255, 0.08);
}

.input[aria-invalid="true"] {
  border-color: var(--color-error);
  box-shadow: 0 0 0 3px var(--color-error-glow);
}
```

### Cards — Glass Edition

```css
.card {
  background: var(--glass-medium-bg);
  backdrop-filter: blur(var(--glass-medium-blur));
  -webkit-backdrop-filter: blur(var(--glass-medium-blur));
  border: 1px solid var(--glass-border);
  border-radius: 1rem;
  padding: 1.75rem;
  box-shadow:
    0 8px 32px var(--glass-shadow),
    inset 0 1px 0 var(--glass-highlight);
  transition:
    box-shadow var(--transition-glass),
    transform var(--transition-glass),
    background var(--transition-glass);
}

/* Interactive card — lifts and glows on hover */
.card-interactive:hover {
  background: var(--glass-heavy-bg);
  box-shadow:
    0 12px 40px var(--glass-shadow),
    0 0 24px var(--color-primary-glow),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  transform: translateY(-2px);
}

/* Featured card — gradient border treatment */
.card-featured {
  position: relative;
  padding: 1px;
  background: var(--gradient-primary);
  border-radius: 1rem;
  border: none;
}

.card-featured > .card-inner {
  background: rgba(6, 6, 15, 0.85);
  backdrop-filter: blur(24px);
  border-radius: calc(1rem - 1px);
  padding: 1.75rem;
}
```

### Modal / Dialog — Glass Edition

```css
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
}

.modal {
  background: var(--glass-heavy-bg);
  backdrop-filter: blur(var(--glass-heavy-blur));
  border: 1px solid var(--glass-border);
  border-radius: 1.25rem;
  box-shadow:
    0 24px 64px rgba(0, 0, 0, 0.4),
    0 0 48px var(--color-primary-glow),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  max-width: 520px;
  width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  padding: 2rem;
}
```

### Tables on Glass

```css
.table-container {
  background: var(--glass-light-bg);
  backdrop-filter: blur(var(--glass-light-blur));
  border: 1px solid var(--glass-border);
  border-radius: 1rem;
  overflow: hidden;
}

.table th {
  background: rgba(255, 255, 255, 0.04);
  font-weight: 600;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--color-text-tertiary);
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--glass-border);
}

.table td {
  padding: 0.875rem 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  color: var(--color-text-primary);
}

.table tr:hover td {
  background: rgba(255, 255, 255, 0.03);
}
```

### Loading Skeleton — Shimmer on Glass

```css
@keyframes shimmer {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.skeleton {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  position: relative;
  overflow: hidden;
}

.skeleton::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.06) 50%,
    transparent 100%
  );
  animation: shimmer 1.5s infinite;
}
```

### Empty States

Empty states on glass should feel inviting, not barren. Use a subtle glow or icon
with a gradient treatment to maintain visual warmth:

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 3rem 2rem;
  gap: 1rem;
}

.empty-state-icon {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gradient-primary);
  border-radius: 16px;
  color: white;
  font-size: 1.5rem;
  box-shadow: 0 0 32px var(--color-primary-glow);
}
```

---

## Motion & Transitions

### Glass-Specific Animation Principles

Glass surfaces respond to interaction like a physical material — they brighten, lift,
and settle. Motion should feel organic and weighted, never mechanical.

**On hover**: Background opacity increases (glass gets slightly more opaque), a subtle
glow appears, and the element lifts slightly via `translateY(-1px to -2px)`.

**On press**: The element settles back down, the glow compresses, and brightness
decreases slightly.

**On appear**: Glass surfaces fade in with a slight upward drift (`translateY(8px) → 0`)
and the blur resolves from 0 to full — like the surface crystallizing into view.

### Glass Enter Animation

```css
@keyframes glass-enter {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.98);
    backdrop-filter: blur(0px);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
    backdrop-filter: blur(var(--glass-medium-blur));
  }
}

.glass-enter {
  animation: glass-enter 400ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
```

### Glow Pulse (Attention / Notification)

```css
@keyframes glow-pulse {
  0%, 100% { box-shadow: 0 0 16px var(--color-primary-glow); }
  50%      { box-shadow: 0 0 32px var(--color-primary-glow); }
}

.glow-pulse {
  animation: glow-pulse 2s ease-in-out infinite;
}
```

### Duration Guidelines

- Micro-interactions (hover glow, press): 150ms
- Small elements (tooltips, dropdowns): 200ms
- Glass surfaces entering/leaving: 300–400ms
- Modal overlay + content: 300ms overlay, 400ms content (staggered)
- Ambient gradient animation: 10–20 seconds per cycle
- Glow pulse: 2–3 seconds per cycle

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    backdrop-filter: blur(var(--glass-medium-blur)) !important; /* Keep blur, skip transition */
  }
}
```

---

## Responsive Design

### Breakpoints

```typescript
export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const;
```

### Glass on Mobile

`backdrop-filter: blur()` is GPU-intensive. On lower-powered devices:

1. **Reduce blur radius** on mobile: 16px → 10px, 24px → 14px.
2. **Increase background opacity** to compensate — the surface stays readable even with
   less blur.
3. **Reduce the number of blurred layers** — if your sidebar, header, AND cards all
   blur, pick the most important and make others semi-opaque without blur.
4. **Test on real devices** — the Chrome DevTools mobile emulator doesn't accurately
   represent blur performance.

```css
@media (max-width: 768px) {
  :root {
    --glass-medium-blur: 10px;
    --glass-heavy-blur: 14px;
    --glass-medium-bg: rgba(255, 255, 255, 0.14);
    --glass-heavy-bg: rgba(255, 255, 255, 0.22);
  }
}
```

### Responsive Patterns

Same as standard responsive patterns (sidebar → bottom nav, multi-column → stacked, etc.)
but with extra attention to:
- Touch targets: minimum 44x44px
- Glass cards stacking vertically need sufficient gap to maintain visual separation
- Environment gradient blobs should reposition on mobile to keep visual interest
  behind the main content area

---

## Accessibility

All standard accessibility requirements apply — the glass aesthetic does not reduce
the obligation to be accessible. In fact, glass surfaces demand extra vigilance on
a few points.

### Non-Negotiable Requirements

1. **Semantic HTML first** — Glass is purely visual; it doesn't change the DOM structure.
2. **Keyboard navigation** — Every interactive element reachable via Tab. Focus order
   matches visual order.
3. **Labels for everything** — Unchanged from standard practice.
4. **Color is not the only indicator** — Especially important because glass surfaces
   mute colors. Always pair color with text, icons, or patterns.
5. **Contrast ratios** — 4.5:1 for normal text, 3:1 for large text. On glass surfaces
   this means testing against multiple background states (scrolled vs. not, dark area
   behind vs. light area behind).
6. **Announce dynamic changes** — `aria-live` for toasts, validation, etc.

### Focus Management on Glass

The default focus ring needs to be more vivid on glass surfaces — a thin outline can
disappear against a translucent background:

```css
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px var(--color-primary-glow);
}

:focus:not(:focus-visible) {
  outline: none;
  box-shadow: none;
}
```

The added glow shadow ensures the focus indicator is visible against any background.

### Forced Colors / High Contrast Mode

When `prefers-contrast: more` is active, increase glass surface opacity significantly
or fall back to solid backgrounds entirely:

```css
@media (prefers-contrast: more) {
  .glass,
  .glass-subtle,
  .glass-light,
  .glass-medium,
  .glass-heavy {
    background: var(--color-bg) !important;
    backdrop-filter: none !important;
    border: 2px solid var(--color-text-primary) !important;
  }
}
```

---

## Dark Mode

The liquid glass aesthetic is naturally dark-first. The default tokens above define the
dark theme. For a light mode variant, invert the glass approach:

```css
[data-theme="light"] {
  /* Light environment */
  --env-base: #f4f2ee;
  --env-blob-1: rgba(99, 102, 241, 0.08);
  --env-blob-2: rgba(168, 85, 247, 0.06);
  --env-blob-3: rgba(236, 72, 153, 0.05);

  /* Glass surfaces become white-tinted on light backgrounds */
  --glass-border: rgba(0, 0, 0, 0.08);
  --glass-highlight: rgba(255, 255, 255, 0.5);
  --glass-shadow: rgba(0, 0, 0, 0.08);

  --glass-subtle-bg: rgba(255, 255, 255, 0.4);
  --glass-light-bg: rgba(255, 255, 255, 0.5);
  --glass-medium-bg: rgba(255, 255, 255, 0.6);
  --glass-heavy-bg: rgba(255, 255, 255, 0.7);
  --glass-solid-bg: rgba(255, 255, 255, 0.85);

  /* Text */
  --color-text-primary: #1c1917;
  --color-text-secondary: #57534e;
  --color-text-tertiary: #a8a29e;
  --color-text-inverse: #fafaf9;
  --color-text-on-glass: #1c1917;

  /* Surface */
  --color-bg: #f4f2ee;
  --color-surface: rgba(255, 255, 255, 0.6);
  --color-surface-raised: rgba(255, 255, 255, 0.8);

  /* Borders */
  --color-border: rgba(0, 0, 0, 0.08);
  --color-border-subtle: rgba(0, 0, 0, 0.04);

  /* Shadows shift to neutral */
  --shadow-color-sm: rgba(0, 0, 0, 0.04);
  --shadow-color-md: rgba(0, 0, 0, 0.06);
  --shadow-color-lg: rgba(0, 0, 0, 0.1);
  --shadow-color-xl: rgba(0, 0, 0, 0.15);

  /* Glows are more subtle in light mode */
  --color-primary-glow: rgba(99, 102, 241, 0.2);
  --color-accent-glow: rgba(168, 85, 247, 0.15);
}
```

Key difference: in light mode, glass surfaces use **higher opacity whites** rather
than low opacity whites. The blur still works, but the frosted effect is brighter and
softer. Glows become less prominent — they're accent, not atmosphere.

---

## Visual Polish Checklist

Before delivering any component or page, verify:

**Glass Quality**
- [ ] Glass surfaces have consistent blur and opacity for their level
- [ ] Border highlights are present (1px translucent border + inset shadow)
- [ ] Glass cards have proper shadow compound (outer + inner highlight)
- [ ] Text on glass meets contrast requirements against all possible backgrounds
- [ ] Environment gradient is visible and provides enough visual texture behind glass
- [ ] No more than 3 layered blur surfaces stacked vertically (performance)

**Gradients**
- [ ] Primary gradient is consistent across all CTA buttons and key accents
- [ ] Gradient text uses `background-clip: text` only on headings/stats, never body text
- [ ] Gradient borders use the pseudo-element technique (for border-radius compatibility)
- [ ] No competing gradient directions — one dominant angle throughout

**Spacing & Alignment**
- [ ] All spacing uses design tokens (no magic numbers)
- [ ] Glass cards have generous padding (28px+ to keep content from touching edges)
- [ ] Content is properly constrained (max-width for readability)
- [ ] Nothing touches the viewport edge without padding

**Typography**
- [ ] Clear heading hierarchy (only one h1 per page)
- [ ] Body text on glass uses weight 500+ for legibility
- [ ] Long text is constrained to ~65 characters per line
- [ ] Gradient headings render correctly in both themes

**Color & Contrast**
- [ ] Text meets WCAG AA contrast ratios on glass surfaces (test multiple scroll positions)
- [ ] Interactive elements have visible hover glow + focus ring with glow
- [ ] Status colors work against translucent backgrounds
- [ ] Glow effects use the *-glow token variants, not ad-hoc opacities

**Interactivity**
- [ ] Buttons have gradient fill (primary) or glass surface (secondary) treatments
- [ ] Hover states include brightness/glow shift, not just color change
- [ ] Focus rings include glow shadow for visibility on glass
- [ ] Loading skeletons use the shimmer animation

**Mobile-First**
- [ ] Base CSS targets 320px — no media query needed for mobile
- [ ] Media queries use `min-width` only (never `max-width` for primary layout)
- [ ] Tested at 320px, 375px, 768px, 1024px, 1440px
- [ ] Touch targets are at least 44×44px on mobile
- [ ] No horizontal overflow at any viewport width
- [ ] Blur radius reduced on mobile for performance (max 3 blurred layers visible)
- [ ] Glass opacity increased on mobile to compensate for reduced blur
- [ ] Tested on real mobile devices (not just DevTools emulation)
- [ ] Sidebar collapses to bottom nav or hamburger on mobile
- [ ] Tables collapse to card layout on mobile
- [ ] Font sizes scale down appropriately (h1: 3rem desktop → 2.25rem mobile)

**Accessibility**
- [ ] Can complete all flows with keyboard only
- [ ] Focus ring + glow is visible against all glass surface levels
- [ ] `prefers-contrast: more` falls back to solid surfaces
- [ ] `prefers-reduced-motion` disables animations but keeps blur
- [ ] Screen reader announces content in logical order
- [ ] Every interactive element has a visible label (no icon-only buttons without aria-label)
- [ ] Heading hierarchy is correct (h1 → h2 → h3, no skips)

---

## CSS Reset & Global Styles

Include this reset in your global stylesheet (`GlobalStyles.tsx` or `index.css`).
It normalizes browser defaults and establishes sensible baselines for the glass system:

```css
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  scroll-behavior: smooth;
  -webkit-text-size-adjust: 100%;
  text-size-adjust: 100%;
}

body {
  min-height: 100dvh;
  font-family: var(--font-sans);
  font-weight: 500;
  line-height: 1.5;
  color: var(--text-primary);
  background-color: var(--bg);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

img, picture, video, canvas, svg {
  display: block;
  max-width: 100%;
}

input, button, textarea, select {
  font: inherit;
  color: inherit;
}

p, h1, h2, h3, h4, h5, h6 {
  overflow-wrap: break-word;
}

h1, h2, h3, h4, h5, h6 {
  text-wrap: balance;
}

a { color: inherit; text-decoration: none; }
button { cursor: pointer; border: none; background: none; }
ul, ol { list-style: none; }

/* Screen reader only utility */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Environment layer — the mesh gradient glass refracts against */
.environment {
  position: fixed;
  inset: 0;
  z-index: -1;
  background-color: var(--env-base);
  background-image:
    radial-gradient(ellipse at 20% 50%, var(--env-blob-1) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 20%, var(--env-blob-2) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 80%, var(--env-blob-3) 0%, transparent 50%);
  pointer-events: none;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

/* High contrast fallback */
@media (prefers-contrast: more) {
  .glass, [class*="glass-"] {
    background: var(--bg) !important;
    backdrop-filter: none !important;
    border: 2px solid var(--text-primary) !important;
  }
  .gradient-text, .heading-gradient {
    background: none !important;
    -webkit-text-fill-color: var(--text-primary) !important;
  }
}

/* Mobile glass performance optimization */
@media (max-width: 768px) {
  :root {
    --glass-medium-blur: 10px;
    --glass-heavy-blur: 14px;
    --glass-medium-bg: rgba(255, 255, 255, 0.14);
    --glass-heavy-bg: rgba(255, 255, 255, 0.22);
  }
}
```

