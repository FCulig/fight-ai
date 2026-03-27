# Architecture Reference

Detailed patterns for project structure, state management, data fetching, routing,
and module boundaries in a production React + TypeScript application.

## Table of Contents

1. [Project Scaffolding](#project-scaffolding)
2. [Feature Module Pattern](#feature-module-pattern)
3. [State Management](#state-management)
4. [Data Fetching & Server State](#data-fetching--server-state)
5. [Routing](#routing)
6. [Form Handling](#form-handling)
7. [Testing Strategy](#testing-strategy)
8. [Error Boundaries & Recovery](#error-boundaries--recovery)
9. [Environment & Configuration](#environment--configuration)
10. [Code Patterns Catalog](#code-patterns-catalog)

---

## Project Scaffolding

Use Vite as the build tool — it's the modern standard for React + TypeScript projects.

### tsconfig.json — Strict by Default

```jsonc
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "exactOptionalPropertyTypes": true,
    "forceConsistentCasingInFileNames": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@features/*": ["./src/features/*"],
      "@shared/*": ["./src/shared/*"],
      "@design-system/*": ["./src/design-system/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

The non-obvious flags explained:
- `noUncheckedIndexedAccess` — array[0] returns `T | undefined`, forcing you to handle missing values.
- `exactOptionalPropertyTypes` — distinguishes `{ x?: string }` from `{ x: string | undefined }`.
  The former means "may be absent", the latter means "present but undefined". This distinction matters.

### Complete Directory Structure

```
project-root/
├── public/
│   └── assets/              ← Static assets (favicons, og-images)
├── src/
│   ├── app/                 ← Application shell
│   │   ├── App.tsx          ← Root component, provider composition
│   │   ├── Router.tsx       ← Route definitions
│   │   ├── Providers.tsx    ← All context providers composed
│   │   └── GlobalStyles.ts  ← CSS reset, global baseline
│   │
│   ├── features/            ← Feature modules (the bulk of the app)
│   │   ├── auth/
│   │   │   ├── components/
│   │   │   │   ├── LoginForm.tsx
│   │   │   │   ├── SignupForm.tsx
│   │   │   │   └── ProtectedRoute.tsx
│   │   │   ├── hooks/
│   │   │   │   ├── useAuth.ts
│   │   │   │   └── useSession.ts
│   │   │   ├── services/
│   │   │   │   └── authApi.ts
│   │   │   ├── stores/
│   │   │   │   └── authStore.ts
│   │   │   ├── types/
│   │   │   │   └── auth.types.ts
│   │   │   └── index.ts     ← Public API — only export what others need
│   │   │
│   │   └── dashboard/
│   │       ├── components/
│   │       ├── hooks/
│   │       ├── services/
│   │       ├── types/
│   │       └── index.ts
│   │
│   ├── shared/              ← Cross-feature reusable code
│   │   ├── components/
│   │   │   ├── ui/          ← Primitive UI components (Button, Input, Modal)
│   │   │   ├── layout/      ← Shell, Sidebar, Header, PageContainer
│   │   │   └── feedback/    ← Toast, Spinner, ErrorFallback, EmptyState
│   │   ├── hooks/
│   │   │   ├── useDebounce.ts
│   │   │   ├── useMediaQuery.ts
│   │   │   ├── useClickOutside.ts
│   │   │   └── useLocalStorage.ts
│   │   ├── utils/
│   │   │   ├── formatters.ts
│   │   │   ├── validators.ts
│   │   │   ├── cn.ts        ← Class name merge utility
│   │   │   └── invariant.ts
│   │   ├── types/
│   │   │   ├── api.types.ts
│   │   │   └── common.types.ts
│   │   └── constants/
│   │       └── config.ts
│   │
│   ├── design-system/       ← Theme, tokens, global visual identity
│   │   ├── tokens.ts        ← Color, spacing, typography tokens
│   │   ├── theme.ts         ← Composed theme object
│   │   ├── GlobalStyles.tsx ← CSS reset + base styles
│   │   └── breakpoints.ts   ← Responsive breakpoints
│   │
│   ├── services/            ← Infrastructure (API client, auth interceptors)
│   │   ├── apiClient.ts
│   │   └── storage.ts
│   │
│   └── main.tsx             ← Entry point
│
├── .env                     ← Local env vars (git-ignored)
├── .env.example             ← Documented env var template
├── vite.config.ts
├── tsconfig.json
└── package.json
```

### Barrel Exports (index.ts)

Every feature module has an `index.ts` that explicitly defines its public API:

```typescript
// features/auth/index.ts
export { LoginForm } from './components/LoginForm';
export { ProtectedRoute } from './components/ProtectedRoute';
export { useAuth } from './hooks/useAuth';
export type { User, AuthState, LoginCredentials } from './types/auth.types';
```

Why this matters: It enforces module boundaries. Other features import from `@features/auth`,
never from `@features/auth/components/LoginForm`. If a refactor moves `LoginForm` to a
different internal path, only the barrel file changes.

---

## Feature Module Pattern

A feature module is a self-contained vertical slice of the application. It owns its
components, hooks, services, types, and state. It exports only what other modules need.

### Rules of Feature Modules

1. **A feature can import from `shared/` and `design-system/`**. These are the "standard library."
2. **A feature can import from another feature's `index.ts`** — never from its internals.
3. **A feature never reaches up to `app/`**. If a feature needs app-level context, it
   receives it via props or a shared provider.
4. **Circular dependencies between features mean the boundary is wrong**. Extract the
   shared concern into `shared/` or create a new feature.

### When to Create a Feature Module

A feature module is warranted when a piece of functionality has:
- Its own route or set of routes
- Its own domain types (not just shared primitives)
- At least 2-3 components that work together
- State or data that other features shouldn't directly access

If the code is a single reusable component with no domain logic, it belongs in `shared/components/`.

---

## State Management

Choose the lightest tool that solves the problem. State management complexity should
match the state's complexity — not exceed it.

### State Decision Tree

```
Is it server/async data? (API responses, cached entities)
  → React Query / TanStack Query. Stop here.

Is it URL-derived? (current page, filters, sort order, search params)
  → URL state (useSearchParams, route params). Stop here.

Is it form state? (input values, validation, dirty tracking)
  → React Hook Form or local useState. Stop here.

Is it shared across distant components? (theme, auth, locale, feature flags)
  → Context + useReducer for simple cases.
  → Zustand for complex cases (many subscribers, computed values, devtools).

Is it local to one component? (toggle, hover, open/close)
  → useState. Stop here.
```

### Zustand Pattern (When You Need a Store)

```typescript
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

interface NotificationStore {
  readonly notifications: readonly Notification[];
  addNotification: (notification: Omit<Notification, 'id' | 'createdAt'>) => void;
  dismissNotification: (id: NotificationId) => void;
  clearAll: () => void;
}

export const useNotificationStore = create<NotificationStore>()(
  devtools(
    immer(
      persist(
        (set) => ({
          notifications: [],

          addNotification: (notification) =>
            set((state) => {
              state.notifications.push({
                ...notification,
                id: crypto.randomUUID() as NotificationId,
                createdAt: Date.now() as Timestamp,
              });
            }),

          dismissNotification: (id) =>
            set((state) => {
              state.notifications = state.notifications.filter((n) => n.id !== id);
            }),

          clearAll: () =>
            set((state) => {
              state.notifications = [];
            }),
        }),
        { name: 'notification-store' }
      )
    ),
    { name: 'NotificationStore' }
  )
);
```

Key patterns:
- Use `immer` middleware for immutable updates with mutable syntax.
- Use `devtools` in development for debugging.
- Use `persist` only for state that genuinely survives page reloads.
- Use selectors to avoid unnecessary re-renders: `useNotificationStore((s) => s.notifications)`.

### Context Pattern (For Simple Shared State)

```typescript
interface ThemeContextValue {
  readonly theme: Theme;
  readonly toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { readonly children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>('light');

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  }, []);

  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (context === null) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
```

The `null` initial value + runtime check pattern is important. It catches the "forgot to
wrap in provider" mistake immediately at the call site, rather than producing subtle
undefined-related bugs downstream.

---

## Data Fetching & Server State

Use TanStack Query (React Query) for all server state. Raw `useEffect` + `fetch` is an
anti-pattern for anything beyond a one-off prototype.

### Query Pattern

```typescript
// services/usersApi.ts
const USERS_QUERY_KEY = ['users'] as const;

export function useUsers(filters: UserFilters) {
  return useQuery({
    queryKey: [...USERS_QUERY_KEY, filters],
    queryFn: () => apiClient.get<PaginatedResponse<User>>('/users', { params: filters }),
    staleTime: 5 * 60 * 1000,  // 5 minutes
    placeholderData: keepPreviousData,
  });
}

export function useUser(id: UserId) {
  return useQuery({
    queryKey: [...USERS_QUERY_KEY, id],
    queryFn: () => apiClient.get<User>(`/users/${id}`),
    enabled: !!id,
  });
}
```

### Mutation Pattern

```typescript
export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateUserPayload) =>
      apiClient.patch<User>(`/users/${data.id}`, data),

    onMutate: async (newData) => {
      // Optimistic update
      await queryClient.cancelQueries({ queryKey: USERS_QUERY_KEY });
      const previousUsers = queryClient.getQueryData(USERS_QUERY_KEY);
      queryClient.setQueryData(USERS_QUERY_KEY, (old: User[] | undefined) =>
        old?.map((user) => (user.id === newData.id ? { ...user, ...newData } : user))
      );
      return { previousUsers };
    },

    onError: (_err, _newData, context) => {
      // Rollback on failure
      if (context?.previousUsers) {
        queryClient.setQueryData(USERS_QUERY_KEY, context.previousUsers);
      }
    },

    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
    },
  });
}
```

### API Client

```typescript
// services/apiClient.ts
class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('GET', path, options);
  }

  async post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>('POST', path, { ...options, body });
  }

  // ... patch, put, delete

  private async request<T>(
    method: string,
    path: string,
    options?: RequestOptions & { body?: unknown }
  ): Promise<T> {
    const url = new URL(path, this.baseUrl);

    if (options?.params) {
      Object.entries(options.params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.set(key, String(value));
        }
      });
    }

    const response = await fetch(url.toString(), {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
        ...options?.headers,
      },
      body: options?.body ? JSON.stringify(options.body) : undefined,
      signal: options?.signal,
    });

    if (!response.ok) {
      throw await ApiError.fromResponse(response);
    }

    return response.json() as Promise<T>;
  }

  private getAuthHeaders(): Record<string, string> {
    const token = getStoredToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }
}

