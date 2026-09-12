# Backend Data TODO

This document tracks every hardcoded mock value in the Analysis Player and the API shape needed to make it real.

All mock data lives in `src/mocks/fightMock.ts` and is consumed by the components in `src/components/player/`.

---

## 1. Fighter Profiles

**Hardcoded in:** `src/mocks/fightMock.ts` → `fighters.red` / `fighters.blue`

**Consumed by:** `FighterColumn.tsx`, `MatchupCard.tsx`, `Momentum.tsx`

**Missing from API:** The backend has no concept of fighter identity beyond `fighter_id` (0 = red, 1 = blue in the overlay). Needed fields per fighter:

```ts
interface FighterProfile {
  fighter_id: number;   // 0 | 1
  name: string;         // e.g. "BATUR"
  first: string;        // first name
  nickname: string;
  record: string;       // "14-3-0"
  country: string;      // ISO 3-letter
  corner: 'red' | 'blue';
  reach: string;        // e.g. '74"'
  height: string;       // e.g. "6'1\""
  age: number;
}
```

**Suggested endpoint:** `GET /fights/{id}/fighters` → `FighterProfile[]`

---

## 2. Per-Round Aggregated Stats Per Fighter

**Status:** Resolved client-side — `deriveStatsForRange()` in `src/utils/liveStats.ts` parses
`events` (frame-filtered to the whole fight, a round's `[start_frame, end_frame]`, or
`[0, currentFrame]` for "Live") and is consumed by `FightStatistics.tsx` for all three
`ScopeToggle` modes. No backend aggregation needed for this to work; an endpoint would
only be a performance optimization for very long event lists.

**Consumed by:** `FightStatistics.tsx` → `FighterColumn.tsx`

**Original gap (kept for reference):** The backend stores raw events but does not aggregate
per-round stats. Shape needed per fighter per scope:

```ts
interface FighterStats {
  sig:      [number, number]; // [landed, attempted]
  total:    [number, number];
  head:     number;           // sig strikes to head
  body:     number;
  leg:      number;
  distance: number;           // sig strikes at distance
  clinch:   number;
  ground:   number;
  td:       [number, number]; // [takedowns landed, attempted]
  ctrl:     number;           // control time in seconds
  kd:       number;           // knockdowns
  sub:      number;           // submission attempts
  acc:      number;           // accuracy %
}
```

**Suggested endpoint:** `GET /fights/{id}/stats?scope=fight|1|2` → `{ red: FighterStats, blue: FighterStats }`

---

## 3. Event Enrichment

**Current state:** Events are `{ id, frame, description, fight_id }` — plain text only.

**Consumed by:** `LiveFeed.tsx` (derives `cat` via regex from `description`; `fighter` and `sub` are always blank)

**Missing from API:** Structured fields on each event:

```ts
interface EnrichedEvent {
  id: number;
  frame: number;
  description: string;
  fight_id: number;
  category:   'strike' | 'grapple' | 'state' | 'round' | 'event';
  fighter_id: number | null;   // 0=red, 1=blue, null=fight-level
  sub: string;                 // e.g. "Landed", "Blocked", "KNOCKDOWN"
}
```

**Interim:** `LiveFeed.tsx` uses `deriveEventCat()` in `eventMeta.ts` (regex-based). Replace when the API provides `category`.

---

## 4. Pace Timeline

**Status:** Resolved client-side — `derivePaceBuckets()` in `src/utils/liveStats.ts` buckets
landed significant strikes from `events` into `bucketSeconds`-wide windows per fighter.
`Momentum.tsx` calls it with the real `events`/`fps` instead of a hardcoded array. No backend
aggregation needed for this to work; an endpoint would only be a performance optimization for
very long fights.

**Consumed by:** `Momentum.tsx` → `PaceChart.tsx`

**Original gap (kept for reference):** No time-series aggregation exists in the backend. Shape
that an endpoint could return instead:

```ts
interface PaceTimeline {
  bucket_seconds: number;    // e.g. 30
  red:  number[];            // sig strikes landed per bucket
  blue: number[];
}
```

**Suggested endpoint:** `GET /fights/{id}/pace?bucket=30` → `PaceTimeline`

---

## 5. Recent Form

**Hardcoded in:** `src/mocks/fightMock.ts` → `fighters.red.form` / `fighters.blue.form`

**Consumed by:** `MatchupCard.tsx` → `RecentForm.tsx`

**Missing from API:** No fight history data exists. Needed per fighter:

```ts
interface FormResult {
  result:   'W' | 'L' | 'NC';
  method:   string;   // "KO", "TKO", "DEC", "SUB"
  opponent: string;   // opponent name
}
```

**Suggested endpoint:** `GET /fighters/{fighter_id}/form?limit=5` → `FormResult[]`

Alternatively, attach form arrays to the `/fights/{id}/fighters` response.

---

## 6. Round 1 End (for PaceChart Divider)

**Current state:** `Player.tsx` derives `r1EndSeconds` from `useRounds()` when available, falling back to the mock constant `R1_END = 313`.

**Status:** Partially real — the rounds hook already provides `end_frame` which is converted to seconds. No additional work needed here once rounds are present in the DB for the loaded fight.
