# Changelog

All notable changes to Darkzloop will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-01-13

### 🎉 Initial Public Release

**Darkzloop is now model-agnostic!** Use your existing Claude, Copilot, or Ollama subscriptions.

### Added

#### Core Engine
- **Finite State Machine (FSM)** - 7-state machine with strict transitions
  - States: IDLE → PLANNING → EXECUTING → TESTING → REMEDIATING → BLOCKED → DONE
  - Per-task retry tracking (circuit breaker per task)
  - Global consecutive failure tracking
  - Max iterations limit (default: 100)

- **Manifest Protocol** - Read-before-write enforcement
  - Files must be read before they can be modified
  - Context window tracking (re-read required if file pruned)
  - Sensitive file prompts (config/secrets protection)
  - Full access audit trail

- **Tiered Quality Gates**
  - Tier 1: Must-pass (cargo check, cargo test)
  - Tier 2: Should-pass with auto-fix (cargo clippy → cargo fmt)
  - Tier 3: Optional (cargo audit)

- **Semantic Expansion**
  - 50+ built-in synonym clusters
  - Project-specific learning glossary
  - Codebase term scanning
  - No external API calls (100% local)

#### CLI Interface
- `darkzloop init` - Auto-detect stack (Rust/Python/Node/Go)
- `darkzloop plan` - Generate execution plan with semantic expansion
- `darkzloop run` - Execute with FSM control and safety checks
- `darkzloop fix "..."` - One-shot fixes without manual spec
- `darkzloop status` - Show current loop state
- `darkzloop graph` - Visualize task DAG (ASCII/HTML/Mermaid)
- `darkzloop config native <tool>` - Configure BYOA mode
- `darkzloop config api <provider>` - Configure direct API
- `darkzloop doctor` - Environment diagnostics

#### BYOA (Bring Your Own Auth)
- **Shell Executor** - Pipe prompts to native CLI tools
  - Claude CLI (`claude --print`)
  - GitHub Copilot (`gh copilot suggest`)
  - Ollama (`ollama run llama3.1`)
  - llm CLI (`llm -m claude-3-sonnet`)
  - Aider (`aider --message`)
  - Any custom command

- **12 Native Tool Presets**
  - `claude`, `claude-json`
  - `gh-copilot`
  - `ollama`, `ollama-codellama`, `ollama-deepseek`
  - `llm`, `llm-gpt4`, `llm-gemini`
  - `aider`
  - `openai`, `anthropic`

- **4-Strategy JSON Extraction** - Handle chatty CLI output
  - Markdown JSON blocks
  - Generic code blocks
  - Balanced brace matching
  - Greedy extraction (last resort)

#### Safety Features
- Git clean check before execution
- Automatic backup branches (`darkzloop-backup-YYYYMMDD-HHMMSS`)
- Dry run mode (`--dry-run`)
- Attended mode (approval at each step)

### Technical Details
- Python 3.10+ required
- ~4,500 lines across 22 modules
- Zero required API keys (BYOA mode)
- MIT licensed

---

## Philosophy

> *"The goal is not to build a smarter agent. It's to build a more disciplined one."*

Darkzloop implements the **Ralph Loop** methodology:
1. **Spec** - Define what you want (the "Pin")
2. **Plan** - Break into tasks with dependencies (DAG)
3. **Execute** - Agent works within strict boundaries
4. **Verify** - Tests must pass before accepting changes
5. **Learn** - Build project-specific vocabulary over time

The agent is powerful. The **system** keeps it honest.