export const apiClient = new ApiClient(import.meta.env.VITE_API_BASE_URL);
```

---

## Routing

Use React Router v6+ with type-safe route definitions.

```typescript
// app/Router.tsx
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { lazy, Suspense } from 'react';

const DashboardPage = lazy(() => import('@features/dashboard/pages/DashboardPage'));
const SettingsPage = lazy(() => import('@features/settings/pages/SettingsPage'));

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    errorElement: <RootErrorBoundary />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      {
        path: 'dashboard',
        element: (
          <Suspense fallback={<PageSkeleton />}>
            <DashboardPage />
          </Suspense>
        ),
      },
      {
        path: 'settings',
        element: (
          <Suspense fallback={<PageSkeleton />}>
            <ProtectedRoute>
              <SettingsPage />
            </ProtectedRoute>
          </Suspense>
        ),
      },
    ],
  },
]);

export function Router() {
  return <RouterProvider router={router} />;
}
```

---

## Form Handling

Use React Hook Form for any form with more than 2 fields. For simple 1-2 field
interactions, controlled `useState` is fine.

```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  rememberMe: z.boolean().default(false),
});

type LoginFormData = z.infer<typeof loginSchema>;

function LoginForm({ onSubmit }: { readonly onSubmit: (data: LoginFormData) => void }) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '', rememberMe: false },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <TextField
        label="Email"
        type="email"
        error={errors.email?.message}
        {...register('email')}
      />
      <TextField
        label="Password"
        type="password"
        error={errors.password?.message}
        {...register('password')}
      />
      <Checkbox label="Remember me" {...register('rememberMe')} />
      <Button type="submit" isLoading={isSubmitting}>
        Sign in
      </Button>
    </form>
  );
}
```

Zod + React Hook Form is the standard pairing. Schema validation at the form boundary
means the rest of the application can trust the shape of validated data.

---

## Testing Strategy

### Test Pyramid for React

1. **Type checking (tsc)** — The first line of defense. Catches shape mismatches, missing props, impossible states.
2. **Unit tests** — Pure functions, utilities, reducers, custom hooks. Fast and focused.
3. **Component tests** — Render a component, interact with it, assert on the DOM. Use Testing Library.
4. **Integration tests** — Test a feature flow end-to-end within the browser. Use Playwright or Cypress.

### Testing Library Principles

```typescript
// ✗ Testing implementation details
expect(wrapper.find('Button').prop('disabled')).toBe(true);

