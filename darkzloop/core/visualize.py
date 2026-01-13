"""
darkzloop Visualization (Dual-Mode)

Generates visual representations for TWO audiences:
1. For Humans: Pretty HTML/PNG with colored graphs
2. For Agents: Concise text representation for context injection

The agent-mode output is critical - if the agent sees the graph in its
context, it immediately understands dependencies and blockers.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
from datetime import datetime
from pathlib import Path
from enum import Enum
import json
import subprocess
import tempfile


class TaskState(Enum):
    """Visual state for tasks."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    """A task in the visual graph."""
    id: str
    description: str
    state: TaskState
    dependencies: List[str] = field(default_factory=list)
    error: Optional[str] = None
    commit_hash: Optional[str] = None


@dataclass
class LoopVisualization:
    """
    Complete visualization state.
    
    This is the single source of truth for rendering both
    human and agent views.
    """
    # FSM state
    fsm_state: str
    iteration: int
    consecutive_failures: int
    
    # Task DAG
    tasks: Dict[str, TaskNode] = field(default_factory=dict)
    
    # Execution order (for showing parallel groups)
    parallel_groups: List[List[str]] = field(default_factory=list)
    
    # Timing
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    # Summary stats
    @property
    def completed_count(self) -> int:
        return sum(1 for t in self.tasks.values() if t.state == TaskState.COMPLETE)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for t in self.tasks.values() if t.state == TaskState.FAILED)
    
    @property
    def pending_count(self) -> int:
        return sum(1 for t in self.tasks.values() if t.state in [TaskState.PENDING, TaskState.READY])
    
    @property
    def blocked_count(self) -> int:
        return sum(1 for t in self.tasks.values() if t.state == TaskState.BLOCKED)


# =============================================================================
# AGENT-MODE OUTPUT (For injection into context window)
# =============================================================================

def render_for_agent(viz: LoopVisualization) -> str:
    """
    Render visualization as concise text for agent context.
    
    This goes into the HISTORY block. The agent sees this and
    immediately understands the state of play.
    
    Format is optimized for:
    - Minimal tokens
    - Clear dependency relationships
    - Actionable blockers
    """
    lines = []
    
    # Header with FSM state
    lines.append(f"[LOOP] state={viz.fsm_state} iter={viz.iteration} fails={viz.consecutive_failures}")
    lines.append(f"[STATS] ✓{viz.completed_count} ✗{viz.failed_count} ◷{viz.pending_count} ⊘{viz.blocked_count}")
    
    # Mermaid-style DAG (text version)
    lines.append("[DAG]")
    
    for task_id, task in viz.tasks.items():
        # State indicator
        if task.state == TaskState.COMPLETE:
            indicator = "✓"
        elif task.state == TaskState.FAILED:
            indicator = "✗"
        elif task.state == TaskState.RUNNING:
            indicator = "►"
        elif task.state == TaskState.BLOCKED:
            indicator = "⊘"
        elif task.state == TaskState.READY:
            indicator = "○"
        else:
            indicator = "◷"
        
        # Build dependency arrows
        if task.dependencies:
            deps = ",".join(task.dependencies)
            lines.append(f"  [{deps}] --> [{indicator}{task_id}]")
        else:
            lines.append(f"  [] --> [{indicator}{task_id}]")
        
        # Add error info for failed tasks
        if task.state == TaskState.FAILED and task.error:
            lines.append(f"    └─ ERROR: {task.error[:50]}")
    
    # Blockers section (critical for agent decision-making)
    blockers = [t for t in viz.tasks.values() if t.state == TaskState.BLOCKED]
    if blockers:
        lines.append("[BLOCKED]")
        for task in blockers:
            failed_deps = [d for d in task.dependencies 
                          if viz.tasks.get(d, TaskNode(d, "", TaskState.PENDING)).state == TaskState.FAILED]
            if failed_deps:
                lines.append(f"  {task.id}: waiting on failed {failed_deps}")
    
    # Next actionable tasks
    ready = [t.id for t in viz.tasks.values() if t.state == TaskState.READY]
    if ready:
        lines.append(f"[READY] {ready}")
    
    return "\n".join(lines)


def render_dag_for_agent(viz: LoopVisualization) -> str:
    """
    Render just the DAG in Mermaid text format.
    
    The agent can parse this to understand the dependency graph.
    """
    lines = ["graph TD"]
    
    for task_id, task in viz.tasks.items():
        node_id = task_id.replace(".", "_")
        
        # State suffix
        if task.state == TaskState.COMPLETE:
            lines.append(f"    {node_id}[{task_id} ✓]")
        elif task.state == TaskState.FAILED:
            lines.append(f"    {node_id}[{task_id} ✗]")
        elif task.state == TaskState.RUNNING:
            lines.append(f"    {node_id}[{task_id} ►]")
        else:
            lines.append(f"    {node_id}[{task_id}]")
        
        # Dependencies
        for dep in task.dependencies:
            dep_id = dep.replace(".", "_")
            dep_task = viz.tasks.get(dep)
            
            # Style the edge based on dependency state
            if dep_task and dep_task.state == TaskState.FAILED:
                lines.append(f"    {dep_id} -.->|blocked| {node_id}")
            elif dep_task and dep_task.state == TaskState.COMPLETE:
                lines.append(f"    {dep_id} -->|done| {node_id}")
            else:
                lines.append(f"    {dep_id} --> {node_id}")
    
    return "\n".join(lines)


# =============================================================================
# HUMAN-MODE OUTPUT (Pretty visualizations)
# =============================================================================

def render_mermaid_flowchart(viz: LoopVisualization) -> str:
    """Render full Mermaid flowchart with styling."""
    lines = ["flowchart TD", ""]
    
    # Render all tasks
    for task_id, task in viz.tasks.items():
        node_id = task_id.replace(".", "_")
        label = f"{task_id}"
        lines.append(f"    {node_id}[\"{label}\"]")
    
    lines.append("")
    
    # Add edges
    for task_id, task in viz.tasks.items():
        node_id = task_id.replace(".", "_")
        for dep in task.dependencies:
            dep_id = dep.replace(".", "_")
            lines.append(f"    {dep_id} --> {node_id}")
    
    lines.append("")
    
    # Add styles based on state
    complete_nodes = [t.id.replace(".", "_") for t in viz.tasks.values() if t.state == TaskState.COMPLETE]
    failed_nodes = [t.id.replace(".", "_") for t in viz.tasks.values() if t.state == TaskState.FAILED]
    running_nodes = [t.id.replace(".", "_") for t in viz.tasks.values() if t.state == TaskState.RUNNING]
    blocked_nodes = [t.id.replace(".", "_") for t in viz.tasks.values() if t.state == TaskState.BLOCKED]
    
    lines.append("    classDef complete fill:#90EE90,stroke:#228B22,stroke-width:2px")
    lines.append("    classDef failed fill:#FF6B6B,stroke:#DC143C,stroke-width:2px")
    lines.append("    classDef running fill:#FFD700,stroke:#FFA500,stroke-width:3px")
    lines.append("    classDef blocked fill:#D3D3D3,stroke:#808080,stroke-width:2px,stroke-dasharray: 5 5")
    lines.append("    classDef pending fill:#E8E8E8,stroke:#888888")
    
    if complete_nodes:
        lines.append(f"    class {','.join(complete_nodes)} complete")
    if failed_nodes:
        lines.append(f"    class {','.join(failed_nodes)} failed")
    if running_nodes:
        lines.append(f"    class {','.join(running_nodes)} running")
    if blocked_nodes:
        lines.append(f"    class {','.join(blocked_nodes)} blocked")
    
    return "\n".join(lines)


def render_fsm_diagram(viz: LoopVisualization) -> str:
    """Render FSM state diagram showing current position."""
    current = viz.fsm_state
    
    lines = ["stateDiagram-v2", "    direction LR", ""]
    
    states = [
        ("init", "INIT"),
        ("plan", "PLAN"),
        ("execute", "EXECUTE"),
        ("observe", "OBSERVE"),
        ("critique", "CRITIQUE"),
        ("checkpoint", "CHECKPOINT"),
        ("complete", "COMPLETE"),
        ("task_failure", "RETRY"),
        ("fatal_error", "FATAL"),
    ]
    
    for state_id, label in states:
        if state_id == current:
            lines.append(f"    {state_id}: 🔵 {label}")
        else:
            lines.append(f"    {state_id}: {label}")
    
    # Transitions
    transitions = [
        ("init", "plan"),
        ("plan", "execute"),
        ("plan", "fatal_error"),
        ("execute", "observe"),
        ("execute", "task_failure"),
        ("execute", "fatal_error"),
        ("observe", "critique"),
        ("critique", "checkpoint"),
        ("critique", "execute"),
        ("critique", "task_failure"),
        ("checkpoint", "plan"),
        ("checkpoint", "complete"),
        ("task_failure", "plan"),
        ("task_failure", "fatal_error"),
    ]
    
    for from_state, to_state in transitions:
        lines.append(f"    {from_state} --> {to_state}")
    
    return "\n".join(lines)


def render_html(viz: LoopVisualization, include_agent_view: bool = True) -> str:
    """Generate standalone HTML with live Mermaid rendering."""
    flowchart = render_mermaid_flowchart(viz)
    fsm = render_fsm_diagram(viz)
    agent_text = render_for_agent(viz) if include_agent_view else ""
    
    total = len(viz.tasks)
    progress = (viz.completed_count / total * 100) if total > 0 else 0
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Darkzloop Status - Iteration {viz.iteration}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        :root {{ --success: #90EE90; --failure: #FF6B6B; --running: #FFD700; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
               color: #eee; min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ font-size: 2rem; margin-bottom: 10px; }}
        .subtitle {{ color: #888; margin-bottom: 30px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: rgba(255,255,255,0.1); border-radius: 12px; padding: 20px; text-align: center; }}
        .stat-card.complete {{ border-left: 4px solid var(--success); }}
        .stat-card.failed {{ border-left: 4px solid var(--failure); }}
        .stat-card.running {{ border-left: 4px solid var(--running); }}
        .stat-value {{ font-size: 2.5rem; font-weight: bold; }}
        .stat-label {{ color: #888; font-size: 0.9rem; margin-top: 5px; }}
        .progress-bar {{ background: rgba(255,255,255,0.1); border-radius: 10px; height: 20px; margin-bottom: 30px; overflow: hidden; }}
        .progress-fill {{ background: linear-gradient(90deg, var(--success), #32CD32); height: 100%; }}
        .card {{ background: rgba(255,255,255,0.05); border-radius: 16px; padding: 25px; margin-bottom: 20px; }}
        .card h2 {{ font-size: 1.2rem; margin-bottom: 20px; color: #aaa; }}
        .mermaid {{ background: white; border-radius: 12px; padding: 20px; }}
        .agent-view {{ background: #0d1117; border-radius: 8px; padding: 15px;
                      font-family: monospace; font-size: 0.85rem; white-space: pre-wrap; color: #58a6ff; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔄 Darkzloop Status</h1>
        <p class="subtitle">Iteration {viz.iteration} • State: <strong>{viz.fsm_state.upper()}</strong></p>
        
        <div class="stats-grid">
            <div class="stat-card complete"><div class="stat-value">{viz.completed_count}</div><div class="stat-label">Completed</div></div>
            <div class="stat-card failed"><div class="stat-value">{viz.failed_count}</div><div class="stat-label">Failed</div></div>
            <div class="stat-card running"><div class="stat-value">{viz.iteration}</div><div class="stat-label">Iterations</div></div>
            <div class="stat-card"><div class="stat-value">{viz.pending_count}</div><div class="stat-label">Pending</div></div>
        </div>
        
        <div class="progress-bar"><div class="progress-fill" style="width: {progress:.0f}%"></div></div>
        
        <div class="card"><h2>📊 Task DAG</h2><div class="mermaid">{flowchart}</div></div>
        <div class="card"><h2>🔀 State Machine</h2><div class="mermaid">{fsm}</div></div>
        {"<div class='card'><h2>🤖 Agent View</h2><div class='agent-view'>" + agent_text + "</div></div>" if include_agent_view else ""}
    </div>
    <script>mermaid.initialize({{ startOnLoad: true, theme: 'default' }});</script>
</body>
</html>'''


def render_ascii(viz: LoopVisualization) -> str:
    """Render ASCII visualization for terminal."""
    lines = [
        "╔══════════════════════════════════════════════════════════════════╗",
        "║                      DARKZLOOP STATUS                            ║",
        "╠══════════════════════════════════════════════════════════════════╣",
    ]
    
    stats = f"║  Iteration: {viz.iteration:<4}  State: {viz.fsm_state:<12}  Fails: {viz.consecutive_failures:<3}"
    lines.append(stats.ljust(67) + "║")
    
    total = len(viz.tasks)
    if total > 0:
        pct = viz.completed_count / total
        bar_width = 40
        filled = int(bar_width * pct)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"║  [{bar}] {pct*100:>3.0f}%".ljust(67) + "║")
    
    lines.append("╠══════════════════════════════════════════════════════════════════╣")
    lines.append("║  TASKS                                                           ║")
    lines.append("╠══════════════════════════════════════════════════════════════════╣")
    
    for task_id, task in viz.tasks.items():
        icon = {"complete": "✅", "failed": "❌", "running": "⏳", "blocked": "🚫"}.get(task.state.value, "⏸ ")
        desc = task.description[:45] if task.description else ""
        lines.append(f"║  {icon} {task_id:<6} {desc}".ljust(67) + "║")
        if task.state == TaskState.FAILED and task.error:
            lines.append(f"║      └─ {task.error[:50]}".ljust(67) + "║")
    
    lines.append("╠══════════════════════════════════════════════════════════════════╣")
    lines.append(f"║  ✅ {viz.completed_count} complete  ❌ {viz.failed_count} failed  ⏸ {viz.pending_count} pending  🚫 {viz.blocked_count} blocked".ljust(67) + "║")
    lines.append("╚══════════════════════════════════════════════════════════════════╝")
    
    return "\n".join(lines)


# =============================================================================
# VISUALIZATION MANAGER
# =============================================================================

class Visualizer:
    """Main visualizer class with state persistence."""
    
    def __init__(self, project_path: Path = None):
        self.project_path = project_path or Path.cwd()
        self.state_file = self.project_path / ".darkzloop" / "viz_state.json"
        self.viz: Optional[LoopVisualization] = None
    
    def initialize(self, tasks: List[dict], parallel_groups: List[List[str]] = None):
        """Initialize with tasks from plan."""
        self.viz = LoopVisualization(
            fsm_state="init", iteration=0, consecutive_failures=0,
            parallel_groups=parallel_groups or [],
            started_at=datetime.now().isoformat(),
        )
        for task in tasks:
            self.viz.tasks[task["id"]] = TaskNode(
                id=task["id"], description=task.get("description", ""),
                state=TaskState.PENDING, dependencies=task.get("dependencies", []),
            )
        self._compute_ready_tasks()
        self.save()
    
    def _compute_ready_tasks(self):
        """Update READY state for tasks with satisfied dependencies."""
        if not self.viz:
            return
        completed = {t.id for t in self.viz.tasks.values() if t.state == TaskState.COMPLETE}
        failed = {t.id for t in self.viz.tasks.values() if t.state == TaskState.FAILED}
        
        for task in self.viz.tasks.values():
            if task.state != TaskState.PENDING:
                continue
            if any(d in failed for d in task.dependencies):
                task.state = TaskState.BLOCKED
            elif all(d in completed for d in task.dependencies):
                task.state = TaskState.READY
    
    def update_fsm(self, state: str, iteration: int, consecutive_failures: int):
        """Update FSM state."""
        if self.viz:
            self.viz.fsm_state = state
            self.viz.iteration = iteration
            self.viz.consecutive_failures = consecutive_failures
            self.viz.updated_at = datetime.now().isoformat()
            self.save()
    
    def update_task(self, task_id: str, state: TaskState, error: str = None, commit_hash: str = None):
        """Update task state."""
        if self.viz and task_id in self.viz.tasks:
            self.viz.tasks[task_id].state = state
            self.viz.tasks[task_id].error = error
            self.viz.tasks[task_id].commit_hash = commit_hash
            self._compute_ready_tasks()
            self.save()
    
    def get_agent_context(self) -> str:
        """Get visualization for agent context injection."""
        return render_for_agent(self.viz) if self.viz else "[LOOP] No state"
    
    def get_human_view(self, format: str = "ascii") -> str:
        """Get visualization for human viewing."""
        if not self.viz:
            return "No state. Run `darkzloop run` first."
        if format == "ascii":
            return render_ascii(self.viz)
        elif format == "mermaid":
            return render_mermaid_flowchart(self.viz)
        elif format == "html":
            return render_html(self.viz)
        return render_ascii(self.viz)
    
    def save(self):
        """Save state."""
        if not self.viz:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "fsm_state": self.viz.fsm_state,
            "iteration": self.viz.iteration,
            "consecutive_failures": self.viz.consecutive_failures,
            "parallel_groups": self.viz.parallel_groups,
            "started_at": self.viz.started_at,
            "updated_at": self.viz.updated_at,
            "tasks": {tid: {"id": t.id, "description": t.description, "state": t.state.value,
                          "dependencies": t.dependencies, "error": t.error, "commit_hash": t.commit_hash}
                     for tid, t in self.viz.tasks.items()}
        }
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self) -> bool:
        """Load state."""
        if not self.state_file.exists():
            return False
        with open(self.state_file) as f:
            data = json.load(f)
        self.viz = LoopVisualization(
            fsm_state=data["fsm_state"], iteration=data["iteration"],
            consecutive_failures=data["consecutive_failures"],
            parallel_groups=data.get("parallel_groups", []),
        )
        for tid, td in data.get("tasks", {}).items():
            self.viz.tasks[tid] = TaskNode(
                id=td["id"], description=td["description"], state=TaskState(td["state"]),
                dependencies=td["dependencies"], error=td.get("error"), commit_hash=td.get("commit_hash"),
            )
        return True


if __name__ == "__main__":
    viz = LoopVisualization(fsm_state="execute", iteration=5, consecutive_failures=0)
    viz.tasks = {
        "1.1": TaskNode("1.1", "Create migration", TaskState.COMPLETE, []),
        "1.2": TaskNode("1.2", "Create model", TaskState.COMPLETE, []),
        "2.1": TaskNode("2.1", "Create handler", TaskState.RUNNING, ["1.1", "1.2"]),
        "2.2": TaskNode("2.2", "Add route", TaskState.PENDING, ["2.1"]),
        "3.1": TaskNode("3.1", "Add tests", TaskState.PENDING, ["2.1", "2.2"]),
    }
    
    print("=== AGENT VIEW ===")
    print(render_for_agent(viz))
    print("\n=== ASCII VIEW ===")
    print(render_ascii(viz))
