# Creating Implementation Plans

The plan translates specs into actionable tasks with **strong linkage**—references to exact files, line ranges, and spec sections.

## Why Linkage Matters

Agents read files in "hunks" (sections). Plans that point to the right hunks:
- Reduce search thrash
- Prevent invention of new patterns
- Keep changes localized
- Enable accurate checkpointing

## Plan Structure

```markdown
# Implementation Plan

**Spec**: DARKZLOOP_SPEC.md
**Status**: In Progress

## Tasks

- [ ] **Task 1**: [Brief description]
  - Modify: `path/to/file.ext` (lines X-Y, description)
  - Reference: DARKZLOOP_SPEC.md section N
  - Pattern: `path/to/similar.ext` (lines A-B)
  - Tests: `tests/path/test.ext`
  - Acceptance: [Verification method]

## Completion Log

| Task | Status | Completed | Commit |
|------|--------|-----------|--------|
| 1    | ⏸️     |           |        |
```

## Linkage Patterns

### Modifying Existing Code

**Bad (no linkage):**
```markdown
- [ ] Add authentication to the API
```

**Good (strong linkage):**
```markdown
- [ ] Add JWT validation middleware to protected routes
  - Modify: `src/api/routes.rs` (lines 45-60, route definitions)
  - Modify: `src/middleware/mod.rs` (lines 1-10, add export)
  - New file: `src/middleware/jwt_auth.rs`
  - Reference: DARKZLOOP_SPEC.md section 2.1
  - Pattern: `src/middleware/rate_limit.rs` (lines 20-50)
  - Tests: Add to `tests/api/auth_integration.rs`
  - Acceptance: `curl -H "Auth: Bearer invalid" /api` → 401
```

### Creating New Features

```markdown
- [ ] Implement event ingestion endpoint
  - New file: `src/api/events.rs`
  - Modify: `src/api/mod.rs` (line 15, add module)
  - Modify: `src/api/routes.rs` (lines 30-35, add route)
  - Reference: DARKZLOOP_SPEC.md section 3.1
  - Pattern: `src/api/users.rs` (CRUD endpoint pattern)
  - Tests: Create `tests/api/events_test.rs`
  - Acceptance: POST /api/events with valid payload → 201
```

### Database Changes

```markdown
- [ ] Add events table migration
  - New file: `migrations/005_events.sql`
  - Reference: DARKZLOOP_SPEC.md section 3.2
  - Pattern: `migrations/003_sessions.sql`
  - Acceptance: `sqlx migrate run` succeeds
```

## Task Granularity

| Granularity | Example | Problem |
|-------------|---------|---------|
| Too coarse | "Build entire auth system" | Will cause drift over many iterations |
| Too fine | "Add line 1 of jwt.rs" | Overhead without benefit |
| Just right | "Create JWT validation function" | One logical change, independently testable |

Each task should be:
- Completable in one iteration
- Independently testable
- Small enough to review
- Large enough to be meaningful

## Ordering Tasks

Order by dependency, then by risk:

1. **Foundation**: Data models, migrations, types
2. **Core logic**: Business logic, algorithms
3. **Integration**: API endpoints, UI
4. **Polish**: Error messages, edge cases, docs

Within each layer, do highest-risk items first. Fail early.

## Checkpointing

Each task should have clear completion state:

```markdown
- [x] Task 1: Setup structure (completed 2024-01-15 14:30)
      Commit: abc1234
- [x] Task 2: Add user model (completed 2024-01-15 15:45)
      Commit: def5678
- [ ] Task 3: Implement auth (in progress)
      Started: 2024-01-15 16:00
      Checkpoint: Added middleware scaffold
- [ ] Task 4: Add routes (blocked on Task 3)
```

This enables:
- Safe resume after interruption
- Progress tracking
- Audit trail

## Plan Evolution

Update the plan when:
- Tasks complete (mark `[x]` + timestamp)
- New tasks discovered mid-implementation
- Dependencies change
- File locations shift

The agent should update `DARKZLOOP_PLAN.md` as part of each iteration.

## Anti-Patterns

| Anti-Pattern | Problem |
|--------------|---------|
| Missing file refs | "Update the user model" — which file? |
| No line ranges | "Modify src/api.rs" — where in 500 lines? |
| No pattern ref | "Create endpoint" — follow what pattern? |
| Vague acceptance | "Should work" — how to verify? |
| Tasks too large | "Implement feature" — takes 10 iterations |

## Example Plan

```markdown
# Implementation Plan: Event Analytics

**Spec**: DARKZLOOP_SPEC.md
**Status**: In Progress

## Phase 1: Foundation

- [x] **Task 1.1**: Create events table migration
  - New file: `migrations/005_events.sql`
  - Reference: DARKZLOOP_SPEC.md section 3.2
  - Pattern: `migrations/003_sessions.sql`
  - Acceptance: `sqlx migrate run` succeeds
  - Completed: 2024-01-15 14:30, commit abc1234

- [ ] **Task 1.2**: Create Event model
  - New file: `src/models/event.rs`
  - Modify: `src/models/mod.rs` (line 5, add export)
  - Reference: DARKZLOOP_SPEC.md section 3.2
  - Pattern: `src/models/user.rs` (struct + impl pattern)
  - Tests: Create `tests/models/event_test.rs`
  - Acceptance: `cargo test event` passes

## Phase 2: API

- [ ] **Task 2.1**: Create events API handler
  - New file: `src/api/handlers/events.rs`
  - Modify: `src/api/handlers/mod.rs` (add export)
  - Reference: DARKZLOOP_SPEC.md section 3.1
  - Pattern: `src/api/handlers/users.rs` (lines 20-80)
  - Tests: Add to `tests/api/events_test.rs`
  - Acceptance: Handler compiles, unit tests pass

- [ ] **Task 2.2**: Add events route
  - Modify: `src/api/routes.rs` (lines 45-50, add route)
  - Reference: DARKZLOOP_SPEC.md section 3.1
  - Pattern: `src/api/routes.rs` (lines 30-35, users route)
  - Acceptance: POST /api/events returns 201

## Completion Log

| Task | Status | Completed | Commit |
|------|--------|-----------|--------|
| 1.1  | ✅     | 2024-01-15 14:30 | abc1234 |
| 1.2  | ⏳     |           |        |
| 2.1  | ⏸️     |           |        |
| 2.2  | ⏸️     |           |        |
```
