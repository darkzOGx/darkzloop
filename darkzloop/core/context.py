"""
darkzloop Context Manager

Implements token pruning and rolling windows to prevent context explosion.
In recursive loops, chat history explodes quickly - this keeps it bounded.

Strategies:
1. Summarization Gate: Compress old iterations into summaries
2. Rolling Window: Keep only N recent detailed steps
3. Mermaid as Memory: Use the graph topology as compressed state
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import json


@dataclass
class IterationSummary:
    """Compressed summary of a completed iteration."""
    iteration: int
    task_id: str
    outcome: str  # "success" | "failure" | "partial"
    key_changes: List[str]  # Files modified
    commit_hash: Optional[str]
    one_liner: str  # Human-readable one-line summary
    
    def to_compact(self) -> str:
        """Ultra-compact representation (~50 tokens)."""
        changes = ",".join(self.key_changes[:3])
        return f"[i{self.iteration}] {self.task_id}: {self.outcome} | {changes} | {self.one_liner[:50]}"


@dataclass
class DetailedStep:
    """Full detail of a recent step (not yet summarized)."""
    state: str
    timestamp: str
    input_summary: str
    output_summary: str
    files_touched: List[str]
    raw_output: Optional[str] = None  # Only kept for very recent
    
    def token_estimate(self) -> int:
        """Rough estimate of tokens this step consumes."""
        text = f"{self.input_summary} {self.output_summary} {self.raw_output or ''}"
        return len(text) // 4  # Rough approximation


@dataclass
class ContextWindow:
    """
    Manages the agent's context window for token economy.
    
    Structure:
    - Goal: Always present (anchors the agent)
    - FSM State: Current position in state machine
    - Summaries: Compressed history of past iterations
    - Recent Steps: Detailed info from current iteration
    - Current Task: Full detail of what to do now
    """
    
    # Configuration
    max_summaries: int = 10  # Keep last N iteration summaries
    max_recent_steps: int = 5  # Keep last N detailed steps
    max_raw_output_tokens: int = 500  # Truncate raw outputs
    target_total_tokens: int = 4000  # Target context size
    
    # Content
    goal: str = ""
    spec_excerpt: str = ""  # Relevant spec sections only
    fsm_compact: str = ""
    summaries: List[IterationSummary] = field(default_factory=list)
    recent_steps: List[DetailedStep] = field(default_factory=list)
    current_task_json: str = ""
    
    def set_goal(self, goal: str, spec_excerpt: str = ""):
        """Set the anchoring goal (always kept)."""
        self.goal = goal
        self.spec_excerpt = spec_excerpt
    
    def update_fsm(self, fsm_compact: str):
        """Update FSM state string."""
        self.fsm_compact = fsm_compact
    
    def add_step(self, step: DetailedStep):
        """Add a detailed step, pruning old ones if needed."""
        # Truncate raw output
        if step.raw_output and len(step.raw_output) > self.max_raw_output_tokens * 4:
            step.raw_output = step.raw_output[:self.max_raw_output_tokens * 4] + "...[truncated]"
        
        self.recent_steps.append(step)
        
        # Prune oldest if over limit
        while len(self.recent_steps) > self.max_recent_steps:
            self.recent_steps.pop(0)
    
    def complete_iteration(self, summary: IterationSummary):
        """
        Called at CHECKPOINT - compresses current iteration into summary.
        This is the "Summarization Gate".
        """
        self.summaries.append(summary)
        
        # Clear detailed steps (they're now summarized)
        self.recent_steps = []
        
        # Prune old summaries
        while len(self.summaries) > self.max_summaries:
            self.summaries.pop(0)
    
    def set_current_task(self, task_json: str):
        """Set the current task (full detail)."""
        self.current_task_json = task_json
    
    def build_context(self) -> str:
        """
        Build the complete context string for the agent.
        This is what gets sent to the LLM.
        """
        sections = []
        
        # Goal anchor (always present)
        sections.append(f"=== GOAL ===\n{self.goal}")
        
        # Spec excerpt (relevant sections only)
        if self.spec_excerpt:
            sections.append(f"=== SPEC (relevant) ===\n{self.spec_excerpt}")
        
        # FSM state (minimal)
        sections.append(f"=== STATE ===\n{self.fsm_compact}")
        
        # Compressed history
        if self.summaries:
            history_lines = [s.to_compact() for s in self.summaries]
            sections.append(f"=== HISTORY (compressed) ===\n" + "\n".join(history_lines))
        
        # Recent detailed steps
        if self.recent_steps:
            recent_lines = []
            for step in self.recent_steps:
                recent_lines.append(
                    f"[{step.state}] {step.input_summary} -> {step.output_summary}"
                )
            sections.append(f"=== RECENT ===\n" + "\n".join(recent_lines))
        
        # Current task (full detail)
        if self.current_task_json:
            sections.append(f"=== CURRENT TASK ===\n{self.current_task_json}")
        
        return "\n\n".join(sections)
    
    def estimate_tokens(self) -> int:
        """Estimate current token usage."""
        context = self.build_context()
        return len(context) // 4
    
    def get_pruning_stats(self) -> dict:
        """Return stats about context management."""
        return {
            "summaries_kept": len(self.summaries),
            "recent_steps": len(self.recent_steps),
            "estimated_tokens": self.estimate_tokens(),
            "target_tokens": self.target_total_tokens,
        }


class ContextManager:
    """
    High-level manager for context across the entire loop lifecycle.
    Handles persistence and automatic pruning.
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.window = ContextWindow(
            max_summaries=self.config.get("max_summaries", 10),
            max_recent_steps=self.config.get("max_recent_steps", 5),
            target_total_tokens=self.config.get("target_tokens", 4000),
        )
        self.mermaid_state: str = ""  # Current Mermaid graph
    
    def initialize(self, goal: str, spec_excerpt: str = ""):
        """Initialize with the goal and relevant spec."""
        self.window.set_goal(goal, spec_excerpt)
    
    def record_step(
        self,
        state: str,
        input_summary: str,
        output_summary: str,
        files_touched: List[str] = None,
        raw_output: str = None
    ):
        """Record a step in the current iteration."""
        step = DetailedStep(
            state=state,
            timestamp=datetime.now().isoformat(),
            input_summary=input_summary,
            output_summary=output_summary,
            files_touched=files_touched or [],
            raw_output=raw_output,
        )
        self.window.add_step(step)
    
    def checkpoint(
        self,
        iteration: int,
        task_id: str,
        outcome: str,
        key_changes: List[str],
        one_liner: str,
        commit_hash: str = None
    ):
        """
        Checkpoint at end of iteration.
        Compresses everything into a summary.
        """
        summary = IterationSummary(
            iteration=iteration,
            task_id=task_id,
            outcome=outcome,
            key_changes=key_changes,
            commit_hash=commit_hash,
            one_liner=one_liner,
        )
        self.window.complete_iteration(summary)
    
    def get_context_for_agent(self, fsm_compact: str, current_task_json: str) -> str:
        """Build and return the context string for the agent."""
        self.window.update_fsm(fsm_compact)
        self.window.set_current_task(current_task_json)
        return self.window.build_context()
    
    def update_mermaid(self, mermaid: str):
        """
        Update the Mermaid graph state.
        This can serve as an alternative "memory" of the loop.
        """
        self.mermaid_state = mermaid
    
    def get_mermaid_as_memory(self) -> str:
        """
        Use the Mermaid graph as compressed memory.
        The graph topology encodes what has happened.
        """
        return self.mermaid_state
    
    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {
            "goal": self.window.goal,
            "spec_excerpt": self.window.spec_excerpt,
            "summaries": [
                {
                    "iteration": s.iteration,
                    "task_id": s.task_id,
                    "outcome": s.outcome,
                    "key_changes": s.key_changes,
                    "commit_hash": s.commit_hash,
                    "one_liner": s.one_liner,
                }
                for s in self.window.summaries
            ],
            "mermaid_state": self.mermaid_state,
        }
    
    @classmethod
    def from_dict(cls, data: dict, config: dict = None) -> "ContextManager":
        """Restore from persistence."""
        mgr = cls(config)
        mgr.window.goal = data.get("goal", "")
        mgr.window.spec_excerpt = data.get("spec_excerpt", "")
        mgr.window.summaries = [
            IterationSummary(**s) for s in data.get("summaries", [])
        ]
        mgr.mermaid_state = data.get("mermaid_state", "")
        return mgr