// ✓ Testing user-observable behavior
expect(screen.getByRole('button', { name: /submit/i })).toBeDisabled();
```

Test what the user sees, not what the code does internally. If a refactor changes the
internal structure but the user experience is identical, tests should still pass.

---

## Error Boundaries & Recovery

```typescript
import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  readonly children: ReactNode;
  readonly fallback: (error: Error, reset: () => void) => ReactNode;
  readonly onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  readonly error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.props.onError?.(error, errorInfo);
  }

  private readonly reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return this.props.fallback(this.state.error, this.reset);
    }
    return this.props.children;
  }
}
```

Place error boundaries at route level, around data-fetching components, and around
any third-party widget that might throw.

---

## Environment & Configuration

```typescript
// shared/constants/config.ts
import { z } from 'zod';

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url(),
  VITE_APP_ENV: z.enum(['development', 'staging', 'production']),
  VITE_SENTRY_DSN: z.string().optional(),
});

function parseEnv() {
  const result = envSchema.safeParse(import.meta.env);
  if (!result.success) {
    throw new Error(
      `Invalid environment variables:\n${result.error.issues
        .map((i) => `  ${i.path.join('.')}: ${i.message}`)
        .join('\n')}`
    );
  }
  return result.data;
}

export const config = parseEnv();
```

Validate environment variables at startup. A clear error message at boot is infinitely
better than a cryptic runtime failure when some API call tries to use an undefined URL.

---

## Code Patterns Catalog

### Discriminated Union for Component States

```typescript
type TableState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'empty'; message: string }
  | { status: 'error'; error: ApiError; retry: () => void }
  | { status: 'success'; data: readonly T[]; totalCount: number };

