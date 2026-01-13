# ♾️ Darkzloop

**Reliable. Autonomous. Model-Agnostic.**  
*Stop hand-carrying cargo. Operate the locomotive.*

[![PyPI](https://img.shields.io/pypi/v/darkzloop)](https://pypi.org/project/darkzloop/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Darkzloop is a terminal-based agent runner that turns **any LLM** into a rigorous software engineer. Unlike flaky chat agents, Darkzloop uses a **Finite State Machine**, **Circuit Breakers**, and **Manifest Protocols** to prevent hallucinations and infinite loops.

**🔥 The Killer Feature: Bring Your Own Auth (BYOA)**  
Darkzloop doesn't need your API keys. It pipes context directly to the tools you're already logged into:

`Claude CLI` • `GitHub Copilot` • `Ollama` • `llm CLI` • `Aider`

---

## ⚡ Quick Start (30 Seconds)

### 1. Install
```bash
pip install darkzloop
```

### 2. Configure (No API Keys Needed!)
Tell Darkzloop which tool to drive:

```bash
# If you have Claude Pro/Enterprise
darkzloop config native claude

# If you have GitHub Copilot
darkzloop config native gh-copilot

# If you want 100% local/offline (Llama 3, DeepSeek)
darkzloop config native ollama
```

### 3. Verify
Ensure your tools are reachable:

```bash
darkzloop doctor
# ✓ Executor: SHELL
# ✓ Command: claude
# ✓ Authenticated: user@example.com
```

### 4. Fix Code
Run the "Fast Lane" command to fix bugs without ceremony:

```bash
darkzloop fix "Add a retry mechanism to the payment webhook"
```

---

## 🛡️ Why Darkzloop?

Most AI agents are just *"loops in a while(true) block."* They drift, hallucinate, and overwrite good code. Darkzloop is different:

| Feature | The Problem | The Darkzloop Solution |
|---------|-------------|------------------------|
| **Manifest Protocol** | Agent edits files blindly | **Read-Before-Write**: Writes blocked unless file is in context |
| **Circuit Breakers** | Agent tries the same wrong fix 10× | **Task Limits**: Hard stop after 3 failed attempts per task |
| **Tiered Gates** | Agent breaks the build | **Quality Control**: Tests must pass before loop completes |
| **Semantic Expansion** | "Fix billing" misses `src/invoice.rs` | **Synonyms**: Auto-expands intent to find relevant files |
| **Git Safety** | Agent overwrites uncommitted work | **Backup Branches**: Auto-creates restore points before execution |

---

## 🧠 Supported Backends

Darkzloop works with **any tool that accepts text via stdin**.

| Backend | Best For | Setup |
|---------|----------|-------|
| **Claude CLI** | Complex refactors, high reasoning | `darkzloop config native claude` |
| **Ollama** | Privacy, offline, free | `darkzloop config native ollama` |
| **GitHub Copilot** | Quick fixes with Enterprise license | `darkzloop config native gh-copilot` |
| **llm CLI** | Universal adapter (50+ providers) | `darkzloop config native llm` |
| **Direct API** | Full control, streaming | `darkzloop config api anthropic` |

---

## 🛠️ Full Workflow

### Initialize a Project
```bash
cd my-rust-project
darkzloop init
# ✓ Detected: Rust (Cargo.toml)
# ✓ Created: darkzloop.json
# ✓ Created: DARKZLOOP_SPEC.md
```

Darkzloop auto-detects your stack and configures appropriate quality gates:
- **Rust**: `cargo check`, `cargo test`, `cargo clippy`
- **Python**: `pytest`, `ruff`, `black`
- **Node**: `npm test`, `eslint`
- **Go**: `go build`, `go test`, `golangci-lint`

### Plan a Feature
```bash
darkzloop plan --task "Add rate limiting to the API endpoints"
# Semantic expansion: rate → [throttle, limit, 429, quota, bucket]
# Found relevant files: src/middleware/auth.rs, src/api/handlers.rs
```

### Execute with Oversight
```bash
darkzloop run --attended
# FSM State: PLANNING → EXECUTING → TESTING → DONE
# ✓ All gates passed
# ✓ Created commit: "feat: Add rate limiting middleware"
```

### One-Shot Fixes (Fast Lane)
```bash
darkzloop fix "Login button not responding on mobile"
# → Searches codebase semantically
# → Generates temporary spec
# → Executes fix
# → Runs tests
# → Done in one command
```

---

## 📦 Architecture

Darkzloop implements the **Ralph Loop** methodology with industrial-grade hardening:

```
┌─────────────────────────────────────────────────────────────┐
│                    DARKZLOOP CONTROL PLANE                   │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│  │   FSM    │───▶│ Manifest │───▶│  Gates   │               │
│  │  Engine  │    │ Protocol │    │ (Tests)  │               │
│  └──────────┘    └──────────┘    └──────────┘               │
│        │              │               │                      │
│        ▼              ▼               ▼                      │
│  ┌─────────────────────────────────────────┐                │
│  │         Semantic Expansion Layer         │                │
│  │   (Synonyms, Learning Glossary, Search)  │                │
│  └─────────────────────────────────────────┘                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   Executor Layer    │
              │  (Model-Agnostic)   │
              └──────────┬──────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ┌─────────┐     ┌──────────┐     ┌─────────┐
   │ Claude  │     │  Ollama  │     │   API   │
   │  CLI    │     │ (Local)  │     │ (SDK)   │
   └─────────┘     └──────────┘     └─────────┘
```

### Finite State Machine

The FSM enforces strict state transitions—no "hallucinated" jumps:

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
┌──────┐    ┌───────────┐    ┌───────────┐    ┌─────────┐│
│ IDLE │───▶│ PLANNING  │───▶│ EXECUTING │───▶│ TESTING ││
└──────┘    └───────────┘    └───────────┘    └────┬────┘│
                                                   │     │
                              ┌─────────────┐      │     │
                              │             │      │     │
                    ┌─────────┤ REMEDIATING │◀─────┘     │
                    │         │             │ (tests     │
                    │         └─────────────┘  failed)   │
                    │               │                    │
                    │               │ (fix applied)      │
                    │               └────────────────────┘
                    │
                    │ (max retries exceeded)
                    ▼
              ┌─────────┐         ┌──────┐
              │ BLOCKED │         │ DONE │◀── (tests passed)
              └─────────┘         └──────┘
```

| State | Description | Exit Condition |
|-------|-------------|----------------|
| **IDLE** | Waiting for task | Plan approved |
| **PLANNING** | Agent generates plan | Plan validated |
| **EXECUTING** | Agent works on current task | Task complete |
| **TESTING** | Running tiered gates | Pass → DONE, Fail → REMEDIATING |
| **REMEDIATING** | Self-healing after test failure (max 3 retries per task) | Fix applied → TESTING |
| **BLOCKED** | Circuit breaker tripped | Human intervention required |
| **DONE** | All tasks complete, all gates passed | — |

### Key Components

- **FSM Engine**: 7-state machine with strict transitions—no skipping states
- **Manifest Protocol**: Tracks every file read/write, enforces read-before-write, **user must approve** sensitive file additions
- **Circuit Breakers**: Max iterations (100), consecutive failures (3), per-task retries (3)
- **Semantic Layer**: Expands search terms using **local synonym matching** + learning glossary (no external API calls, no data leaves your machine)
- **Executor Interface**: Pluggable backends via stdin/stdout protocol

### The Manifest Protocol (Read-Before-Write)

```
┌─────────────────────────────────────────────────────────────┐
│                      MANIFEST RULES                          │
├─────────────────────────────────────────────────────────────┤
│  ✓ Agent wants to READ src/api/users.rs                     │
│    → Allowed (adds to manifest automatically)               │
│                                                              │
│  ✗ Agent wants to WRITE src/api/users.rs (not in manifest)  │
│    → BLOCKED: "Must read file before modifying"             │
│                                                              │
│  ⚠ Agent wants to READ config/secrets.json                  │
│    → PROMPT: "Add sensitive file to manifest? [y/N]"        │
│                                                              │
│  ✓ Agent wants to WRITE src/api/users.rs (in manifest)      │
│    → Allowed (file was previously read)                     │
└─────────────────────────────────────────────────────────────┘
```

This prevents the #1 agent failure mode: blindly overwriting files it hasn't seen.

### Semantic Expansion

When you say `darkzloop fix "billing issue"`, the semantic layer expands your intent:

```
Input:  "billing"
        ↓
Synonyms: ["invoice", "payment", "charge", "subscription", "price"]
        ↓
Learned: ["stripe", "checkout"] (from project glossary)
        ↓
Search:  Finds src/billing.rs, src/invoice.rs, src/stripe/webhook.rs
```

**Implementation**: Local dictionary + project-specific learning glossary stored in `.darkzloop/glossary.json`. No embeddings, no external calls—fast and private.

---

## 🔧 Configuration

### Global Config (`~/.darkzloop/config.json`)
```json
{
  "agent": {
    "mode": "shell",
    "command": "claude",
    "args": ["--print"]
  },
  "default_attended": true,
  "default_auto_commit": true
}
```

### Project Config (`./darkzloop.json`)
```json
{
  "project": { "name": "my-api", "type": "rust" },
  "gates": {
    "tier1": { "commands": ["cargo check", "cargo test"] },
    "tier2": { "commands": ["cargo clippy"], "auto_fix_commands": ["cargo fmt"] }
  },
  "loop": {
    "max_iterations": 100,
    "max_consecutive_failures": 3,
    "max_task_retries": 3
  }
}
```

---

## 📊 Commands

| Command | Description |
|---------|-------------|
| `darkzloop init` | Initialize project with auto-detected stack |
| `darkzloop plan` | Generate execution plan from spec or task |
| `darkzloop run` | Execute plan with FSM control |
| `darkzloop fix "..."` | One-shot fix without manual spec |
| `darkzloop status` | Show current loop state |
| `darkzloop graph` | Visualize task DAG |
| `darkzloop config native <tool>` | Configure native CLI backend |
| `darkzloop config api <provider>` | Configure direct API backend |
| `darkzloop doctor` | Verify environment and configuration |

---

## 🚨 Safety Features

Darkzloop is designed to **never lose your work**:

1. **Git Clean Check**: Warns before running with uncommitted changes
2. **Backup Branches**: Creates `darkzloop-backup-YYYYMMDD-HHMMSS` before execution
3. **Dry Run Mode**: `--dry-run` shows what would happen without executing
4. **Attended Mode**: Requires approval at each major step
5. **Read-Before-Write**: Cannot modify files not explicitly loaded into context
6. **Sensitive File Prompts**: Asks permission before reading config/secrets

---

## 🎯 Philosophy

> *"The goal is not to build a smarter agent. It's to build a more disciplined one."*

Darkzloop is based on the **Ralph Loop** methodology:

1. **Spec**: Define what you want (the "Pin")
2. **Plan**: Break it into tasks with dependencies (DAG)
3. **Execute**: Let the agent work within strict boundaries
4. **Verify**: Run tests before accepting any change
5. **Learn**: Build project-specific vocabulary over time

The agent is powerful. The **system** keeps it honest.

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
git clone https://github.com/yourusername/darkzloop
cd darkzloop
pip install -e ".[dev]"
pytest
```

---

## 📄 License

MIT © 2025

---

<p align="center">
  <strong>Stop debugging your debugger. Start shipping.</strong><br>
  <code>pip install darkzloop && darkzloop config native claude && darkzloop fix "your bug here"</code>
</p>
