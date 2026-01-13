# TypeScript App Example

Example spec and plan for adding a dashboard component to a React application.

## DARKZLOOP_SPEC.md

```markdown
# Analytics Dashboard Spec

## Objective

Add a dashboard page showing key metrics from our analytics API.
Display event counts, user trends, and conversion funnels.

## Keywords & Synonyms

- dashboard, metrics, charts, visualization
- analytics, events, conversions, funnel
- recharts, chart.js (library patterns)
- useQuery, useSWR (data fetching patterns)

## Existing System Links

**Components:**
- Page layout: `src/components/Layout.tsx` (lines 1-50)
- Card component: `src/components/ui/Card.tsx`
- Loading states: `src/components/ui/Skeleton.tsx`

**Data fetching:**
- API client: `src/lib/api.ts`
- Query hooks: `src/hooks/useQuery.ts`

**Routes:**
- Route config: `src/App.tsx` (lines 20-60)

**Patterns:**
- Page component: `src/pages/Settings.tsx`
- Chart usage: `src/components/charts/LineChart.tsx`

## Requirements

1. `/dashboard` route accessible from main nav
2. Display cards: Total Events, Active Users, Conversion Rate
3. Line chart showing events over time (7 days default)
4. Loading skeletons while data fetches
5. Error states with retry button

## Constraints

**Must follow:**
- Use existing Card and Skeleton components
- Use useQuery hook for data fetching
- Follow Settings.tsx page structure
- Use Tailwind for styling (no custom CSS)

**Must avoid:**
- No new charting libraries (use existing recharts)
- No inline styles
- No direct API calls (use api.ts client)

## Non-Goals

- Real-time updates (polling only)
- Export functionality
- Date range picker (hardcoded 7 days)
- Mobile-specific layout

## Success Criteria

- [ ] /dashboard renders without errors
- [ ] Cards show correct metrics from API
- [ ] Chart displays event data
- [ ] Loading states display correctly
- [ ] Error states work with retry
- [ ] `npm test` passes
- [ ] `npm run lint` clean
```

## DARKZLOOP_PLAN.md

```markdown
# Implementation Plan: Analytics Dashboard

**Spec**: DARKZLOOP_SPEC.md
**Status**: Not Started

## Phase 1: Page Structure

- [ ] **Task 1.1**: Create Dashboard page component
  - New file: `src/pages/Dashboard.tsx`
  - Pattern: `src/pages/Settings.tsx` (page structure)
  - Acceptance: Component renders placeholder

- [ ] **Task 1.2**: Add dashboard route
  - Modify: `src/App.tsx` (lines 45-50, add route)
  - Modify: `src/components/Nav.tsx` (add nav link)
  - Pattern: `src/App.tsx` (lines 30-35, settings route)
  - Acceptance: /dashboard accessible from nav

## Phase 2: Data Layer

- [ ] **Task 2.1**: Add analytics API functions
  - Modify: `src/lib/api.ts` (add analytics endpoints)
  - Pattern: `src/lib/api.ts` (lines 20-40, existing endpoints)
  - Tests: `src/lib/__tests__/api.test.ts`
  - Acceptance: API functions return typed data

- [ ] **Task 2.2**: Create useAnalytics hook
  - New file: `src/hooks/useAnalytics.ts`
  - Pattern: `src/hooks/useQuery.ts`
  - Acceptance: Hook fetches and returns analytics data

## Phase 3: UI Components

- [ ] **Task 3.1**: Create MetricCard component
  - New file: `src/components/dashboard/MetricCard.tsx`
  - Pattern: `src/components/ui/Card.tsx`
  - Tests: `src/components/dashboard/__tests__/MetricCard.test.tsx`
  - Acceptance: Displays label, value, loading state

- [ ] **Task 3.2**: Add EventsChart component
  - New file: `src/components/dashboard/EventsChart.tsx`
  - Pattern: `src/components/charts/LineChart.tsx`
  - Acceptance: Renders line chart with event data

## Phase 4: Integration

- [ ] **Task 4.1**: Wire up Dashboard page
  - Modify: `src/pages/Dashboard.tsx` (integrate components)
  - Acceptance: Full dashboard renders with real data

- [ ] **Task 4.2**: Add error handling
  - Modify: `src/pages/Dashboard.tsx` (error states)
  - Pattern: `src/pages/Settings.tsx` (error handling)
  - Acceptance: Error state shows retry button
```

## Key Patterns

Note how the plan references exact line numbers and pattern files for consistency.
