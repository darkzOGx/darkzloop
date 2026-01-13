# Using darkzloop with Claude Code

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) is Anthropic's CLI tool for agentic coding. It's well-suited for darkzloop because it can read files, execute commands, and make changes autonomously.

## Setup

1. Install Claude Code following [the official docs](https://docs.anthropic.com/en/docs/claude-code)

2. Initialize darkzloop in your project:
   ```bash
   cd your-project
   darkzloop init
   ```

3. Create your spec and plan:
   ```bash
   darkzloop spec --edit
   darkzloop plan --edit
   ```

## Running Iterations

### Manual Iteration

Run a single iteration:
```bash
claude "$(cat darkzloop-prompt.md)"
```

Or with the file directly:
```bash
claude --print "Please read darkzloop-prompt.md and execute one iteration of the loop."
```

### Attended Loop

Run with manual confirmation between iterations:
```bash
while true; do
    echo "Starting iteration..."
    claude "$(cat darkzloop-prompt.md)"
    
    # Quality gates
    cargo test || { echo "Tests failed"; break; }
    
    # Commit
    git add -A && git commit -m "darkzloop iteration $(date +%s)"
    
    read -p "Continue? (y/n) " answer
    [[ "$answer" != "y" ]] && break
done
```

### Unattended Loop

Run fully autonomous (after you trust the setup):
```bash
#!/bin/bash
MAX_FAILURES=3
failures=0

while [ $failures -lt $MAX_FAILURES ]; do
    claude "$(cat darkzloop-prompt.md)"
    
    if cargo test; then
        failures=0
        git add -A && git commit -m "darkzloop $(date +%s)"
    else
        ((failures++))
        git checkout -- .
        echo "Failure $failures/$MAX_FAILURES"
    fi
    
    sleep 5
done
```

## Tips for Claude Code

### Keep Context Focused

Claude Code maintains conversation context. For darkzloop, start fresh sessions for implementation to avoid context rot:

```bash
# Start a new session for implementation
claude --new-session "$(cat darkzloop-prompt.md)"
```

### Use Print Mode for Inspection

Check what Claude plans to do before executing:
```bash
claude --print "Read DARKZLOOP_PLAN.md and tell me what the next task is"
```

### Limit File Edits

If Claude is modifying too many files, be more explicit in your prompt:
```bash
claude "Read darkzloop-prompt.md. Only modify files explicitly listed in the current task."
```

## Example Session

```bash
$ darkzloop init
🔄 Initializing darkzloop

Detected: rust
  Test: cargo test
  Format: cargo fmt --check
  Lint: cargo clippy -- -D warnings

  ✅ Created darkzloop.json
  ✅ Created DARKZLOOP_SPEC.md
  ✅ Created DARKZLOOP_PLAN.md

$ # Edit your spec and plan
$ darkzloop spec --edit
$ darkzloop plan --edit

$ # Run first iteration attended
$ claude "$(cat darkzloop-prompt.md)"

# Claude reads spec, finds first task, makes changes...

$ cargo test
running 15 tests ... ok

$ git add -A && git commit -m "Task 1.1: Add events migration"

$ # Continue with next iteration
$ claude "$(cat darkzloop-prompt.md)"
```

## Troubleshooting

### Claude ignores the spec
Make sure your spec has strong linkage—file paths and line numbers. Vague specs lead to invention.

### Too many changes per iteration
Add to your prompt: "Complete only ONE task per iteration. Stop after the first task."

### Claude creates new patterns instead of following existing ones
Ensure your spec's "Patterns to follow" section has exact file paths and line ranges.
