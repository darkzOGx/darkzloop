# ============================================================================
# Darkzloop Demo Tape - Product Hunt Launch GIF
# ============================================================================
# Run with: vhs demo.tape
# Requires: https://github.com/charmbracelet/vhs
# ============================================================================

# Terminal Configuration
Output demo.gif
Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 800
Set Padding 20
Set FontFamily "JetBrains Mono"
Set Theme "Catppuccin Mocha"
Set WindowBar "Rings"
Set TypingSpeed 50ms

# ============================================================================
# Scene 1: Setup the scene (hidden)
# ============================================================================
Hide
Type "export PS1='➜ '"
Enter
Type "cd ~/projects/payment-api"
Enter
Type "clear"
Enter
Show

# ============================================================================
# Scene 2: Show the context - A Rust project with a bug
# ============================================================================
Type "# A payment API that needs retry logic"
Sleep 500ms
Enter
Sleep 500ms

Type "ls -la"
Sleep 300ms
Enter
Sleep 1.5s

Type "cat src/webhook.rs | head -20"
Sleep 300ms
Enter
Sleep 2s

# ============================================================================
# Scene 3: The 30-Second Promise - Install & Configure
# ============================================================================
Type "# Step 1: Install darkzloop"
Enter
Sleep 500ms

Type "pip install darkzloop"
Sleep 300ms
Enter
Sleep 1.5s

Type "# Step 2: Configure (BYOA - no API keys!)"
Enter
Sleep 500ms

Type "darkzloop config native claude"
Sleep 300ms
Enter
Sleep 1s

# Simulated output
Type "✓ Configured: Claude CLI"
Enter
Type "✓ Command: claude --print"
Enter
Sleep 1s

# ============================================================================
# Scene 4: Initialize the project
# ============================================================================
Type "darkzloop init"
Sleep 300ms
Enter
Sleep 1s

# Simulated output
Type "🔍 Detecting project type..."
Enter
Sleep 500ms
Type "✓ Detected: Rust (Cargo.toml)"
Enter
Sleep 300ms
Type "✓ Configured gates:"
Enter
Type "   Tier 1: cargo check, cargo test"
Enter
Type "   Tier 2: cargo clippy → cargo fmt"
Enter
Sleep 300ms
Type "✓ Created: darkzloop.json"
Enter
Type "✓ Created: DARKZLOOP_SPEC.md"
Enter
Sleep 1s

# ============================================================================
# Scene 5: The Magic - One-shot fix
# ============================================================================
Type "# Step 3: Fix the bug (one command!)"
Enter
Sleep 500ms

Type `darkzloop fix "Payment webhook fails on 429 errors. Add exponential backoff with jitter."`
Sleep 500ms
Enter
Sleep 1s

# ============================================================================
# Scene 6: FSM in Action
# ============================================================================
Type ""
Enter
Type "♾️  Darkzloop v0.6.0"
Enter
Type "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Enter
Sleep 500ms

# Planning phase
Type "⚙️  [FSM] IDLE → PLANNING"
Enter
Sleep 300ms
Type "🔍 [Semantic] Expanding search terms..."
Enter
Sleep 300ms
Type "   backoff → [retry, delay, jitter, sleep, exponential]"
Enter
Type "   webhook → [handler, endpoint, callback, hook]"
Enter
Type "   429 → [rate_limit, throttle, too_many_requests]"
Enter
Sleep 500ms

Type "📂 [Search] Found relevant files:"
Enter
Type "   src/webhook.rs (0.95 confidence)"
Enter
Type "   src/http_client.rs (0.82 confidence)"
Enter
Sleep 500ms

# Manifest - the safety feature
Type "📜 [Manifest] Building context..."
Enter
Sleep 300ms
Type "   ✓ Reading src/webhook.rs (added to manifest)"
Enter
Type "   ✓ Reading src/http_client.rs (added to manifest)"
Enter
Sleep 500ms

# Executing phase
Type "⚙️  [FSM] PLANNING → EXECUTING"
Enter
Sleep 500ms
Type "🤖 [Claude] Generating implementation..."
Enter
Sleep 1s
Type "✍️  [Write] Patching src/webhook.rs"
Enter
Type "   + Added: RetryConfig struct"
Enter
Type "   + Added: exponential_backoff_with_jitter()"
Enter
Type "   + Modified: handle_payment_webhook()"
Enter
Sleep 500ms

# Testing phase - the killer feature
Type "⚙️  [FSM] EXECUTING → TESTING"
Enter
Sleep 300ms
Type "🛡️  [Gate Tier 1] Running cargo check..."
Enter
Sleep 800ms
Type "   ✓ Passed (0 errors, 0 warnings)"
Enter
Sleep 300ms
Type "🛡️  [Gate Tier 1] Running cargo test..."
Enter
Sleep 800ms
Type "   ✓ Passed (12 tests, 0 failures)"
Enter
Sleep 300ms
Type "🛡️  [Gate Tier 2] Running cargo clippy..."
Enter
Sleep 500ms
Type "   ✓ Passed"
Enter
Sleep 500ms

# Success
Type "⚙️  [FSM] TESTING → DONE"
Enter
Sleep 300ms
Type "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Enter
Type "✨ Fix applied successfully!"
Enter
Type "📁 Backup: .darkzloop/backups/webhook.rs.20260113"
Enter
Type "🔗 Commit: feat: Add exponential backoff to payment webhook"
Enter
Sleep 1s

# ============================================================================
# Scene 7: Verify the fix
# ============================================================================
Type ""
Enter
Type "# Let's see what changed:"
Enter
Sleep 500ms

Type "git diff --stat"
Sleep 300ms
Enter
Sleep 1s

# Simulated diff output
Type " src/webhook.rs | 45 ++++++++++++++++++++++++++++++++++++"
Enter
Type " 1 file changed, 45 insertions(+)"
Enter
Sleep 2s

# ============================================================================
# Scene 8: The Tagline
# ============================================================================
Type ""
Enter
Type "# ♾️ Darkzloop: Reliable. Autonomous. Model-Agnostic."
Enter
Type "# pip install darkzloop"
Enter
Sleep 3s
