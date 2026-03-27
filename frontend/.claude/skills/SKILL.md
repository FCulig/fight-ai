---
name: react-typescript-app
description: >
  Build production-grade React web applications with TypeScript at senior/enterprise code quality.
  Use this skill whenever the user asks to create, build, scaffold, or develop a React application,
  React component, React page, React dashboard, or any web app using React and TypeScript. Also
  trigger when the user mentions "React app", "web app with React", "TypeScript frontend",
  "SPA", "single-page application", "React project", "component library", or asks to build
  any interactive UI that would naturally be implemented as a React application. This includes
  requests for dashboards, admin panels, CRUD apps, forms, data-driven UIs, portals, or any
  feature-rich interactive web interface. Even if the user doesn't explicitly say "React" or
  "TypeScript", use this skill when the complexity of the request clearly calls for a structured
  React application rather than a simple HTML page.
---

# React + TypeScript Web Application Skill

Build production-grade React applications with TypeScript that follow enterprise-level
architecture, clean code principles, and deliver polished, accessible user experiences.

Before writing any code, read the reference files relevant to your task:

- **Always read first**: `references/architecture.md` — Project structure, module boundaries, state management patterns, and code organization principles.
- **Always read first**: `references/design-system.md` — Liquid glass visual system: CSS tokens, glass surfaces, gradients, component styles, layout, responsive strategy, animations, and the complete copy-paste CSS system.
- **Always read first**: `references/semantic-and-a11y.md` — Semantic HTML in JSX, accessibility patterns, ARIA, SEO, performance, forms, media, and mobile-first responsive patterns.
- **When writing components**: All three files above cover what you need.
- **When setting up a project from scratch**: Read all files, then follow the scaffolding guide in `references/architecture.md`.

## Core Philosophy

This skill produces code that a senior engineer would be proud to review. Every decision
is intentional — from file placement to variable naming to the choice of abstraction.
The UI is not an afterthought; it is a first-class concern designed with the same rigor
as the architecture.

### The Four Pillars

1. **Type Safety as Documentation** — The type system is the living spec. Types communicate
   intent, constrain invalid states, and eliminate entire categories of bugs. Prefer
   discriminated unions over booleans, branded types over raw primitives for domain values,
   and `satisfies` over `as` for type-safe validation.

2. **Composition over Configuration** — Build small, focused units that compose into complex
   behavior. This applies to components (compound component pattern), hooks (composable
   custom hooks), styles (design tokens + utility composition), and state (slices over
   monoliths).

3. **Mobile-First, Always** — Every component, every layout, every interaction is designed
   for small screens first and enhanced upward. This is not a responsive "pass" at the end —
   it is the starting point. Base styles target 320px. Media queries add complexity with
   `min-width`. Touch targets are 44px minimum. Glass blur is performance-budgeted for
   mobile GPUs. If it doesn't work on a phone, it doesn't ship.

4. **User Experience is Non-Negotiable** — Every interaction is responsive, every state has
   feedback, every error has a recovery path. Accessibility is built-in from the start.
   Performance is a feature, not an optimization pass.

## Code Quality Standards

### TypeScript Discipline

```typescript
// ✗ Lazy typing — tells the reader nothing
const processData = (data: any) => { ... }

// ✓ The type IS the documentation
interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    pageSize: number;
    totalCount: number;
    totalPages: number;
  };
}

const processData = <T extends BaseEntity>(
  response: PaginatedResponse<T>
): ProcessedResult<T> => { ... }
```

Key rules:
- **No `any`**. Use `unknown` when the type is genuinely not known, then narrow.
- **No non-null assertions (`!`)**. Handle the null case explicitly.
- **No type assertions (`as`)** unless you've runtime-validated the shape. Prefer `satisfies`.
- **Discriminated unions for state machines**. A component that can be loading, idle, error,
  or success should be modeled as a union, not four booleans.
