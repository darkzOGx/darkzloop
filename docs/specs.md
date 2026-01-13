# Writing Effective Specs

The spec is your **pin**—the anchor that prevents agent invention. The more specific your spec, the less the agent hallucinates.

## Spec Structure

```markdown
# [Feature Name] Spec

## Objective
[One paragraph: what and why]

## Keywords & Synonyms
[Search terms for code discovery]

## Existing System Links
[Pointers to code the work touches]

## Requirements
[What must be true when done]

## Constraints
[Patterns to follow, things to avoid]

## Non-Goals
[Explicitly out of scope]

## Success Criteria
[How to verify completion]
```

## Keywords & Synonyms

This is the most underrated section. Good keywords help the agent's search tools find relevant code.

**Bad:**
```markdown
## Keywords
- analytics
```

**Good:**
```markdown
## Keywords & Synonyms
Search terms for discovery:
- analytics, tracking, events, telemetry
- pageview, click, conversion, funnel
- PostHog, Mixpanel (pattern references)
- user_events table, events API endpoint
```

Include:
- Technical synonyms (`auth`/`authentication`/`login`)
- Related concepts the agent might search for
- Names of similar systems to use as patterns
- Database tables or API endpoints involved

## Existing System Links

Point to exact locations. Agents read in "hunks" (file sections).

**Bad:**
```markdown
See the authentication module.
```

**Good:**
```markdown
## Existing System Links

Authentication system:
- Entry point: `src/auth/mod.rs` (lines 1-30, public API)
- JWT handling: `src/auth/jwt.rs` (entire file, ~200 lines)
- Middleware: `src/middleware/auth.rs` (lines 45-90, verify_token fn)

Database:
- Users table: `migrations/001_users.sql`
- Sessions table: `migrations/003_sessions.sql`

Patterns to follow:
- Error handling: `src/api/users.rs` (lines 60-80)
- Tests: `tests/api/auth_test.rs`
```

## Constraints

Be explicit about patterns and anti-patterns.

```markdown
## Constraints

**Must follow:**
- Use existing `ApiError` type for all errors
- Follow i18n patterns in `src/i18n/`
- Use `#[instrument]` tracing macro on public functions

**Must avoid:**
- Do not introduce new error types
- Do not add dependencies without approval
- Do not modify the User struct

**Security:**
- All PII must use `Secret<T>` wrapper
- No sensitive data in logs
```

## Non-Goals

Prevents scope creep and invention.

```markdown
## Non-Goals

Explicitly out of scope:
- Real-time analytics (batch only for now)
- Custom dashboard UI (use existing admin)
- Data export (future iteration)
- GDPR compliance (separate project)
```

Without non-goals, agents tend to "helpfully" add features you didn't ask for.

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|--------------|---------|-----|
| Too vague | "Build analytics" | Define specific requirements |
| Too rigid | 100 lines of exact code | Describe intent, link patterns |
| Missing links | No file references | Add existing system links |
| No keywords | Agent can't find code | Add search terms |
| No non-goals | Agent invents features | Define scope boundaries |

## Spec Evolution

Specs are living documents. Update when:
- You discover missing constraints
- File locations change
- New patterns emerge
- Non-goals become goals (new iteration)

The spec stays the source of truth throughout the loop lifecycle.

## Example: Product Analytics

```markdown
# Product Analytics Spec

## Objective
Add event tracking to capture user behavior for product decisions.
Track anonymous and authenticated users with proper PII handling.

## Keywords & Synonyms
- analytics, tracking, events, telemetry, metrics
- pageview, click, action, conversion
- anonymous user, identified user, user_id
- PostHog, Mixpanel, Amplitude (patterns)
- events table, analytics API

## Existing System Links

API layer:
- Route definitions: `src/api/routes.rs` (lines 20-80)
- Request handling: `src/api/handlers/mod.rs`
- Auth middleware: `src/middleware/auth.rs`

Database:
- Schema: `migrations/` directory
- Connection: `src/db/mod.rs`

Patterns:
- API endpoint: `src/api/handlers/users.rs` (CRUD pattern)
- Migration: `migrations/003_sessions.sql`

## Requirements
1. POST /api/events endpoint accepts event payloads
2. Events stored with timestamp, user_id (nullable), properties
3. Anonymous users tracked via device fingerprint
4. SDK methods: track(event, properties), identify(user_id)
5. Rate limiting: 100 events/minute per client

## Constraints

**Must follow:**
- Use existing `ApiResponse` wrapper
- Follow migration naming: `NNN_description.sql`
- IP addresses wrapped in `Secret<IpAddr>`

**Must avoid:**
- No PII in event properties
- No blocking calls in event ingestion
- No new external dependencies

## Non-Goals
- Real-time dashboards (future)
- A/B testing integration (separate spec)
- Data export/warehouse sync (future)
- GDPR data deletion (separate spec)

## Success Criteria
- [ ] POST /api/events returns 201 for valid payload
- [ ] Events queryable in database
- [ ] Anonymous tracking works without auth
- [ ] identify() merges anonymous → authenticated
- [ ] Rate limit returns 429 when exceeded
```
