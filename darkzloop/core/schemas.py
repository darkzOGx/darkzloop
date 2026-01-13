"""
darkzloop Schemas

Strict JSON schemas for internal communication between loop steps.
Using structured data instead of natural language is:
- 100% deterministic to parse
- Faster than parsing prose
- Validatable (fail fast on invalid output)

These schemas define the "fuel" that passes between FSM nodes.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
import json
from datetime import datetime


# =============================================================================
# Core Action Types
# =============================================================================

class ActionType(Enum):
    """Valid action types the agent can take."""
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    MODIFY_FILE = "modify_file"
    RUN_COMMAND = "run_command"
    SEARCH_CODE = "search_code"
    ASK_HUMAN = "ask_human"
    COMMIT = "commit"
    NO_OP = "no_op"


class TaskStatus(Enum):
    """Status of a task in the plan."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


# =============================================================================
# Input Schemas (Agent receives these)
# =============================================================================

@dataclass
class TaskDefinition:
    """
    A single task from the implementation plan.
    This is what the agent receives as input for EXECUTE state.
    """
    id: str
    description: str
    files_to_modify: List[str]
    files_to_create: List[str]
    reference_files: List[str]  # Pattern files to follow
    spec_sections: List[str]    # Which spec sections apply
    acceptance_criteria: str
    dependencies: List[str] = field(default_factory=list)  # Task IDs this depends on
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
    
    @classmethod
    def from_json(cls, data: str | dict) -> "TaskDefinition":
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)
    
    def to_prompt_fragment(self) -> str:
        """Minimal token representation for agent context."""
        return (
            f"TASK: {self.id}\n"
            f"DESC: {self.description}\n"
            f"MODIFY: {self.files_to_modify}\n"
            f"CREATE: {self.files_to_create}\n"
            f"PATTERNS: {self.reference_files}\n"
            f"ACCEPT: {self.acceptance_criteria}\n"
        )


@dataclass
class LoopInput:
    """
    Complete input for a single loop iteration.
    This is the structured "context" passed to the agent.
    """
    task: TaskDefinition
    fsm_state: str
    valid_actions: List[str]
    iteration: int
    history_summary: str  # Compressed summary, not full history
    goal_reminder: str    # Original objective for drift detection
    
    def to_json(self) -> str:
        return json.dumps({
            "task": asdict(self.task),
            "fsm_state": self.fsm_state,
            "valid_actions": self.valid_actions,
            "iteration": self.iteration,
            "history_summary": self.history_summary,
            "goal_reminder": self.goal_reminder,
        }, indent=2)


# =============================================================================
# Output Schemas (Agent produces these)
# =============================================================================

@dataclass
class AgentAction:
    """
    A single action the agent wants to take.
    Must be one of the valid ActionTypes.
    """
    action: str  # ActionType value
    target: str  # File path or command
    content: Optional[str] = None  # For write/modify
    reason: str = ""  # Why this action
    
    def validate(self) -> tuple[bool, str]:
        """Validate the action is well-formed."""
        try:
            ActionType(self.action)
        except ValueError:
            return False, f"Invalid action type: {self.action}"
        
        if not self.target:
            return False, "Action requires a target"
        
        if self.action in ["write_file", "modify_file"] and not self.content:
            return False, f"{self.action} requires content"
        
        return True, ""
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
    
    @classmethod
    def from_json(cls, data: str | dict) -> "AgentAction":
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)


@dataclass
class ExecutionResult:
    """
    Result of executing an action.
    This is produced by EXECUTE and consumed by OBSERVE.
    """
    action: AgentAction
    success: bool
    output: str
    error: Optional[str] = None
    duration_ms: int = 0
    
    def to_json(self) -> str:
        return json.dumps({
            "action": asdict(self.action),
            "success": self.success,
            "output": self.output[:500],  # Truncate for token economy
            "error": self.error,
            "duration_ms": self.duration_ms,
        }, indent=2)


@dataclass
class Observation:
    """
    Agent's observation after execution.
    Structured analysis of what happened.
    """
    execution_succeeded: bool
    tests_passed: bool
    files_changed: List[str]
    issues_found: List[str]
    next_step_suggestion: str
    confidence: float  # 0.0 to 1.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
    
    @classmethod
    def from_json(cls, data: str | dict) -> "Observation":
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)


@dataclass
class CritiqueResult:
    """
    Result of the CRITIQUE phase.
    Validates execution against spec and goal.
    """
    matches_spec: bool
    matches_goal: bool
    issues: List[str]
    should_retry: bool
    should_proceed: bool
    reasoning: str
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
    
    @classmethod  
    def from_json(cls, data: str | dict) -> "CritiqueResult":
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)


@dataclass
class CheckpointData:
    """
    Data saved at CHECKPOINT state.
    This becomes the compressed history for next iteration.
    """
    iteration: int
    task_id: str
    task_status: str  # TaskStatus value
    commit_hash: Optional[str]
    summary: str  # Human-readable summary
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


