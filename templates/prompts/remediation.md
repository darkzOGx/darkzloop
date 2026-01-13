# Remediation Loop Prompt

You are executing a remediation loop to fix accumulated issues.

## Your Anchor Document

**DARKZLOOP_SPEC.md** - The remediation specification defining what to fix.

## Remediation Types

This loop is for cleanup work, not new features:
- **Refactor**: Restructure code to follow patterns
- **Security**: Apply security hardening
- **Coverage**: Add missing tests
- **Debt**: Fix accumulated technical debt

## Instructions

1. **Study the remediation spec**
   - Understand the scope (which files/modules)
   - Note what should NOT change (behavior, API)
   - Review the target pattern

2. **Find issues to fix**
   - Search the scoped files for the problem pattern
   - List all instances that need remediation

3. **Fix one issue at a time**
   - Make the minimal change needed
   - Follow the target pattern exactly
   - Do not change behavior
   - Verify tests still pass

4. **Track progress**
   - Note which files have been remediated
   - Flag any complex cases for manual review

## Rules

- **Scope strictly** - Only touch files in the defined scope
- **Preserve behavior** - Do not change what the code does
- **Pattern exactly** - Match the target pattern precisely
- **One at a time** - Fix one issue per iteration
- **Test constantly** - Run tests after every change

## If Something Goes Wrong

- Tests fail → Rollback, the "fix" changed behavior
- Pattern unclear → Stop and flag for clarification
- Complex case → Skip and flag for manual review
- Outside scope → Do not touch it

## Output

After each iteration, report:
1. What was fixed
2. Files modified
3. Tests status
4. Remaining issues count
5. Any flagged items for manual review
