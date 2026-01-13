"""
darkzloop Finite State Machine

Enforces strict state transitions to prevent agents from hallucinating
invalid moves. Reduces the "search space" at every step.

States:
    INIT -> PLAN -> EXECUTE -> OBSERVE -> CRITIQUE -> CHECKPOINT -> (loop or COMPLETE)

The agent can only transition along defined edges. Any attempt to jump
states (e.g., PLAN -> COMPLETE) is rejected.
"""

from enum import Enum, auto
from typing import Optional, Set, Dict, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json


class LoopState(Enum):
    """
    Valid states in the darkzloop FSM.
    
    Key distinction:
    - TASK_FAILURE: Retryable (tests failed, lint error). Can go back to PLAN.
    - FATAL_ERROR: Non-retryable (API down, auth invalid, max failures). Must stop.
    """
    INIT = "init"
    PLAN = "plan"
    EXECUTE = "execute"
    OBSERVE = "observe"
    CRITIQUE = "critique"
    CHECKPOINT = "checkpoint"
    COMPLETE = "complete"
    TASK_FAILURE = "task_failure"  # Retryable - tests failed, can try again
    FATAL_ERROR = "fatal_error"    # Non-retryable - must stop
    BLOCKED = "blocked"            # Waiting for human intervention


# Define valid state transitions (edges in the FSM graph)
VALID_TRANSITIONS: Dict[LoopState, Set[LoopState]] = {
    LoopState.INIT: {LoopState.PLAN, LoopState.FATAL_ERROR},
    LoopState.PLAN: {LoopState.EXECUTE, LoopState.BLOCKED, LoopState.FATAL_ERROR},
    LoopState.EXECUTE: {LoopState.OBSERVE, LoopState.TASK_FAILURE, LoopState.FATAL_ERROR},
    LoopState.OBSERVE: {LoopState.CRITIQUE, LoopState.TASK_FAILURE, LoopState.FATAL_ERROR},
    LoopState.CRITIQUE: {LoopState.CHECKPOINT, LoopState.EXECUTE, LoopState.TASK_FAILURE},  # Can retry via EXECUTE
    LoopState.CHECKPOINT: {LoopState.PLAN, LoopState.COMPLETE},  # Loop back or finish
    LoopState.COMPLETE: set(),  # Terminal state
    LoopState.TASK_FAILURE: {LoopState.PLAN, LoopState.FATAL_ERROR},  # Retry or give up
    LoopState.FATAL_ERROR: set(),  # Terminal state - cannot recover
    LoopState.BLOCKED: {LoopState.PLAN, LoopState.FATAL_ERROR},  # Needs human, then continue
}


@dataclass
class StateTransition:
    """Record of a state transition for audit trail."""
    from_state: LoopState
    to_state: LoopState
    timestamp: str
    reason: str
    iteration: int
    metadata: dict = field(default_factory=dict)