# =============================================================================
# Plan Schema (DAG Structure)
# =============================================================================

@dataclass
class PlanNode:
    """
    A node in the execution DAG.
    Contains task info and dependency edges.
    """
    task: TaskDefinition
    status: TaskStatus = TaskStatus.PENDING
    depends_on: List[str] = field(default_factory=list)  # Task IDs
    
    def is_ready(self, completed_tasks: set) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_tasks for dep in self.depends_on)


@dataclass
class ExecutionPlan:
    """
    The complete execution plan as a DAG.
    Enables parallel execution of independent tasks.
    """
    nodes: Dict[str, PlanNode]  # task_id -> PlanNode
    
    def get_ready_tasks(self, completed: set = None) -> List[str]:
        """
        Return task IDs that are ready to execute (all deps satisfied).
        These can be run in parallel.
        """
        completed = completed or set()
        ready = []
        
        for task_id, node in self.nodes.items():
            if node.status == TaskStatus.PENDING and node.is_ready(completed):
                ready.append(task_id)
        
        return ready
    
    def get_parallel_groups(self) -> List[List[str]]:
        """
        Compute execution order with parallel groups.
        Returns list of lists - each inner list can run in parallel.
        """
        completed = set()
        groups = []
        
        while True:
            ready = self.get_ready_tasks(completed)
            if not ready:
                break
            groups.append(ready)
            completed.update(ready)
        
        return groups
    
    def to_mermaid(self) -> str:
        """Generate Mermaid DAG diagram of the plan."""
        lines = ["graph TD"]
        
        for task_id, node in self.nodes.items():
            # Style based on status
            if node.status == TaskStatus.COMPLETE:
                lines.append(f"    {task_id}[✅ {task_id}]")
            elif node.status == TaskStatus.IN_PROGRESS:
                lines.append(f"    {task_id}[⏳ {task_id}]")
            elif node.status == TaskStatus.FAILED:
                lines.append(f"    {task_id}[❌ {task_id}]")
            else:
                lines.append(f"    {task_id}[{task_id}]")
            
            # Add edges
            for dep in node.depends_on:
                lines.append(f"    {dep} --> {task_id}")
        
        return "\n".join(lines)
    
    def to_json(self) -> str:
        return json.dumps({
            task_id: {
                "task": asdict(node.task),
                "status": node.status.value,
                "depends_on": node.depends_on,
            }
            for task_id, node in self.nodes.items()
        }, indent=2)


# =============================================================================
# Validation Helpers
# =============================================================================

def validate_agent_output(output: str, expected_schema: type) -> tuple[bool, Any, str]:
    """
    Validate that agent output matches expected schema.
    Returns (is_valid, parsed_object_or_None, error_message).
    
    Use this to hard-fail on invalid output before wasting tokens.
    """
    try:
        data = json.loads(output)
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON: {e}"
    
    try:
        obj = expected_schema.from_json(data)
        return True, obj, ""
    except (TypeError, KeyError) as e:
        return False, None, f"Schema validation failed: {e}"


def extract_json_from_response(response: str) -> Optional[str]:
    """
    Extract JSON from agent response that may contain other text.
    Looks for ```json blocks or raw JSON objects.
    """
    # Try to find ```json block
    import re
    json_block = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    if json_block:
        return json_block.group(1)
    
    # Try to find raw JSON object
    json_obj = re.search(r'\{.*\}', response, re.DOTALL)
    if json_obj:
        try:
            json.loads(json_obj.group(0))
            return json_obj.group(0)
        except json.JSONDecodeError:
            pass
    
    return None


# =============================================================================
# Token-Efficient Serialization
# =============================================================================

def compact_serialize(obj: Any) -> str:
    """
    Serialize to minimal JSON (no whitespace).
    Use for internal state passing where tokens matter.
    """
    if hasattr(obj, 'to_json'):
        return json.dumps(json.loads(obj.to_json()), separators=(',', ':'))
    return json.dumps(asdict(obj), separators=(',', ':'))


if __name__ == "__main__":
    # Demo schemas
    task = TaskDefinition(
        id="1.1",
        description="Create events table migration",
        files_to_modify=[],
        files_to_create=["migrations/005_events.sql"],
        reference_files=["migrations/003_sessions.sql"],
        spec_sections=["3.2"],
        acceptance_criteria="sqlx migrate run succeeds",
    )
    
    print("Task JSON:")
    print(task.to_json())
    
    print("\nTask prompt fragment:")
    print(task.to_prompt_fragment())
    
    print("\nCompact serialization:")
    print(compact_serialize(task))
    
    # Demo action validation
    action = AgentAction(
        action="write_file",
        target="migrations/005_events.sql",
        content="CREATE TABLE events...",
        reason="Creating migration per task 1.1"
    )
    
    valid, error = action.validate()
    print(f"\nAction valid: {valid}")
