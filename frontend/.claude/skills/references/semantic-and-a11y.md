# Semantic HTML & Accessibility in React — Mobile-First

Semantic markup, accessibility patterns, ARIA, SEO, performance, forms, media, and
mobile-first responsive patterns — all in the context of React + TypeScript with JSX.

## Table of Contents

1. [Semantic JSX](#semantic-jsx)
2. [Document Structure](#document-structure)
3. [Common Section Components](#common-section-components)
4. [Accessibility Patterns](#accessibility-patterns)
5. [Mobile-First Responsive Patterns](#mobile-first-responsive-patterns)
6. [SEO in React SPAs](#seo-in-react-spas)
7. [Performance Patterns](#performance-patterns)
8. [Forms](#forms)
9. [Media](#media)

---

## Semantic JSX

React outputs HTML. That HTML must be semantic. JSX makes it easy to fall into
`<div>` soup because `div` is the path of least resistance. Resist it.

### The Semantic Element Map

Use this as a quick reference when deciding which element to render:

| Instead of...             | Use...                        | Why                                      |
|---------------------------|-------------------------------|------------------------------------------|
| `<div onClick={...}>`     | `<button onClick={...}>`      | Keyboard accessible, focusable by default |
| `<div className="nav">`   | `<nav aria-label="...">`      | Landmark for screen readers               |
| `<div className="header">`| `<header>`                    | Banner landmark                           |
| `<div className="main">`  | `<main>`                      | Main content landmark                     |
| `<div className="footer">`| `<footer>`                    | Contentinfo landmark                      |
| `<div className="card">`  | `<article>`                   | Self-contained content unit               |
| `<div className="sidebar">`| `<aside>`                    | Complementary content                     |
| `<div>` for grouping      | `<section aria-labelledby>` | Thematic group with a heading             |
| `<span onClick={...}>`    | `<a href={...}>`              | Navigation, has native link behavior      |
| `<div className="list">`  | `<ul>` or `<ol>`              | List semantics for screen readers         |
| `<img>` without alt       | `<img alt="description">`     | Required. Empty `alt=""` for decorative.  |

### JSX-Specific Rules

```tsx
// ✗ Div soup — no meaning, no accessibility, no keyboard support
<div className="header">
  <div className="nav">
    <div className="link" onClick={() => navigate('/')}>Home</div>
  </div>
</div>

// ✓ Semantic, accessible, keyboard-navigable
<header className={styles.header}>
  <nav aria-label="Main navigation">
    <Link to="/" aria-current={isHome ? 'page' : undefined}>Home</Link>
  </nav>
</header>
```

Key rules for JSX:
- **`className` not `class`** — obvious, but worth stating for the semantic mapping.
- **`htmlFor` not `for`** on `<label>` elements.
- **Boolean attributes**: `disabled` not `disabled={true}`, but `aria-expanded={isOpen}`
  (ARIA attributes need the explicit value).
- **Fragments over wrapper divs**: `<>...</>` when you need a parent but no DOM element.
- **`role` as a last resort** — if the semantic element exists, use it instead of
  `<div role="button">`. The exception: `role="list"` on styled `<ul>` elements where
  list-style removal in Safari strips the role.

---

## Document Structure

### App Shell Pattern

The root layout component establishes the landmark structure:

```tsx
function AppLayout() {
  return (
    <>
      {/* Environment gradient — glass needs something to refract */}
      <div className="environment" aria-hidden="true" />

      {/* Skip link for keyboard users */}
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <Header />

      <main id="main-content">
        <Outlet /> {/* React Router nested routes */}
      </main>

      <Footer />
    </>
  );
}
```

### Skip Link Component

```tsx
function SkipLink() {
  return (
    <a href="#main-content" className={styles.skipLink}>
      Skip to main content
    </a>
  );
}

// CSS Module
.skipLink {
  position: absolute;
  left: -9999px;
  top: auto;
  width: 1px;
  height: 1px;
  overflow: hidden;
  z-index: 100;
}

.skipLink:focus {
  position: fixed;
  top: var(--space-4);
  left: var(--space-4);
  width: auto;
  height: auto;
  padding: var(--space-3) var(--space-5);
  background: var(--gradient-primary);
  color: white;
  border-radius: var(--radius-md);
  font-weight: 600;
  z-index: 100;
}
```

### Page Component Pattern

Every route-level page component follows this structure:

```tsx
function DashboardPage() {
  return (
    <>
      <Head title="Dashboard" description="Your project overview." />

      <section aria-labelledby="stats-heading">
        <h1 id="stats-heading" className="heading-gradient">Dashboard</h1>
        <StatsGrid />
      </section>

      <section aria-labelledby="activity-heading">
        <h2 id="activity-heading">Recent Activity</h2>
        <ActivityFeed />
      </section>
    </>
  );
}
```

Each `<section>` has a heading and `aria-labelledby` pointing to it. This gives
screen readers a navigable outline of the page.

---

## Common Section Components

### Navigation Header

```tsx
interface NavItem {
  readonly label: string;
  readonly href: string;
}

function Header({ items }: { readonly items: readonly NavItem[] }) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className={cn('glass glass-medium', styles.header)}>
      <div className={styles.headerInner}>
        <Link to="/" className={styles.logo} aria-label="Homepage">
          <span className="gradient-text">Brand</span>
        </Link>

        <nav
          aria-label="Main navigation"
          className={cn(styles.nav, isMenuOpen && styles.navOpen)}
          id="main-nav"
        >
          <ul role="list" className={styles.navList}>
            {items.map((item) => (
              <li key={item.href}>
                <NavLink
                  to={item.href}
                  className={({ isActive }) =>
                    cn(styles.navLink, isActive && styles.navLinkActive)
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <button
          className={styles.menuToggle}
          onClick={() => setIsMenuOpen((prev) => !prev)}
          aria-expanded={isMenuOpen}
          aria-controls="main-nav"
          aria-label="Toggle navigation menu"
        >
          <span className={styles.menuBar} />
          <span className={styles.menuBar} />
          <span className={styles.menuBar} />
        </button>
      </div>
    </header>
  );
}
```

The mobile toggle uses `aria-expanded` and `aria-controls`. CSS reads
`aria-expanded` for styling, JS only toggles the boolean.

### Hero Section

```tsx
function Hero() {
  return (
    <section className={styles.hero} aria-labelledby="hero-heading">
      <div className={styles.heroContent}>
        <p className="label-caps">Introducing v2.0</p>
        <h1 id="hero-heading">
          <span className="heading-gradient">Build faster.</span>
          <br />
          Ship with confidence.
        </h1>
        <p className={styles.heroDescription}>
          A concise value proposition — one or two sentences max.
        </p>
        <div className={styles.heroActions}>
          <Link to="/signup" className="btn btn-primary btn-lg">Get started free</Link>
          <Link to="#demo" className="btn btn-secondary btn-lg">See it in action</Link>
        </div>
      </div>
    </section>
  );
}
```

### Feature Card Grid

```tsx
interface Feature {
  readonly icon: ReactNode;
  readonly title: string;
  readonly description: string;
}

function FeatureGrid({ features }: { readonly features: readonly Feature[] }) {
  return (
    <div className="grid-auto">
      {features.map((feature) => (
        <article key={feature.title} className="card glass glass-medium">
          <div className={styles.featureIcon} aria-hidden="true">
            {feature.icon}
          </div>
          <h3>{feature.title}</h3>
          <p className="text-secondary">{feature.description}</p>
        </article>
      ))}
    </div>
  );
}
```

`<article>` because each card is self-contained. Icon is `aria-hidden` because the
title provides the label.

### Footer

```tsx
interface FooterNavGroup {
  readonly heading: string;
  readonly links: readonly { label: string; href: string }[];
}

function Footer({ navGroups }: { readonly navGroups: readonly FooterNavGroup[] }) {
  return (
    <footer className={cn('glass glass-light', styles.footer)}>
      <div className={styles.footerInner}>
        <div className={styles.footerBrand}>
          <span className="gradient-text logo-text">Brand</span>
          <p className="text-secondary text-sm">A short tagline.</p>
        </div>

        <nav aria-label="Footer navigation" className={styles.footerNav}>
          {navGroups.map((group) => (
            <div key={group.heading}>
              <h3 className="label-caps">{group.heading}</h3>
              <ul role="list">
                {group.links.map((link) => (
                  <li key={link.href}>
                    <Link to={link.href}>{link.label}</Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <p className="text-tertiary text-xs">
          &copy; {new Date().getFullYear()} Brand. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
```

---

## Accessibility Patterns

### Focus Management

```css
/* Glow-enhanced focus ring — visible on glass surfaces */
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

### Focus Trapping (Modals, Drawers)

When a modal or drawer opens, focus must be trapped inside it and returned to the
trigger on close. Use the native `<dialog>` element or a library like `@radix-ui/react-dialog`
which handles this correctly.

```tsx
function Modal({ isOpen, onClose, children }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen) {
      dialog.showModal();
    } else {
      dialog.close();
    }
  }, [isOpen]);

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      className={cn('glass glass-heavy', styles.modal)}
    >
      {children}
    </dialog>
  );
}
```

Native `<dialog>` with `showModal()` gives you focus trapping, Escape to close,
and the backdrop — for free.

### Screen Reader Utilities

```tsx
// Visually hidden but announced by screen readers
function ScreenReaderOnly({ children }: { readonly children: ReactNode }) {
  return <span className="sr-only">{children}</span>;
}

// Usage
<button aria-label="Close dialog">
  <XIcon aria-hidden="true" />
</button>

// Or when you need both visible text and extra context:
<button>
  Delete
  <ScreenReaderOnly>user John Smith</ScreenReaderOnly>
</button>
```

### Live Regions

For content that updates dynamically (toasts, form validation, search results count):

```tsx
function LiveAnnouncer() {
  const [message, setMessage] = useState('');

  // Expose setMessage via context or a custom hook
  return (
    <div role="status" aria-live="polite" className="sr-only">
      {message}
    </div>
  );
}
```

### ARIA Quick Reference for React

| Pattern                        | ARIA                                          |
|--------------------------------|-----------------------------------------------|
| Hamburger toggle               | `aria-expanded={isOpen}` `aria-controls="id"` |
| Current page in nav            | `aria-current="page"`                         |
| Section with heading           | `aria-labelledby="heading-id"`                |
| Icon-only button               | `aria-label="Action description"`             |
| Loading indicator              | `aria-busy={true}` on the loading container   |
| Error message linked to input  | `aria-describedby="error-id"` on input        |
| Invalid input                  | `aria-invalid={true}`                         |
| Sortable table column          | `aria-sort="ascending"` or `"descending"`     |
| Tab panel                      | `role="tablist"`, `role="tab"`, `role="tabpanel"` |
| Expandable accordion           | `aria-expanded` on trigger, `aria-controls`   |

### High Contrast Fallback

When `prefers-contrast: more` is active, glass surfaces become unreadable. Fall back
to solid backgrounds:

```css
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

  .btn-primary {
    background: var(--color-primary) !important;
    box-shadow: none !important;
  }
}
```

---

## Mobile-First Responsive Patterns

### The Mobile-First Rule

**This is the most important section in this file.** Every component is designed for
mobile first. Not "also works on mobile" — mobile IS the default.

```css
/* ✗ Desktop-first: starts wide, then overrides for mobile */
.grid { grid-template-columns: repeat(3, 1fr); }
@media (max-width: 768px) {
  .grid { grid-template-columns: 1fr; }  /* Undoing the desktop layout */
}

/* ✓ Mobile-first: starts narrow, enhances for wider */
.grid { grid-template-columns: 1fr; }
@media (min-width: 768px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}
@media (min-width: 1024px) {
  .grid { grid-template-columns: repeat(3, 1fr); }
}
```

### Breakpoints

```typescript
export const breakpoints = {
  sm: '640px',    // Large phones landscape
  md: '768px',    // Tablets
  lg: '1024px',   // Small laptops
  xl: '1280px',   // Desktops
  '2xl': '1536px', // Large desktops
} as const;
```

### useMediaQuery Hook

```typescript
function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false
  );

  useEffect(() => {
    const mql = window.matchMedia(query);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, [query]);

  return matches;
}

// Usage
const isDesktop = useMediaQuery('(min-width: 1024px)');
```

Use `useMediaQuery` sparingly — prefer CSS media queries for layout changes. Reserve
the hook for cases where you need to render fundamentally different component trees
(e.g., a sidebar on desktop vs. a bottom sheet on mobile).

### Common Responsive Patterns

**Sidebar → Bottom Navigation**
```css
.app-layout {
  display: grid;
  grid-template-rows: 1fr auto; /* Content + bottom nav */
}

.sidebar { display: none; }
.bottom-nav { display: flex; }

@media (min-width: 1024px) {
  .app-layout {
    grid-template-columns: 260px 1fr;
    grid-template-rows: 1fr;
  }
  .sidebar { display: flex; }
  .bottom-nav { display: none; }
}
```

**Stacked → Side-by-Side**
```css
.split-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

@media (min-width: 768px) {
  .split-layout {
    flex-direction: row;
  }
}
```

**Table → Card List on Mobile**
```tsx
function DataDisplay<T extends { id: string }>({
  data,
  columns,
}: DataDisplayProps<T>) {
  const isDesktop = useMediaQuery('(min-width: 768px)');

  if (isDesktop) {
    return <DataTable data={data} columns={columns} />;
  }

  return (
    <div className={styles.cardList}>
      {data.map((item) => (
        <DataCard key={item.id} item={item} columns={columns} />
      ))}
    </div>
  );
}
```

**Inline Actions → Overflow Menu**
```tsx
function RowActions({ actions }: { readonly actions: readonly Action[] }) {
  const isDesktop = useMediaQuery('(min-width: 768px)');

  if (isDesktop) {
    return (
      <div className={styles.inlineActions}>
        {actions.map((action) => (
          <Button key={action.id} variant="ghost" size="sm" onClick={action.handler}>
            {action.label}
          </Button>
        ))}
      </div>
    );
  }

  return <OverflowMenu actions={actions} />;
}
```

### Touch Target Sizing

Every interactive element must be at least 44×44px on mobile. This includes buttons,
links, checkboxes, radio buttons, and any tappable area:

```css
/* Minimum touch target */
.btn {
  min-height: 44px;
  min-width: 44px;
}

/* For small visual elements, expand the tap area with padding or ::after */
.icon-button {
  position: relative;
  width: 24px;
  height: 24px;
}

.icon-button::after {
  content: '';
  position: absolute;
  inset: -10px; /* Expand tap area to 44px */
}
```

### Glass Performance on Mobile

`backdrop-filter: blur()` is GPU-intensive. Budget for mobile:

```css
@media (max-width: 768px) {
  :root {
    /* Reduce blur, increase opacity to compensate */
    --glass-medium-blur: 10px;
    --glass-heavy-blur: 14px;
    --glass-medium-bg: rgba(255, 255, 255, 0.14);
    --glass-heavy-bg: rgba(255, 255, 255, 0.22);
  }
}
```

Rules:
- **Maximum 3 blurred layers** visible at once on mobile (e.g., header + one card + modal).
- **Reduce blur radius** from desktop values. 16px → 10px, 24px → 14px.
- **Increase surface opacity** to compensate for less blur.
- **Test on real devices** — Chrome DevTools mobile emulation does not accurately
  represent blur performance.

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Respect the user's preference. Disable animations but keep glass blur (the blur itself
isn't motion).

---

## SEO in React SPAs

### Document Head Management

Use `react-helmet-async` or a framework-level head manager to set per-page meta:

```tsx
function Head({
  title,
  description,
}: {
  readonly title: string;
  readonly description: string;
}) {
  return (
    <Helmet>
      <title>{title} — Brand</title>
      <meta name="description" content={description} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
    </Helmet>
  );
}
```

### Heading Hierarchy

Search engines and screen readers use headings to understand page structure:

```
h1: Page title (one per route/page)
  h2: Major section (Features, Pricing, Activity Feed)
    h3: Subsection (individual feature, card title)
      h4: Detail (rarely needed)
```

Never skip levels. Never use headings for visual sizing — use CSS classes.

### Structured Data

For product/service pages, add JSON-LD in the document head:

```tsx
function StructuredData({ data }: { readonly data: Record<string, unknown> }) {
  return (
    <Helmet>
      <script type="application/ld+json">{JSON.stringify(data)}</script>
    </Helmet>
  );
}
```

---

## Performance Patterns

### Font Loading

```html
<!-- In index.html — preconnect before stylesheet -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
```

Load only the weights you use. `display=swap` prevents invisible text during loading.

### Image Component

```tsx
interface OptimizedImageProps {
  readonly src: string;
  readonly alt: string;
  readonly width: number;
  readonly height: number;
  readonly priority?: boolean;
  readonly className?: string;
}

function OptimizedImage({
  src,
  alt,
  width,
  height,
  priority = false,
  className,
}: OptimizedImageProps) {
  return (
    <img
      src={src}
      alt={alt}
      width={width}
      height={height}
      loading={priority ? 'eager' : 'lazy'}
      decoding="async"
      className={className}
    />
  );
}
```

Always specify `width` and `height` to prevent layout shift. Images above the fold
use `priority` (no lazy loading). Everything else lazy-loads.

### Code Splitting

```tsx
const DashboardPage = lazy(() => import('@features/dashboard/pages/DashboardPage'));
const SettingsPage = lazy(() => import('@features/settings/pages/SettingsPage'));

// In router
<Suspense fallback={<PageSkeleton />}>
  <DashboardPage />
</Suspense>
```

Every route-level page component should be lazy-loaded. The `PageSkeleton` fallback
uses the shimmer animation from the glass design system.

---

## Forms

### Accessible Form Component

```tsx
interface TextFieldProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  readonly label: string;
  readonly error?: string;
  readonly hint?: string;
}

const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  ({ label, error, hint, id: providedId, ...inputProps }, ref) => {
    const generatedId = useId();
    const id = providedId ?? generatedId;
    const errorId = `${id}-error`;
    const hintId = `${id}-hint`;

    return (
      <div className={styles.formGroup}>
        <label htmlFor={id} className={styles.formLabel}>
          {label}
        </label>
        <input
          ref={ref}
          id={id}
          className={cn(styles.input, error && styles.inputError)}
          aria-invalid={!!error}
          aria-describedby={
            [error && errorId, hint && hintId].filter(Boolean).join(' ') || undefined
          }
          {...inputProps}
        />
        {hint && !error && (
          <p id={hintId} className={styles.formHint}>{hint}</p>
        )}
        {error && (
          <p id={errorId} className={styles.formError} role="alert">{error}</p>
        )}
      </div>
    );
  }
);

TextField.displayName = 'TextField';
```

Key accessibility points:
- `htmlFor` + `id` links label to input.
- `aria-invalid` marks errored fields.
- `aria-describedby` links to hint and/or error text.
- Error uses `role="alert"` for screen reader announcement.
- `useId()` generates unique IDs (React 18+).
- `forwardRef` allows parent forms to focus the input.

---

## Media

### Responsive Video Embed

```tsx
function VideoEmbed({
  src,
  title,
}: {
  readonly src: string;
  readonly title: string;
}) {
  return (
    <div className={cn('glass glass-medium', styles.videoWrapper)}>
      <iframe
        src={src}
        title={title}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
        loading="lazy"
      />
    </div>
  );
}
```

```css
.videoWrapper {
  position: relative;
  padding-bottom: 56.25%; /* 16:9 */
  height: 0;
  overflow: hidden;
  border-radius: var(--radius-lg);
}

.videoWrapper iframe {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 0;
}
```

### Inline SVG Icons

For icons alongside text, inline SVG inherits `currentColor` and scales with font size:

```tsx
interface IconProps {
  readonly size?: number;
  readonly className?: string;
}

function PlusIcon({ size = 20, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
      className={className}
    >
      <path d="M10 2v16M2 10h16" />
    </svg>
  );
}

// Usage — icon is decorative, button text provides the label
<button className="btn btn-primary">
  <PlusIcon />
  <span>Add item</span>
</button>

// Icon-only button — needs aria-label
<button className="btn btn-ghost" aria-label="Close dialog">
  <XIcon />
</button>
```

`aria-hidden="true"` on the SVG because the button text or `aria-label` provides
the accessible name. Never leave an icon button without a label.