function DataTable<T extends { id: string }>({ state }: { state: TableState<T> }) {
  switch (state.status) {
    case 'idle':
      return null;
    case 'loading':
      return <TableSkeleton />;
    case 'empty':
      return <EmptyState message={state.message} />;
    case 'error':
      return <ErrorState error={state.error} onRetry={state.retry} />;
    case 'success':
      return <Table data={state.data} totalCount={state.totalCount} />;
  }
}
```

### Branded Types

```typescript
declare const brand: unique symbol;
type Brand<T, B extends string> = T & { readonly [brand]: B };

type UserId = Brand<string, 'UserId'>;
type OrderId = Brand<string, 'OrderId'>;
type Timestamp = Brand<number, 'Timestamp'>;

// Factory functions
const UserId = (id: string) => id as UserId;
const OrderId = (id: string) => id as OrderId;

// Now these are type errors:
// findUser(orderId) — can't pass OrderId where UserId is expected
```

### Exhaustive Switch

```typescript
function assertNever(value: never): never {
  throw new Error(`Unhandled discriminated union member: ${JSON.stringify(value)}`);
}

function getStatusColor(status: OrderStatus): string {
  switch (status) {
    case 'pending': return tokens.colors.warning;
    case 'processing': return tokens.colors.info;
    case 'shipped': return tokens.colors.primary;
    case 'delivered': return tokens.colors.success;
    case 'cancelled': return tokens.colors.error;
    default: return assertNever(status);
    // If a new status is added to the union, TypeScript will error here
  }
}
```

### Compound Component Pattern

```typescript
interface TabsContextValue {
  readonly activeTab: string;
  readonly setActiveTab: (id: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabs() {
  const context = useContext(TabsContext);
  if (!context) throw new Error('Tab components must be used within <Tabs>');
  return context;
}

function Tabs({ defaultTab, children }: { defaultTab: string; children: ReactNode }) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  const value = useMemo(() => ({ activeTab, setActiveTab }), [activeTab]);
  return <TabsContext.Provider value={value}>{children}</TabsContext.Provider>;
}

function TabList({ children }: { children: ReactNode }) {
  return <div role="tablist">{children}</div>;
}

function Tab({ id, children }: { id: string; children: ReactNode }) {
  const { activeTab, setActiveTab } = useTabs();
  return (
    <button
      role="tab"
      aria-selected={activeTab === id}
      onClick={() => setActiveTab(id)}
    >
      {children}
    </button>
  );
}

function TabPanel({ id, children }: { id: string; children: ReactNode }) {
  const { activeTab } = useTabs();
  if (activeTab !== id) return null;
  return <div role="tabpanel">{children}</div>;
}

Tabs.List = TabList;
Tabs.Tab = Tab;
Tabs.Panel = TabPanel;

// Usage:
// <Tabs defaultTab="general">
//   <Tabs.List>
//     <Tabs.Tab id="general">General</Tabs.Tab>
//     <Tabs.Tab id="security">Security</Tabs.Tab>
//   </Tabs.List>
//   <Tabs.Panel id="general">...</Tabs.Panel>
//   <Tabs.Panel id="security">...</Tabs.Panel>
// </Tabs>
```