@dataclass 
class FSMContext:
    """
    The FSM context holds current state and transition history.
    This is the "control layer" that prevents illegal moves.
    
    Includes per-task retry tracking to prevent infinite loops:
    TASK_FAILURE -> PLAN -> TASK_FAILURE -> PLAN... (blocked after N retries)
    """
    current_state: LoopState = LoopState.INIT
    iteration: int = 0
    transitions: list = field(default_factory=list)
    max_iterations: int = 100
    consecutive_failures: int = 0
    max_consecutive_failures: int = 3
    
    # Per-task retry tracking (circuit breaker for individual tasks)
    task_retries: Dict[str, int] = field(default_factory=dict)
    current_task_id: Optional[str] = None
    max_task_retries: int = 3
    
    def can_transition(self, to_state: LoopState) -> bool:
        """Check if a transition is valid without executing it."""
        return to_state in VALID_TRANSITIONS.get(self.current_state, set())
    
    def get_valid_transitions(self) -> Set[LoopState]:
        """Return all valid next states from current state."""
        return VALID_TRANSITIONS.get(self.current_state, set())
    
    def transition(self, to_state: LoopState, reason: str = "", metadata: dict = None) -> bool:
        """
        Attempt a state transition.
        
        Returns True if successful, raises InvalidTransition if not allowed.
        """
        if not self.can_transition(to_state):
            valid = self.get_valid_transitions()
            raise InvalidTransitionError(
                f"Cannot transition from {self.current_state.value} to {to_state.value}. "
                f"Valid transitions: {[s.value for s in valid]}"
            )
        
        # Record the transition
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            timestamp=datetime.now().isoformat(),
            reason=reason,
            iteration=self.iteration,
            metadata=metadata or {}
        )
        self.transitions.append(transition)
        
        # Update state
        old_state = self.current_state
        self.current_state = to_state
        
        # Track iterations and failures
        if to_state == LoopState.CHECKPOINT:
            self.iteration += 1
            self.consecutive_failures = 0  # Reset on success
        elif to_state == LoopState.TASK_FAILURE:
            self.consecutive_failures += 1
            # Check if we should escalate to fatal
            if self.consecutive_failures >= self.max_consecutive_failures:
                # Don't auto-escalate here - let the caller decide
                pass
        elif to_state in {LoopState.PLAN, LoopState.EXECUTE}:
            # Don't reset failures when retrying - only on CHECKPOINT
            pass
        
        return True
    
    def is_terminal(self) -> bool:
        """Check if we're in a terminal state."""
        return self.current_state in {LoopState.COMPLETE, LoopState.FATAL_ERROR}
    
    def is_retryable_failure(self) -> bool:
        """Check if we're in a retryable failure state."""
        return self.current_state == LoopState.TASK_FAILURE
    
    def should_stop(self) -> tuple[bool, str]:
        """Check if the loop should stop and why."""
        if self.current_state == LoopState.COMPLETE:
            return True, "completed"
        if self.current_state == LoopState.FATAL_ERROR:
            return True, "fatal_error"
        if self.current_state == LoopState.BLOCKED:
            return True, "blocked_needs_human"
        if self.iteration >= self.max_iterations:
            return True, "max_iterations_reached"
        if self.consecutive_failures >= self.max_consecutive_failures:
            return True, "max_failures_reached"
        return False, ""
    
    def fail_task(self, reason: str = "", can_retry: bool = True) -> bool:
        """
        Record a task failure.
        
        Args:
            reason: Why the task failed
            can_retry: If True, goes to TASK_FAILURE (retryable). 
                      If False, goes to FATAL_ERROR (stops loop).
        """
        target_state = LoopState.TASK_FAILURE if can_retry else LoopState.FATAL_ERROR
        return self.transition(target_state, reason)
    
    def escalate_to_fatal(self, reason: str = "") -> bool:
        """Escalate from TASK_FAILURE to FATAL_ERROR (too many retries)."""
        if self.current_state == LoopState.TASK_FAILURE:
            return self.transition(LoopState.FATAL_ERROR, reason)
    
    def start_task(self, task_id: str):
        """
        Begin working on a task. Initializes retry counter if new.
        """
        self.current_task_id = task_id
        if task_id not in self.task_retries:
            self.task_retries[task_id] = 0
    
    def record_task_failure(self, reason: str = "") -> tuple[LoopState, str]:
        """
        Record a task failure with per-task retry tracking.
        
        Returns (next_state, message) indicating what happened:
        - (TASK_FAILURE, "retry") - Can retry this task
        - (BLOCKED, "max_retries") - Too many retries, need human
        - (FATAL_ERROR, "escalated") - Escalated to fatal
        
        This is the circuit breaker that prevents:
        TASK_FAILURE -> PLAN -> TASK_FAILURE -> PLAN... (infinite loop)
        """
        task_id = self.current_task_id
        
        if task_id:
            self.task_retries[task_id] = self.task_retries.get(task_id, 0) + 1
            retries = self.task_retries[task_id]
            
            if retries >= self.max_task_retries:
                # Circuit breaker: too many retries on this task
                self.transition(LoopState.BLOCKED, f"Task {task_id} failed {retries} times - needs human help")
                return LoopState.BLOCKED, f"max_retries_exceeded ({retries})"
        
        # Normal failure - can retry
        self.transition(LoopState.TASK_FAILURE, reason)
        return LoopState.TASK_FAILURE, "retry"
    
    def get_task_retry_count(self, task_id: str = None) -> int:
        """Get retry count for a task."""
        tid = task_id or self.current_task_id
        return self.task_retries.get(tid, 0) if tid else 0
    
    def reset_task_retries(self, task_id: str = None):
        """Reset retry count for a task (e.g., after success)."""
        tid = task_id or self.current_task_id
        if tid and tid in self.task_retries:
            self.task_retries[tid] = 0
    
    def to_dict(self) -> dict:
        """Serialize FSM state for persistence."""
        return {
            "current_state": self.current_state.value,
            "iteration": self.iteration,
            "consecutive_failures": self.consecutive_failures,
            "transitions": [
                {
                    "from": t.from_state.value,
                    "to": t.to_state.value,
                    "timestamp": t.timestamp,
                    "reason": t.reason,
                    "iteration": t.iteration,
                }
                for t in self.transitions[-10:]  # Keep last 10 for context economy
            ]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "FSMContext":
        """Restore FSM state from persistence."""
        ctx = cls(
            current_state=LoopState(data["current_state"]),
            iteration=data.get("iteration", 0),
            consecutive_failures=data.get("consecutive_failures", 0),
        )
        return ctx
    
    def to_mermaid(self) -> str:
        """
        Generate Mermaid diagram showing current position in FSM.
        This serves as both visualization AND compressed state summary.
        """
        lines = ["stateDiagram-v2"]
        
        # Add all states with current highlighted
        for state in LoopState:
            if state == self.current_state:
                lines.append(f"    {state.value}: {state.value.upper()} ⬅️ CURRENT")
            else:
                lines.append(f"    {state.value}: {state.value.upper()}")
        
        # Add transitions
        for from_state, to_states in VALID_TRANSITIONS.items():
            for to_state in to_states:
                lines.append(f"    {from_state.value} --> {to_state.value}")
        
        # Add notes for failure states
        lines.append("")
        lines.append("    note right of task_failure: Retryable\\n(tests failed)")
        lines.append("    note right of fatal_error: Terminal\\n(cannot recover)")
        
        return "\n".join(lines)
    
    def get_compact_summary(self) -> str:
        """
        Ultra-compact state summary for context economy.
        This replaces verbose history with minimal tokens.
        """
        return (
            f"[FSM] state={self.current_state.value} "
            f"iter={self.iteration} "
            f"fails={self.consecutive_failures} "
            f"valid_next={[s.value for s in self.get_valid_transitions()]}"
        )


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class LoopController:
    """
    High-level controller that wraps the FSM and provides
    the main loop execution interface.
    """
    
    def __init__(self, config: dict = None):
        self.fsm = FSMContext()
        self.config = config or {}
        self.hooks: Dict[LoopState, list] = {state: [] for state in LoopState}
        
        if "max_iterations" in self.config:
            self.fsm.max_iterations = self.config["max_iterations"]
        if "max_consecutive_failures" in self.config:
            self.fsm.max_consecutive_failures = self.config["max_consecutive_failures"]
    
    def register_hook(self, state: LoopState, callback: Callable):
        """Register a callback to run when entering a state."""
        self.hooks[state].append(callback)
    
    def _run_hooks(self, state: LoopState, context: dict):
        """Run all hooks for a state."""
        for hook in self.hooks[state]:
            hook(self.fsm, context)
    
    def step(self, to_state: LoopState, reason: str = "", context: dict = None) -> bool:
        """
        Execute a single state transition with hooks.
        
        This is the primary interface for agents to move through the loop.
        """
        context = context or {}
        
        # Validate and transition
        self.fsm.transition(to_state, reason, context)
        
        # Run hooks
        self._run_hooks(to_state, context)
        
        return True
    
    def get_next_valid_actions(self) -> list[str]:
        """
        Returns the list of valid next actions as strings.
        This constrains what the agent can do next.
        """
        return [state.value for state in self.fsm.get_valid_transitions()]
    
    def get_state_prompt_fragment(self) -> str:
        """
        Returns a minimal prompt fragment describing current state
        and valid actions. Designed for token economy.
        """
        return (
            f"CURRENT_STATE: {self.fsm.current_state.value}\n"
            f"VALID_ACTIONS: {self.get_next_valid_actions()}\n"
            f"ITERATION: {self.fsm.iteration}\n"
        )


# Convenience function for creating a new loop
def create_loop(config: dict = None) -> LoopController:
    """Factory function to create a new loop controller."""
    return LoopController(config)


if __name__ == "__main__":
    # Demo the FSM
    loop = create_loop({"max_iterations": 10})
    
    print("Initial state:", loop.fsm.current_state.value)
    print("Valid next:", loop.get_next_valid_actions())
    
    # Simulate a successful iteration
    loop.step(LoopState.PLAN, "Starting first task")
    loop.step(LoopState.EXECUTE, "Running task 1.1")
    loop.step(LoopState.OBSERVE, "Checking results")
    loop.step(LoopState.CRITIQUE, "Validating against spec")
    loop.step(LoopState.CHECKPOINT, "Task complete, committed")
    
    print("\nAfter one iteration:")
    print(loop.fsm.get_compact_summary())
    print("\nMermaid diagram:")
    print(loop.fsm.to_mermaid())
