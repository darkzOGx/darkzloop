# Darkzloop - Product Hunt Launch Copy

## Tagline (60 chars max)
**Turn any LLM into a disciplined software engineer**

## One-liner (140 chars)
Model-agnostic agent runner with FSM control, circuit breakers, and "Bring Your Own Auth" - use Claude, Copilot, or Ollama without API keys.

---

## Description

### The Hook
Most AI coding agents are just loops in a `while(true)` block. They drift, hallucinate, and overwrite good code.

**Darkzloop is different.**

We built the control plane that makes any LLM behave like a disciplined engineer—not a chaotic intern.

### The Problem
- Agents edit files they've never seen
- Agents try the same broken fix 10 times
- Agents break the build and keep going
- API keys are a hassle and security risk

### The Solution
**Finite State Machine** - Strict state transitions prevent "hallucinated" actions
**Read-Before-Write** - Can't modify files not in context
**Circuit Breakers** - Hard stop after 3 failed attempts
**BYOA Mode** - Use your existing Claude/Copilot/Ollama subscription

### The Killer Feature: Bring Your Own Auth
```bash
pip install darkzloop
darkzloop config native claude  # Uses your Claude Pro subscription
darkzloop fix "Add retry logic"  # No API keys needed!
```

Darkzloop pipes prompts to tools you're already logged into. Your data never leaves your existing workflow.

### Why Now?
Claude Code, GitHub Copilot CLI, and Ollama have made powerful LLMs accessible via simple shell commands. But they lack guardrails.

Darkzloop adds the discipline layer without requiring another API subscription.

---

## First Comment (from maker)
Hey Product Hunt! 👋

I built Darkzloop because I was tired of babysitting AI coding agents.

Every tool promises "autonomous coding" but delivers chaos:
- Edits files it's never read
- Tries the same wrong fix forever
- Breaks the build and keeps going

Darkzloop fixes this with a simple principle: **Strict discipline beats raw intelligence.**

The FSM ensures the agent can only make valid moves. The Manifest Protocol blocks writes to files not in context. Circuit breakers stop infinite loops.

And the best part? **No API keys required.** If you have Claude Pro or GitHub Copilot, you already have everything you need.

Try it:
```bash
pip install darkzloop
darkzloop config native claude
darkzloop doctor
```

Would love your feedback! 🚀

---

## Maker's Comment Thread Prompts

**For skeptics:**
"But can't Claude/Copilot already do this?"
→ They can generate code, but they can't *discipline themselves*. Darkzloop adds the control plane.

**For enterprise users:**
"We can't use API keys due to security policy"
→ BYOA mode means your code goes through your existing authenticated CLI. No new API keys, no data sent to new endpoints.

**For local-first advocates:**
"I want to run everything offline"
→ `darkzloop config native ollama` gives you a 100% local, 100% free agent runner.

---

## Media Assets Needed

1. **Hero GIF** (15 seconds)
   - `pip install darkzloop`
   - `darkzloop config native claude`
   - `darkzloop fix "Add retry logic"`
   - Show FSM states: PLANNING → EXECUTING → TESTING → DONE

2. **Architecture Diagram**
   - Control Plane (FSM, Manifest, Gates)
   - Executor Layer (Shell, API, Mock)
   - Backend icons (Claude, Ollama, Copilot)

3. **Feature Grid**
   - FSM Engine ✅
   - Read-Before-Write ✅
   - Circuit Breakers ✅
   - Semantic Expansion ✅
   - Git Safety ✅

---

## Category Tags
- Developer Tools
- Artificial Intelligence
- Command Line Tools
- Open Source
- Productivity

## Pricing
**Free & Open Source** (MIT License)

Optional: API access for Anthropic/OpenAI if you prefer direct SDK integration.

---

## Social Copy

### Twitter/X
🚀 Launching Darkzloop on Product Hunt!

Turn any LLM into a disciplined software engineer.

✅ FSM-controlled execution
✅ Read-before-write protection
✅ Circuit breakers
✅ No API keys needed (BYOA mode)

Works with Claude, Copilot, Ollama.

pip install darkzloop

[link]

### LinkedIn
Excited to launch Darkzloop - a model-agnostic agent runner that brings discipline to AI coding.

The problem with current AI coding agents: they're just loops in a while(true) block. They drift, hallucinate, and break things.

Darkzloop adds:
• Finite State Machine control
• Read-before-write enforcement
• Circuit breakers for infinite loops
• "Bring Your Own Auth" - use existing subscriptions

No more babysitting your AI assistant.

Open source, MIT licensed.

[link]

### Hacker News
Show HN: Darkzloop – FSM-based agent runner for disciplined AI coding

I built this because I was tired of AI coding agents that:
- Edit files they've never seen
- Try the same broken fix forever
- Need yet another API key

Darkzloop wraps any LLM (Claude, Copilot, Ollama) with strict FSM control, read-before-write enforcement, and circuit breakers.

Key innovation: "BYOA" (Bring Your Own Auth) - pipe prompts to CLI tools you're already logged into. No new API keys.

```
pip install darkzloop
darkzloop config native claude
darkzloop fix "Add input validation"
```

MIT licensed. ~4,500 lines of Python.

Feedback welcome!

[GitHub link]
