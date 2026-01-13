# Using darkzloop with Aider

[Aider](https://aider.chat) is a command-line AI coding assistant that works well for darkzloop's loop-based approach.

## Setup

1. Install Aider:
   ```bash
   pip install aider-chat
   ```

2. Initialize darkzloop:
   ```bash
   cd your-project
   darkzloop init
   ```

3. Create your spec and plan

## Running Iterations

### Single Iteration

```bash
aider --message-file darkzloop-prompt.md \
      --read DARKZLOOP_SPEC.md \
      --read DARKZLOOP_PLAN.md
```

Or inline:
```bash
aider --message "Read DARKZLOOP_SPEC.md and DARKZLOOP_PLAN.md. Execute the next uncompleted task from the plan."
```

### Attended Loop

```bash
#!/bin/bash
while true; do
    aider --message-file darkzloop-prompt.md \
          --read DARKZLOOP_SPEC.md \
          --read DARKZLOOP_PLAN.md \
          --yes  # Auto-accept changes
    
    # Quality gates
    cargo test || { echo "Tests failed"; break; }
    cargo fmt --check || cargo fmt
    
    # Aider auto-commits, so we just verify
    echo "Iteration complete"
    
    read -p "Continue? (y/n) " answer
    [[ "$answer" != "y" ]] && break
done
```

### Unattended Loop

```bash
#!/bin/bash
MAX_FAILURES=3
failures=0

while [ $failures -lt $MAX_FAILURES ]; do
    aider --message-file darkzloop-prompt.md \
          --read DARKZLOOP_SPEC.md \
          --read DARKZLOOP_PLAN.md \
          --yes \
          --no-git  # We'll handle git ourselves
    
    if cargo test; then
        failures=0
        git add -A
        git commit -m "darkzloop iteration $(date +%s)"
    else
        ((failures++))
        git checkout -- .
        echo "Failure $failures/$MAX_FAILURES"
    fi
    
    sleep 2
done
```

## Aider-Specific Options

### Read-Only Context

Use `--read` for files Aider should see but not modify:
```bash
aider --read DARKZLOOP_SPEC.md \
      --read DARKZLOOP_PLAN.md \
      --read src/models/user.rs  # Pattern file
```

### Auto-Commits

Aider commits after each change by default. For darkzloop:
- Use default behavior for attended loops
- Use `--no-git` for unattended loops where you want control

### Model Selection

Aider supports multiple models. For darkzloop:
```bash
# Claude (recommended for complex tasks)
aider --model claude-3-5-sonnet-20241022

# GPT-4
aider --model gpt-4-turbo

# Local models via Ollama
aider --model ollama/deepseek-coder
```

## Tips for Aider

### Add Files Explicitly

Tell Aider which files to work on:
```bash
aider src/models/event.rs src/api/events.rs \
      --read DARKZLOOP_SPEC.md \
      --message "Implement the Event model following user.rs pattern"
```

### Use /read Command

In interactive mode, add context files:
```
/read DARKZLOOP_SPEC.md
/read src/models/user.rs
```

### Check /diff Before Committing

In interactive mode:
```
/diff  # See what changed
/commit  # Commit if satisfied
/undo  # Rollback if not
```

## Example Session

```bash
$ darkzloop init
$ darkzloop spec --edit
$ darkzloop plan --edit

$ aider --read DARKZLOOP_SPEC.md --read DARKZLOOP_PLAN.md

aider> Read the plan and tell me the next task
Task 1.2: Create Event model
- New file: src/models/event.rs
- Pattern: src/models/user.rs

aider> /add src/models/event.rs src/models/mod.rs

aider> Create the Event model following the pattern in src/models/user.rs

# Aider creates the files and shows diff

aider> /diff
# Review changes

aider> /commit
Committed: Create Event model

$ cargo test
running 12 tests ... ok
```

## Troubleshooting

### Aider modifies wrong files
Use `--read` for context files and only `/add` files that should be modified.

### Too many changes
Be specific in your message: "Only create src/models/event.rs following the user.rs pattern."

### Context getting stale
For long loops, restart Aider between iterations to get fresh context.