# =============================================================================
# Summarization Helpers
# =============================================================================

def create_iteration_summary(
    iteration: int,
    task_id: str,
    success: bool,
    files_changed: List[str],
    commit_hash: str = None,
    error: str = None
) -> IterationSummary:
    """Helper to create iteration summaries."""
    outcome = "success" if success else "failure"
    
    if success:
        one_liner = f"Completed {task_id}"
    else:
        one_liner = f"Failed {task_id}: {error[:30] if error else 'unknown'}"
    
    return IterationSummary(
        iteration=iteration,
        task_id=task_id,
        outcome=outcome,
        key_changes=files_changed[:5],  # Max 5 files
        commit_hash=commit_hash,
        one_liner=one_liner,
    )


def extract_relevant_spec_sections(full_spec: str, task_sections: List[str]) -> str:
    """
    Extract only the relevant sections from the spec.
    Reduces tokens by not including the entire spec.
    """
    # Simple implementation - look for section headers
    lines = full_spec.split('\n')
    relevant_lines = []
    in_relevant_section = False
    
    for line in lines:
        # Check if this is a header for a relevant section
        if line.startswith('#'):
            in_relevant_section = any(
                section.lower() in line.lower() 
                for section in task_sections
            )
        
        if in_relevant_section:
            relevant_lines.append(line)
    
    return '\n'.join(relevant_lines) if relevant_lines else full_spec[:1000]


if __name__ == "__main__":
    # Demo context management
    mgr = ContextManager({"max_summaries": 5})
    
    mgr.initialize(
        goal="Build event analytics API",
        spec_excerpt="## Requirements\n1. POST /api/events endpoint\n2. Rate limiting"
    )
    
    # Simulate an iteration
    mgr.record_step(
        state="PLAN",
        input_summary="Read spec and plan",
        output_summary="Selected task 1.1: Create migration",
        files_touched=["DARKZLOOP_PLAN.md"]
    )
    
    mgr.record_step(
        state="EXECUTE",
        input_summary="Create migrations/005_events.sql",
        output_summary="Wrote 45 lines",
        files_touched=["migrations/005_events.sql"]
    )
    
    # Checkpoint
    mgr.checkpoint(
        iteration=1,
        task_id="1.1",
        outcome="success",
        key_changes=["migrations/005_events.sql"],
        one_liner="Created events table migration",
        commit_hash="abc1234"
    )
    
    # Build context for next iteration
    context = mgr.get_context_for_agent(
        fsm_compact="[FSM] state=plan iter=1 fails=0",
        current_task_json='{"id": "1.2", "description": "Create Event model"}'
    )
    
    print("Context for agent:")
    print(context)
    print(f"\nEstimated tokens: {mgr.window.estimate_tokens()}")
