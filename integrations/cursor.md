# Using darkzloop with Cursor

[Cursor](https://cursor.sh) is an AI-powered code editor with built-in agent capabilities. Here's how to use darkzloop methodology with Cursor.

## Setup

1. Initialize darkzloop in your project:
   ```bash
   cd your-project
   darkzloop init
   ```

2. Open the project in Cursor

3. Create your spec and plan (you can use Cursor's AI to help):
   - Open `DARKZLOOP_SPEC.md`
   - Use Cmd+K or Cursor's chat to fill it out

## Running Iterations

### Using Cursor Chat

1. Open Cursor's chat panel (Cmd+L)

2. Paste the iteration prompt:
   ```
   @DARKZLOOP_SPEC.md @DARKZLOOP_PLAN.md

   Execute one iteration of the darkzloop. Read the spec as your anchor,
   find the first uncompleted task in the plan, and complete only that task.
   Follow the patterns referenced in the task. Update the plan when done.
   ```

3. Review Cursor's proposed changes before accepting

### Using Composer

Cursor's Composer mode is well-suited for darkzloop iterations:

1. Open Composer (Cmd+I)

2. Include context:
   ```
   Using @DARKZLOOP_SPEC.md as the specification and @DARKZLOOP_PLAN.md
   as the implementation plan, complete the next uncompleted task.
   ```

3. Composer will show you all proposed changes across files—review before applying

## Attended Workflow

For each iteration:

1. **Run the agent**
   - Use Chat or Composer with the iteration prompt
   - Review proposed changes

2. **Accept or reject**
   - Accept changes that match the spec
   - Reject or modify changes that drift

3. **Run gates**
   ```bash
   cargo test
   cargo fmt --check
   cargo clippy
   ```

4. **Commit**
   ```bash
   git add -A && git commit -m "Task X.X: description"
   ```

5. **Update plan**
   - Mark task complete in `DARKZLOOP_PLAN.md`
   - Note any discovered work

## Tips for Cursor

### Use @ References

Always reference your spec and plan files:
```
@DARKZLOOP_SPEC.md @DARKZLOOP_PLAN.md
```

This ensures Cursor reads them as context.

### Pin Important Files

Pin `DARKZLOOP_SPEC.md` and `DARKZLOOP_PLAN.md` in Cursor so they're always visible and easy to reference.

### Use Checkpoints

After each successful iteration, make a git commit. This gives you clean rollback points.

### Review Diffs Carefully

Cursor shows diffs before applying—use this to catch drift early. Look for:
- Changes to files not in the task
- New patterns instead of following existing ones
- Features not in the spec

## Caveats

Cursor is interactive by design, so it's best suited for **attended** darkzloop operation. For unattended loops, consider Claude Code or Aider.

However, attended operation in Cursor has advantages:
- Easy diff review before accepting
- Quick iteration on spec/plan
- Good for the "screwdriver" phase of learning

## Example Workflow

```
# In Cursor Chat:

Me: @DARKZLOOP_SPEC.md @DARKZLOOP_PLAN.md 
    What is the next uncompleted task?

Cursor: Looking at DARKZLOOP_PLAN.md, the next uncompleted task is:
        Task 1.2: Create Event model
        - New file: src/models/event.rs
        - Pattern: src/models/user.rs
        ...

Me: Execute that task. Follow the pattern in src/models/user.rs exactly.

Cursor: [Shows proposed changes to create event.rs and modify mod.rs]

Me: [Reviews diff, accepts changes]

$ cargo test
# Tests pass

$ git add -A && git commit -m "Task 1.2: Create Event model"
```
