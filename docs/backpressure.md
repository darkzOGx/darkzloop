# Back-pressure & Quality Gates

Back-pressure keeps generative loops on the rails. Add gates incrementally based on observed failure modes.

## Gate Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Loop Iteration                     │
├─────────────────────────────────────────────────────┤
│  1. Agent makes changes                             │
│  2. Gate: Tests pass?          ─── No ──→ Rollback  │
│  3. Gate: Format check?        ─── No ──→ Auto-fix  │
│  4. Gate: Lint clean?          ─── No ──→ Rollback  │
│  5. All pass → Commit + Checkpoint                  │
│  6. Next iteration                                  │
└─────────────────────────────────────────────────────┘
```

## Gate Tiers

### Tier 1: Essential (Always Include)

Tests must pass. Non-negotiable.

```bash
$TEST_COMMAND || exit 1
```

### Tier 2: Code Quality (Recommended)

Format and lint catch style drift.

```bash
# Format check (auto-fixable)
$FORMAT_CHECK || {
    $FORMAT_FIX
    $TEST_COMMAND || exit 1  # Re-test after fix
}

# Lint check
$LINT_COMMAND || exit 1
```

### Tier 3: Safety (Add When Needed)

Type checking, security scanning, dependency audits.

```bash
$TYPE_CHECK || exit 1
$SECURITY_SCAN || exit 1
$AUDIT || exit 1
```

## Language Configurations

### Rust
```json
{
  "test": "cargo test",
  "format_check": "cargo fmt --check",
  "format_fix": "cargo fmt",
  "lint": "cargo clippy -- -D warnings"
}
```

### TypeScript
```json
{
  "test": "npm test",
  "format_check": "npx prettier --check .",
  "format_fix": "npx prettier --write .",
  "lint": "npx eslint .",
  "type_check": "npx tsc --noEmit"
}
```

### Python
```json
{
  "test": "pytest",
  "format_check": "black --check .",
  "format_fix": "black .",
  "lint": "ruff check .",
  "type_check": "mypy ."
}
```

### Go
```json
{
  "test": "go test ./...",
  "format_check": "test -z $(gofmt -l .)",
  "format_fix": "gofmt -w .",
  "lint": "golangci-lint run"
}
```

## Failure Response Patterns

### Test Failure
1. Stop iteration
2. Show failure output
3. **Attended**: Human reviews, adjusts spec
4. **Unattended**: Rollback, log failure, increment failure counter

### Format/Lint Failure
1. Attempt auto-fix
2. Re-run tests (format changes can break things)
3. If tests pass, continue
4. If tests fail, treat as test failure

### Repeated Failures
If the same task fails 3+ times:
1. Stop the loop
2. Mark task as blocked
3. Flag for human review
4. Consider: Is the spec clear enough?

## Rollback Patterns

### Simple Rollback
```bash
git checkout -- .
git clean -fd
```

### Checkpoint Rollback
```bash
git reset --hard $LAST_GOOD_COMMIT
```

### Stash for Investigation
```bash
git stash push -m "Failed iteration $(date +%s)"
git checkout -- .
```

## Incremental Gate Addition

Start minimal, add gates when you observe failure modes:

**Week 1**: Tests only
```bash
cargo test || exit 1
```

**Week 2**: Formatting issues → add format gate
```bash
cargo test || exit 1
cargo fmt --check || { cargo fmt && cargo test || exit 1; }
```

**Week 3**: Lint warnings accumulating → add lint gate
```bash
cargo test || exit 1
cargo fmt --check || { cargo fmt && cargo test || exit 1; }
cargo clippy -- -D warnings || exit 1
```

**Week 4**: Security issue shipped → add audit
```bash
# ... previous gates ...
cargo audit || exit 1
```

Let observed failures drive gate additions.

## Remediation Loops

When issues accumulate, don't hand-fix. Run a targeted cleanup loop.

### Refactor Loop
```markdown
# Remediation: Refactor [Module]

## Objective
Refactor to follow [pattern]

## Scope
- Only files in `src/[module]/`
- Do not change public API
- Do not change behavior

## Pattern
See `src/[good_example]/`
```

### Security Loop
```markdown
# Remediation: Security Hardening

## Objective
Apply security patterns

## Tasks
- Replace raw SQL with parameterized queries
- Add input validation to API endpoints
- Ensure PII uses Secret<T> wrapper
```

### Test Coverage Loop
```markdown
# Remediation: Test Coverage

## Objective
Increase coverage for [module]

## Tasks
- Add unit tests for uncovered functions
- Add integration tests for endpoints
- Target: 80% line coverage
```

## Observability

### What to Log
```
[2024-01-15T14:30:00Z] Starting iteration 5 for task 2.1
[2024-01-15T14:30:45Z] Agent completed
[2024-01-15T14:30:46Z] Tests: PASS (12 tests, 0.8s)
[2024-01-15T14:30:47Z] Format: PASS
[2024-01-15T14:30:48Z] Lint: PASS
[2024-01-15T14:30:49Z] Committed: abc1234
[2024-01-15T14:30:50Z] Task 2.1 complete
```

### Metrics to Track
- Iterations per task
- Test pass rate
- Time per iteration
- Rollback frequency
- Tasks completed per hour

### Alert Conditions
- 3+ consecutive failures
- Iteration > 10 minutes
- Unusual file changes (many deletions, huge additions)

## Philosophy

Back-pressure is about **catching drift early**. Every gate you add is a checkpoint that says "this far, but no further" if quality degrades.

The goal isn't to prevent all failures—it's to fail fast and visibly, so you can adjust the spec or plan before drift compounds.
