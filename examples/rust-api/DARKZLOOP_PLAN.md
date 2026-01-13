# Implementation Plan: Event Analytics API

**Spec**: DARKZLOOP_SPEC.md  
**Created**: 2024-01-15  
**Status**: Not Started

---

## Phase 1: Database Foundation

- [ ] **Task 1.1**: Create events table migration
  - New file: `migrations/005_events.sql`
  - Reference: DARKZLOOP_SPEC.md Requirements #2
  - Pattern: `migrations/003_sessions.sql`
  - Acceptance: `sqlx migrate run` succeeds, table exists with correct schema

- [ ] **Task 1.2**: Create Event model struct
  - New file: `src/models/event.rs`
  - Modify: `src/models/mod.rs` (line 5, add `pub mod event;`)
  - Reference: DARKZLOOP_SPEC.md Requirements #2
  - Pattern: `src/models/user.rs` (lines 1-50, struct definition)
  - Tests: Create `tests/models/event_test.rs`
  - Acceptance: `cargo test event` passes

- [ ] **Task 1.3**: Add Event database queries
  - Modify: `src/models/event.rs` (add impl block)
  - Reference: DARKZLOOP_SPEC.md Requirements #1, #2
  - Pattern: `src/models/user.rs` (lines 52-120, impl block with CRUD)
  - Tests: Add to `tests/models/event_test.rs`
  - Acceptance: Can insert and query events in tests

## Phase 2: API Endpoints

- [ ] **Task 2.1**: Create events API handler
  - New file: `src/api/handlers/events.rs`
  - Modify: `src/api/handlers/mod.rs` (add `pub mod events;`)
  - Reference: DARKZLOOP_SPEC.md Requirements #1
  - Pattern: `src/api/handlers/users.rs` (lines 20-80)
  - Acceptance: Handler compiles, returns proper types

- [ ] **Task 2.2**: Add POST /api/events route
  - Modify: `src/api/routes.rs` (lines 45-50, add route)
  - Reference: DARKZLOOP_SPEC.md Requirements #1
  - Pattern: `src/api/routes.rs` (lines 30-35, POST route pattern)
  - Tests: Create `tests/api/events_test.rs`
  - Acceptance: POST /api/events with valid payload returns 201

- [ ] **Task 2.3**: Add input validation for events
  - Modify: `src/api/handlers/events.rs` (validation in handler)
  - Reference: DARKZLOOP_SPEC.md Requirements #1, Constraints
  - Pattern: `src/api/handlers/users.rs` (lines 25-40, validation)
  - Tests: Add validation tests to `tests/api/events_test.rs`
  - Acceptance: Returns 400 for missing required fields

- [ ] **Task 2.4**: Create identify endpoint
  - Modify: `src/api/handlers/events.rs` (add identify handler)
  - Modify: `src/api/routes.rs` (add POST /api/identify route)
  - Reference: DARKZLOOP_SPEC.md Requirements #3
  - Tests: Add to `tests/api/events_test.rs`
  - Acceptance: POST /api/identify links device_id to user_id

## Phase 3: Security & Rate Limiting

- [ ] **Task 3.1**: Add IP address encryption
  - Modify: `src/api/handlers/events.rs` (wrap IP in Secret<T>)
  - Reference: DARKZLOOP_SPEC.md Constraints (Security)
  - Pattern: `src/types/secret.rs` (Secret wrapper usage)
  - Tests: Verify IP not stored in plaintext
  - Acceptance: IP addresses encrypted in database

- [ ] **Task 3.2**: Add rate limiting middleware
  - Modify: `src/api/routes.rs` (apply rate limit to events routes)
  - Reference: DARKZLOOP_SPEC.md Requirements #4
  - Pattern: `src/middleware/rate_limit.rs` (existing middleware)
  - Tests: Add rate limit test to `tests/api/events_test.rs`
  - Acceptance: Returns 429 after 100 requests/minute

## Phase 4: Polish

- [ ] **Task 4.1**: Add comprehensive error handling
  - Modify: `src/api/handlers/events.rs` (error cases)
  - Reference: DARKZLOOP_SPEC.md Constraints
  - Pattern: `src/api/error.rs` (ApiError enum)
  - Acceptance: All error paths return appropriate status codes

- [ ] **Task 4.2**: Add API documentation
  - Modify: `src/api/handlers/events.rs` (add doc comments)
  - Reference: DARKZLOOP_SPEC.md Requirements
  - Pattern: `src/api/handlers/users.rs` (doc comment style)
  - Acceptance: `cargo doc` generates docs for events module

---

## Completion Log

| Task | Status | Completed | Commit | Notes |
|------|--------|-----------|--------|-------|
| 1.1  | ⏸️     |           |        |       |
| 1.2  | ⏸️     |           |        |       |
| 1.3  | ⏸️     |           |        |       |
| 2.1  | ⏸️     |           |        |       |
| 2.2  | ⏸️     |           |        |       |
| 2.3  | ⏸️     |           |        |       |
| 2.4  | ⏸️     |           |        |       |
| 3.1  | ⏸️     |           |        |       |
| 3.2  | ⏸️     |           |        |       |
| 4.1  | ⏸️     |           |        |       |
| 4.2  | ⏸️     |           |        |       |

**Legend**: ✅ Complete | ⏳ In Progress | ⏸️ Not Started | ❌ Blocked

---

## Discovered Work

[Tasks discovered during implementation]

## Blocked Items

[Tasks blocked and why]
