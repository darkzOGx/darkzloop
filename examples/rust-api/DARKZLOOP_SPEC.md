# Event Analytics API Spec

## Objective

Add event tracking to capture user behavior. Track anonymous and authenticated users with proper PII handling. Events will be used for product analytics decisions.

## Keywords & Synonyms

Search terms for code discovery:
- analytics, tracking, events, telemetry, metrics
- pageview, click, action, conversion, funnel
- anonymous user, identified user, user_id, device_id
- PostHog, Mixpanel, Amplitude (pattern references)
- events table, analytics endpoint, track, identify

## Existing System Links

**API Layer:**
- Route definitions: `src/api/routes.rs` (lines 15-80)
- Request handlers: `src/api/handlers/mod.rs`
- Auth middleware: `src/middleware/auth.rs` (lines 30-60)
- Error handling: `src/api/error.rs`

**Database:**
- Migrations directory: `migrations/`
- Connection pool: `src/db/mod.rs`
- Query helpers: `src/db/queries.rs`

**Models:**
- User model: `src/models/user.rs` (struct + impl pattern)
- Model exports: `src/models/mod.rs`

**Patterns to follow:**
- API handler: `src/api/handlers/users.rs` (lines 20-80, CRUD pattern)
- Migration: `migrations/003_sessions.sql`
- Model tests: `tests/models/user_test.rs`

## Requirements

1. `POST /api/events` accepts event payloads with:
   - `event_name`: string (required)
   - `properties`: JSON object (optional)
   - `timestamp`: ISO 8601 (optional, defaults to server time)
   - `user_id`: string (optional, for identified users)
   - `device_id`: string (required, for anonymous tracking)

2. Events stored in `events` table with:
   - `id`: UUID primary key
   - `event_name`: VARCHAR(255)
   - `properties`: JSONB
   - `user_id`: UUID nullable (FK to users)
   - `device_id`: VARCHAR(255)
   - `ip_address`: encrypted
   - `created_at`: timestamp

3. `POST /api/identify` links device_id to user_id for user identification

4. Rate limiting: 100 events/minute per device_id

5. All endpoints return standard `ApiResponse` wrapper

## Constraints

**Must follow:**
- Use existing `ApiResponse<T>` wrapper from `src/api/response.rs`
- Follow migration naming: `NNN_description.sql`
- Use `Secret<T>` wrapper for IP addresses (see `src/types/secret.rs`)
- Use existing rate limiter middleware pattern
- Write integration tests in `tests/api/`

**Must avoid:**
- No PII in event properties (reject if detected)
- No blocking operations in event ingestion path
- No new external dependencies
- Do not modify existing User model

**Security:**
- IP addresses encrypted at rest
- Device IDs hashed before storage
- Rate limiting to prevent abuse

## Non-Goals

Explicitly out of scope:
- Real-time dashboards (batch queries only for now)
- A/B testing / feature flags integration (separate project)
- Data export to warehouse (future iteration)
- GDPR data deletion endpoint (separate compliance project)
- Client SDKs (API only for now)

## Success Criteria

- [ ] `POST /api/events` returns 201 for valid payload
- [ ] `POST /api/events` returns 400 for missing required fields
- [ ] `POST /api/events` returns 429 when rate limited
- [ ] `POST /api/identify` links device to user
- [ ] Events queryable in database with correct schema
- [ ] IP addresses stored encrypted
- [ ] All new code has test coverage
- [ ] `cargo test` passes
- [ ] `cargo clippy` clean