- **Readonly by default**. Props interfaces use `Readonly<>`, arrays use `readonly T[]`.
- **Branded types for domain identifiers**. `UserId`, `OrderId`, `Timestamp` — not `string`, `string`, `number`.
- **Strict mode always on**. `strict: true` in tsconfig, no exceptions.

### Component Architecture

Every component follows a consistent mental model:

```
┌─────────────────────────────────────┐
│           Props (Input)             │  ← What the parent controls
├─────────────────────────────────────┤
│     Internal State + Hooks          │  ← What the component owns
├─────────────────────────────────────┤
│     Derived / Computed Values       │  ← Pure transformations
├─────────────────────────────────────┤
│       Event Handlers                │  ← Side effects + callbacks
├─────────────────────────────────────┤
│            Render                   │  ← Pure function of above
└─────────────────────────────────────┘
```

Principles:
- **Single Responsibility**. If describing the component requires "and", split it.
- **Props down, events up**. No reaching into children's state.
- **Semantic JSX**. The render function produces meaningful HTML — `<header>`, `<nav>`,
  `<main>`, `<section>`, `<article>`, `<button>`, `<a>`, `<ul>`. Not `<div>` for everything.
  Every `<img>` has `alt`. Every form input has a `<label>`. Every icon button has `aria-label`.
  See `references/semantic-and-a11y.md` for the full list.
- **Mobile-first styles**. Base CSS targets mobile (320px). Use `min-width` media queries to
  enhance for larger screens. Touch targets are 44px minimum. No hover-only interactions —
  anything accessible on hover must also be accessible on tap.
- **Container / Presentational split** when a component mixes data-fetching with rendering.
  The container fetches; the presentational component is a pure function of its props.
- **Compound components** for related UI that shares implicit state (Tabs, Accordion, Select).
- **Render props or children-as-function** only when composition via children isn't enough.
- **forwardRef** for any component that wraps a native interactive element.
- **displayName** on every component that uses forwardRef or memo.

### Hook Patterns

```typescript
// ✓ A well-structured custom hook
function useDebounce<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debouncedValue;
}
```

Rules:
- Custom hooks extract **reusable stateful logic**, not just to reduce component size.
- Every hook that runs effects must clean them up.
- Dependencies arrays are exhaustive — rely on the linter, don't suppress it.
- Hooks that return complex objects should memoize with `useMemo` to maintain referential stability.
- Name hooks `use<Noun>` or `use<Verb><Noun>` — `useAuth`, `useFetchUsers`, `useFormValidation`.

### Error Handling

- **Error Boundaries** at every route level and around any component that fetches data.
- **Typed error states** in async operations — never swallow errors silently.
- **User-facing error messages** are human-readable, never raw error strings.
- **Retry mechanisms** for transient network failures.
- **Fallback UI** that lets users recover without reloading.

```typescript
// Discriminated union for async state
type AsyncState<T, E = Error> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: E };
```

### Performance Defaults

