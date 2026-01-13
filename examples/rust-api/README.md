# Rust API Example

This example shows a darkzloop spec and plan for adding event analytics to a Rust web API.

## What This Demonstrates

- **Keywords section** with database tables and pattern references
- **Existing system links** with specific file paths and line ranges
- **Strong linkage** in the plan referencing exact locations
- **Phased implementation** (foundation → API → security → polish)
- **Clear acceptance criteria** for each task

## Key Patterns

### Spec: Linking to Existing Code

```markdown
**API Layer:**
- Route definitions: `src/api/routes.rs` (lines 15-80)
- Request handlers: `src/api/handlers/mod.rs`
```

### Plan: Strong Linkage

```markdown
- [ ] **Task 2.2**: Add POST /api/events route
  - Modify: `src/api/routes.rs` (lines 45-50, add route)
  - Pattern: `src/api/routes.rs` (lines 30-35, POST route pattern)
```

## Running This Example

1. Copy these files to a Rust project with the referenced structure
2. Adjust file paths and line numbers to match your actual codebase
3. Run `darkzloop validate` to check the spec/plan quality
4. Run `darkzloop run --attended` to start the loop
