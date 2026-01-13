# ============================================================================
# Darkzloop Quick Demo - 15 Second Version
# ============================================================================
# This is a shorter version optimized for social media.
# Run with: vhs demo-quick.tape
# ============================================================================

Output demo-quick.gif
Set Shell "bash"
Set FontSize 20
Set Width 1000
Set Height 600
Set Padding 20
Set FontFamily "JetBrains Mono"
Set Theme "Catppuccin Mocha"
Set WindowBar "Rings"
Set TypingSpeed 30ms

# Setup (hidden)
Hide
Type "export PS1='➜ '"
Enter
Type "clear"
Enter
Show

# The 3-command promise
Type "# 🚀 Darkzloop in 30 seconds"
Enter
Sleep 1s

Type "pip install darkzloop"
Enter
Sleep 1.5s

Type "darkzloop config native claude"
Enter
Sleep 1s
Type "✓ Configured: Claude CLI"
Enter
Sleep 500ms

Type "darkzloop init"
Enter
Sleep 500ms
Type "✓ Detected: Rust (Cargo.toml)"
Enter
Type "✓ Created: darkzloop.json"
Enter
Sleep 500ms

Type `darkzloop fix "Add retry logic to payment webhook"`
Enter
Sleep 500ms
Type "⚙️  PLANNING → EXECUTING → TESTING → DONE"
Enter
Type "✓ All gates passed"
Enter
Type "✓ Fix applied!"
Enter
Sleep 2s

Type "# ♾️ Reliable. Autonomous. Model-Agnostic."
Enter
Sleep 3s
