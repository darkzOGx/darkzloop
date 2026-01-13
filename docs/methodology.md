# The Methodology

Darkzloop implements the **Ralph Loops** methodology for autonomous software development.

## The Economics Have Changed

Running a coding agent continuously costs approximately **$10/hour** with current models. This changes everything:

- Continuous execution becomes the default
- Output rate clears backlog-sized work quickly
- The important metric becomes **cost per backlog consumed**, not cost per hour
- A widening gap forms between teams that can run reliable loops and teams that cannot

## Software Development vs Software Engineering

| Aspect | Software Development | Software Engineering |
|--------|---------------------|---------------------|
| What | Writing code | Designing systems |
| Cost | $10/hour (automated) | Human expertise |
| Focus | Feature implementation | Constraints, safety, reliability |
| Role | Delegated to agents | Your primary job |

**The new job**: Stop hand-carrying cargo. Operate the locomotive and standardize the containers.

## Screwdriver Before Jackhammer

- **Jackhammer**: Full-power automation (unattended looping, heavy orchestration)
- **Screwdriver**: Manual fundamentals (shaping specs, controlling context, learning failure modes)

Master the fundamentals first. Graduate to power tools when you understand the failure modes.

## Context Windows Are Arrays

The context window is an array. Understanding this is crucial:

- Less in the array → less sliding → fewer degradations
- More in the array → more sliding → earlier compaction
- **Compaction is lossy**. Loss drops critical anchors and produces drift.

This is why phase separation matters. Keep planning and implementation in separate contexts.

## The System Boundary

The "system" includes:
- Your application
- The operating system
- External vendors/APIs
- The AI model itself

Reliability requires engineering across this entire boundary. Your job is to build the rails that keep the system stable.

## Loops → Chains → Autonomous Systems

### Level 1: Manual Fundamentals (Screwdriver)
- Generate specs via conversation
- Edit and tighten constraints
- Keep context minimal
- Operate attended

### Level 2: Unattended Looping (Jackhammer)
- `while true` style runs
- Single objective per iteration
- Automated tests + commit
- Checkpointed state

### Level 3: Orchestrated Loops
- Multiple loops running in parallel
- Reactive chaining as needed
- Actor/pub-sub patterns

### Level 4: Autonomous Product Systems
- Ship behind feature flags
- Deploy without code review
- Observe analytics
- Decide whether changes worked
- Decide whether to optimize further

## The Pottery Wheel Process

Spec-building is iterative:

1. **Probe understanding**: Ask the model what it thinks the spec means
2. **Apply judgment**: Identify gaps or misunderstandings
3. **Reshape**: Tighten constraints, add links, clarify keywords
4. **Validate**: Run a few iterations attended
5. **Refine**: If direction drifts, adjust and restart

Don't try to perfect the spec upfront. Let loop behavior inform refinements.

## Robots-First Thinking

Beyond workflow, consider redesigning your stack for machines:

- Question assumptions: user space, TTY, JSON serialization
- Optimize for tokenization (JSON is suboptimal)
- Control the stack to enable cheaper, more reliable agents

The teams that redesign for AI assistance will pull ahead.