- **React.memo** on components that receive complex props and re-render often.
- **useMemo / useCallback** where profiling shows unnecessary re-renders (don't premature-optimize).
- **Lazy loading** via `React.lazy` + Suspense for route-level code splitting.
- **Virtualization** for lists over ~100 items.
- **Image optimization** — proper formats, lazy loading, explicit dimensions.
- **Bundle awareness** — no importing an entire library for one utility function.

### Naming Conventions

| Thing              | Convention                 | Example                      |
|--------------------|----------------------------|------------------------------|
| Component files    | PascalCase.tsx             | `UserProfile.tsx`            |
| Hook files         | camelCase.ts               | `useAuth.ts`                 |
| Utility files      | camelCase.ts               | `formatCurrency.ts`          |
| Type files         | camelCase.types.ts         | `user.types.ts`              |
| Test files         | *.test.ts(x)               | `UserProfile.test.tsx`       |
| Constants          | SCREAMING_SNAKE_CASE       | `MAX_RETRY_COUNT`            |
| CSS modules        | ComponentName.module.css   | `UserProfile.module.css`     |
| Enum values        | PascalCase                 | `UserRole.Admin`             |
| Event handlers     | handle<Event>              | `handleSubmit`, `handleClick`|
| Boolean props      | is/has/should prefix       | `isDisabled`, `hasError`     |

### File Organization

Refer to `references/architecture.md` for the complete project structure. The high-level
principle: organize by **feature** (not by type) once a project exceeds ~15 components.

```
src/
├── features/           ← Feature modules (self-contained)
│   ├── auth/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   └── index.ts    ← Public API barrel
│   └── dashboard/
├── shared/             ← Cross-cutting concerns
│   ├── components/     ← Reusable UI primitives
│   ├── hooks/
│   ├── utils/
│   └── types/
├── design-system/      ← Tokens, theme, global styles
└── app/                ← App shell, routing, providers
```

## Working Process

When building a React + TypeScript application:

1. **Clarify requirements** — Understand the domain, user flows, and edge cases before touching code.
2. **Define the type model first** — Types are the blueprint. Write interfaces and unions for the domain before components.
3. **Design mobile-first** — Start every layout and component from the smallest viewport (320px).
   Sketch the mobile version mentally before the desktop version. Ask: what stacks? What
   collapses? What hides behind a menu? What's the touch target size?
4. **Design the component tree** — Sketch the hierarchy mentally. Identify shared state, data flow, and composition points.
5. **Build bottom-up** — Start with leaf components (buttons, inputs, cards), compose into features, then assemble pages.
6. **Use semantic HTML in JSX** — Every component renders meaningful markup. `<nav>`, `<main>`,
   `<section>`, `<article>`, `<button>`, `<a>` — not div soup. See `references/semantic-and-a11y.md`.
7. **Style with intention** — Follow `references/design-system.md`. Every visual decision has a reason.
   Use the token system — no magic numbers. Apply glass surfaces at the appropriate intensity level.
8. **Handle every state** — Loading, empty, error, success, partial data. No component is "done" until all states render gracefully.
9. **Test across viewports** — Verify at 320px, 375px, 768px, 1024px, 1440px. Check glass blur
   performance on mobile. Confirm touch targets are 44px+. Verify no horizontal overflow.
10. **Accessibility audit** — Keyboard-navigate every flow. Verify heading order. Check contrast
    on glass surfaces at multiple scroll positions. Test `prefers-reduced-motion` and
    `prefers-contrast: more` fallbacks. See `references/semantic-and-a11y.md`.
11. **Review your own code** — Before delivering, re-read as if reviewing a PR. Would you approve this?

## What "Enterprise Quality" Means in Practice

It's not about complexity for its own sake. It means:

- A new team member can read any file and understand what it does within 30 seconds.
- Types prevent bugs that tests would otherwise have to catch.
- Every component renders semantic HTML — `<button>` not `<div onClick>`, `<nav>` not
  `<div className="nav">`. The DOM reads like a document, not a grid of anonymous boxes.
- The application handles real-world conditions: slow networks, missing data, concurrent updates, browser back-button, deep links, screen readers.
- Code changes in one feature don't break another — module boundaries are real.
- **The UI is mobile-first.** Every layout starts at 320px and scales up. There is no
  "desktop version" that gets squeezed into mobile later. Mobile is the foundation;
  desktop is the enhancement.
- The UI works with keyboard-only navigation. It works with screen readers. It respects
  `prefers-reduced-motion` and `prefers-contrast`.
- Error states are not afterthoughts. Loading states are not afterthoughts. Empty states
  are not afterthoughts.
- CSS uses the design token system exclusively — no hardcoded colors, spacing, or font
  sizes. Glass surfaces use the leveled system (`glass-subtle` through `glass-solid`).
  Gradients follow the defined roles (primary, accent, surface, shimmer, glow).
