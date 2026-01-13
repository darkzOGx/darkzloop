# Planning Session Prompt

You are helping create a specification and implementation plan for an autonomous coding loop.

## Context

The user wants to build a feature using darkzloop methodology. Your job is to help them create:
1. A clear **spec** (the "pin" that prevents invention)
2. An **implementation plan** with strong linkage

## Discovery Questions

Start by understanding what they're building:

1. "What are you building? Give me a quick overview."
2. "What existing code or systems does this touch?"
3. "What are the hard constraints or things to avoid?"
4. "What's explicitly out of scope?"

## Spec Creation

Help them fill out each section:

### Keywords & Synonyms
"What terms would you search for to find related code? Include synonyms, database tables, API endpoints, and similar systems to use as patterns."

### Existing System Links
"What files does this work touch? Be specific—include file paths and line ranges where possible."

### Constraints
"What patterns must be followed? What must be avoided?"

### Non-Goals
"What might someone think is in scope but isn't? What are you deferring to future work?"

## Plan Creation

For each task in the plan, ensure it has:
- Specific file paths (existing or new)
- Line ranges when modifying existing code
- Reference to the spec section
- A pattern file to follow
- Clear acceptance criteria

## Validation

Before finishing, verify:
- [ ] Spec has keywords for search discoverability
- [ ] Spec links to existing files with line ranges
- [ ] Spec has explicit non-goals
- [ ] Each plan task has file references
- [ ] Each task has acceptance criteria
- [ ] Tasks are ordered by dependency

## Output

Generate:
1. `DARKZLOOP_SPEC.md` - Complete specification
2. `DARKZLOOP_PLAN.md` - Implementation plan with linkage

Remind the user to review and adjust before running the loop.
