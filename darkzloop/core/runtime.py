"""
darkzloop Runtime v2

The main execution engine that orchestrates all components:
- FSM for state control (with per-task circuit breakers)
- Context for token management
- Manifest for read-before-write enforcement
- Critic for validation
- DAG for parallel execution
- Visualizer for dual-mode output
- Tiered gates for quality enforcement

This is the "locomotive" that runs the loop.
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List, Tuple
from pathlib import Path
import json
import time
import subprocess
import asyncio
from datetime import datetime

from .fsm import LoopState, FSMContext, LoopController, create_loop, InvalidTransitionError
from .schemas import (
    TaskDefinition, AgentAction, ExecutionResult, 
    Observation, CritiqueResult, CheckpointData,
    validate_agent_output, extract_json_from_response
)
from .context import ContextManager, create_iteration_summary
from .critic import Critic, CritiqueVerdict, quick_critique
from .dag import DAGExecutor, parse_plan_to_dag, run_shell_command_async, run_shell_command_sync
from .manifest import ContextManifest, ManifestEnforcer
from .locks import FileAwareDAGScheduler, FileLockManager
from .visualize import Visualizer, TaskState, render_for_agent
from .semantic import SemanticExpander, create_expander


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class GateConfig:
    """Configuration for a single quality gate."""
    name: str
    command: str
    tier: int  # 1=essential, 2=quality, 3=safety
    auto_fix_command: Optional[str] = None
    on_failure: str = "task_failure"  # task_failure, warning, blocked, fatal_error

@dataclass
class LoopConfig:
    """Configuration for a darkzloop run."""
    spec_path: Path
    plan_path: Path
    project_root: Path
    
    # Execution settings
    max_iterations: int = 100
    max_consecutive_failures: int = 3
    max_task_retries: int = 3
    stop_on_failure: bool = True
    
    # Tiered quality gates
    gates: List[GateConfig] = field(default_factory=list)
    
    # Token management
    max_context_tokens: int = 4000
    max_summaries: int = 10
    
    # Parallelism
    enable_parallel: bool = False
    max_parallel_tasks: int = 4
    respect_file_locks: bool = True
    
    # Manifest settings
    enforce_read_before_write: bool = True
    require_pattern_read: bool = True
    
    # Critic settings
    enable_critic: bool = True
    use_llm_critic: bool = False
    
    # Visualization
    auto_update_viz: bool = True
    viz_format: str = "html"
    
    @classmethod
    def from_file(cls, config_path: Path) -> "LoopConfig":
        """Load config from darkzloop.json."""
        with open(config_path) as f:
            data = json.load(f)
        
        # Parse tiered gates
        gates = []
        gates_config = data.get("gates", {})
        
        for tier_num, tier_key in [(1, "tier1"), (2, "tier2"), (3, "tier3")]:
            tier_config = gates_config.get(tier_key, {})
            if tier_config.get("enabled", False):
                commands = tier_config.get("commands", [])
                auto_fixes = tier_config.get("auto_fix_commands", [])
                on_failure = tier_config.get("on_failure", "task_failure")
                
                for i, cmd in enumerate(commands):
                    auto_fix = auto_fixes[i] if i < len(auto_fixes) else None
                    gates.append(GateConfig(
                        name=f"tier{tier_num}_{i}",
                        command=cmd,
                        tier=tier_num,
                        auto_fix_command=auto_fix,
                        on_failure=on_failure,
                    ))
        
        # Fallback to legacy gates
        if not gates:
            legacy = gates_config
            if legacy.get("require_tests"):
                cmd = data.get("commands", {}).get("test", "")
                if cmd:
                    gates.append(GateConfig("test", cmd, 1))
            if legacy.get("require_format"):
                cmd = data.get("commands", {}).get("format_check", "")
                fix = data.get("commands", {}).get("format_fix", "")
                if cmd:
                    gates.append(GateConfig("format", cmd, 2, fix if legacy.get("auto_fix_format") else None))
            if legacy.get("require_lint"):
                cmd = data.get("commands", {}).get("lint", "")
                if cmd:
                    gates.append(GateConfig("lint", cmd, 2))
        
        return cls(
            spec_path=Path(data.get("paths", {}).get("spec", "DARKZLOOP_SPEC.md")),
            plan_path=Path(data.get("paths", {}).get("plan", "DARKZLOOP_PLAN.md")),
            project_root=config_path.parent,
            max_iterations=data.get("loop", {}).get("max_iterations", 100),
            max_consecutive_failures=data.get("loop", {}).get("max_consecutive_failures", 3),
            max_task_retries=data.get("loop", {}).get("max_task_retries", 3),
            gates=gates,
            enable_parallel=data.get("parallel", {}).get("enabled", False),
            max_parallel_tasks=data.get("parallel", {}).get("max_parallel_tasks", 4),
            respect_file_locks=data.get("parallel", {}).get("respect_file_locks", True),
            enforce_read_before_write=data.get("manifest", {}).get("enforce_read_before_write", True),
            require_pattern_read=data.get("manifest", {}).get("require_pattern_read", True),
            max_context_tokens=data.get("context", {}).get("max_tokens", 4000),
            max_summaries=data.get("context", {}).get("max_summaries", 10),
        )


@dataclass
class IterationResult:
    """Result of a single loop iteration."""
    iteration: int
    task_id: str
    success: bool
    state_path: List[str]
    files_changed: List[str]
    commit_hash: Optional[str]
    duration_ms: int
    critique_verdict: Optional[str] = None
    gates_passed: List[str] = field(default_factory=list)
    gates_failed: List[str] = field(default_factory=list)
    retry_count: int = 0
    error: Optional[str] = None
    hints: List[str] = field(default_factory=list)


# =============================================================================
# Runtime Engine
# =============================================================================

class DarkzloopRuntime:
    """
    The main runtime for executing darkzloop.
    
    Coordinates all components:
    - FSM (control flow with circuit breakers)
    - Context (token economy)
    - Manifest (read-before-write)
    - Critic (validation)
    - DAG (parallelism with file locking)
    - Visualizer (dual-mode output)
    - Gates (tiered quality enforcement)
    """
    
    def __init__(self, config: LoopConfig):
        self.config = config
        
        # Core FSM with circuit breaker settings
        self.loop = create_loop({
            "max_iterations": config.max_iterations,
            "max_consecutive_failures": config.max_consecutive_failures,
        })
        self.loop.fsm.max_task_retries = config.max_task_retries
        
        # Context manager
        self.context = ContextManager({
            "max_summaries": config.max_summaries,
            "target_tokens": config.max_context_tokens,
        })
        
        # Manifest enforcer
        self.manifest_enforcer = ManifestEnforcer(config.project_root)
        
        # Semantic expander (vocabulary gap bridging)
        self.semantic_expander = SemanticExpander(config.project_root)
        
        # Visualizer
        self.visualizer = Visualizer(config.project_root)
        
        # Optional components
        self.critic: Optional[Critic] = None
        self.dag: Optional[DAGExecutor] = None
        self.scheduler: Optional[FileAwareDAGScheduler] = None
        self.lock_manager: Optional[FileLockManager] = None
        
        # Agent executor (set by user)
        self.agent_executor: Optional[Callable] = None
        
        # State
        self.current_task: Optional[TaskDefinition] = None
        self.current_manifest: Optional[ContextManifest] = None
        self.iteration_results: List[IterationResult] = []
        self.hints: List[str] = []  # Hints to inject into next prompt
        
        # Load documents
        self._load_documents()
    
    def _load_documents(self):
        """Load spec and plan, initialize components."""
        spec_path = self.config.project_root / self.config.spec_path
        plan_path = self.config.project_root / self.config.plan_path
        
        # Load spec
        if spec_path.exists():
            self.spec_content = spec_path.read_text()
            goal = self._extract_goal(self.spec_content)
            self.context.initialize(goal, self.spec_content[:2000])
            
            if self.config.enable_critic:
                self.critic = Critic(goal)
        else:
            self.spec_content = ""
            self.context.initialize("Complete tasks", "")
        
        # Load plan and build DAG
        if plan_path.exists():
            plan_content = plan_path.read_text()
            self.dag = parse_plan_to_dag(plan_content)
            
            # Initialize visualizer
            tasks = [
                {"id": node.id, "description": node.task_data.get("description", ""),
                 "dependencies": node.dependencies}
                for node in self.dag.nodes.values()
            ]
            groups = self.dag.compute_execution_order() if self.config.enable_parallel else []
            self.visualizer.initialize(tasks, groups)
            
            # Set up file-aware scheduler if parallel
            if self.config.enable_parallel and self.config.respect_file_locks:
                self.scheduler = FileAwareDAGScheduler()
                self.lock_manager = FileLockManager()
                for node in self.dag.nodes.values():
                    self.scheduler.register_task(node.task_data)
    
    def _extract_goal(self, spec_content: str) -> str:
        """Extract goal from spec content."""
        if "## Objective" in spec_content:
            parts = spec_content.split("## Objective")
            if len(parts) > 1:
                return parts[1].split("##")[0].strip()[:500]
        return "Complete tasks in plan"
    
    def set_agent_executor(
        self,
        executor: Callable[[str, dict], Tuple[bool, str, str]]
    ):
        """Set the agent executor function."""
        self.agent_executor = executor
    
    # =========================================================================
    # System Prompt Generation
    # =========================================================================
    
    def render_system_prompt(self, task: TaskDefinition) -> str:
        """
        Render the dynamic system prompt for the agent.
        
        This exposes FSM state, manifest constraints, and circuit breaker
        status so the agent can make informed decisions.
        """
        try:
            from jinja2 import Template
            template_path = Path(__file__).parent.parent / "templates" / "prompts" / "system.j2"
            if template_path.exists():
                template = Template(template_path.read_text())
            else:
                # Fallback to inline template
                template = Template(self._get_fallback_template())
        except ImportError:
            # No Jinja2, use simple string formatting
            return self._render_simple_prompt(task)
        
        # Gather template variables
        files_in_context = list(self.current_manifest.files_in_context) if self.current_manifest else []
        files_must_read = list(self.current_manifest.get_unread_required()) if self.current_manifest else []
        
        active_gates = [
            {
                "name": g.name,
                "command": g.command,
                "tier": g.tier,
                "auto_fix": g.auto_fix_command,
            }
            for g in self.config.gates
        ]
        
        # Generate semantic expansion for task keywords
        semantic_expansion = {}
        task_terms = self._extract_task_terms(task)
        for term in task_terms[:10]:  # Limit to prevent token bloat
            expansion = self.semantic_expander.expand(term, include_codebase=True)
            # Get top 5 synonyms (excluding the term itself)
            top_synonyms = [t for t, c in sorted(expansion.items(), key=lambda x: -x[1]) 
                          if t != term][:5]
            if top_synonyms:
                semantic_expansion[term] = top_synonyms
        
        # Sanitize dag_status for Windows before rendering
        dag_status = self._sanitize_for_platform(self.visualizer.get_agent_context())

        rendered = template.render(
            fsm_state=self.loop.fsm.current_state.value,
            iteration=self.loop.fsm.iteration,
            files_in_context=files_in_context,
            files_must_read=files_must_read,
            current_task={
                "id": task.id,
                "description": task.description,
                "files_to_modify": task.files_to_modify,
                "files_to_create": task.files_to_create,
                "reference_files": task.reference_files,
                "acceptance_criteria": task.acceptance_criteria,
                "spec_sections": task.spec_sections,
            },
            task_retries=self.loop.fsm.get_task_retry_count(task.id),
            max_retries=self.config.max_task_retries,
            consecutive_failures=self.loop.fsm.consecutive_failures,
            max_consecutive_failures=self.config.max_consecutive_failures,
            active_gates=active_gates,
            dag_status=dag_status,
            hints=self.hints,
            semantic_expansion=semantic_expansion,
        )
        # Sanitize emojis for Windows compatibility
        return self._sanitize_for_platform(rendered)

    def _sanitize_for_platform(self, text: str) -> str:
        """Replace problematic Unicode characters for Windows compatibility."""
        import sys
        if sys.platform != "win32":
            return text
        # Replace common emojis and Unicode symbols with ASCII equivalents
        replacements = {
            '✓': '[+]',
            '✗': '[x]',
            '⚠️': '[!]',
            '⚠': '[!]',
            'ℹ️': '[i]',
            'ℹ': '[i]',
            '→': '->',
            '═': '=',
            '🔄': '[~]',
            '📦': '[=]',
            '🚀': '[>]',
            '💡': '[*]',
            '🔧': '[%]',
            '►': '[>]',
            '⊘': '[0]',
            '○': '[ ]',
            '◷': '[.]',
            '└': '`-',
            '─': '-',
        }
        for emoji, replacement in replacements.items():
            text = text.replace(emoji, replacement)
        return text

    def _extract_task_terms(self, task: TaskDefinition) -> List[str]:
        """Extract key terms from a task for semantic expansion."""
        import re
        terms = set()
        
        # From description
        words = re.findall(r'\b[a-z]{3,}\b', task.description.lower())
        terms.update(words)
        
        # From file paths
        for path in task.files_to_modify + task.files_to_create + task.reference_files:
            parts = re.split(r'[_\-./]', Path(path).stem.lower())
            terms.update(p for p in parts if len(p) > 2)
        
        # Filter out common stop words
        stop_words = {'the', 'and', 'for', 'with', 'from', 'this', 'that', 'file', 'create', 'add', 'new'}
        terms = terms - stop_words
        
        return list(terms)
    
    def _get_fallback_template(self) -> str:
        """Fallback template if file not found."""
        return """
You are Darkzloop, an autonomous software engineer.
Current state: {{ fsm_state | upper }} (iteration {{ iteration }})

## MANIFEST
Files in context: {{ files_in_context | length }}
Must read before writing: {{ files_must_read }}

## CIRCUIT BREAKER
Task retries: {{ task_retries }} / {{ max_retries }}
{% if task_retries >= max_retries - 1 %}
⚠️ WARNING: ONE attempt remaining!
{% endif %}

## CURRENT TASK
{{ current_task.id }}: {{ current_task.description }}

## DAG STATUS
{{ dag_status }}

{% for hint in hints %}
{{ hint }}
{% endfor %}
"""
    
    def _render_simple_prompt(self, task: TaskDefinition) -> str:
        """Simple prompt without Jinja2."""
        lines = [
            f"You are Darkzloop. State: {self.loop.fsm.current_state.value.upper()}",
            f"Iteration: {self.loop.fsm.iteration}",
            "",
            f"Task: {task.id} - {task.description}",
            "",
            "DAG Status:",
            self.visualizer.get_agent_context(),
        ]
        
        if self.hints:
            lines.append("")
            lines.append("HINTS:")
            lines.extend(self.hints)
        
        return "\n".join(lines)
    
    # =========================================================================
    # Quality Gates
    # =========================================================================
    
    def _run_tiered_gates(self) -> Tuple[bool, List[str], List[str], str]:
        """
        Run tiered quality gates.
        
        Returns: (all_passed, passed_gates, failed_gates, error_message)
        """
        passed = []
        failed = []
        
        for gate in sorted(self.config.gates, key=lambda g: g.tier):
            success, stdout, stderr = run_shell_command_sync(
                gate.command,
                cwd=str(self.config.project_root),
                timeout=300
            )
            
            if success:
                passed.append(gate.name)
            else:
                # Try auto-fix for Tier 2
                if gate.auto_fix_command and gate.tier == 2:
                    fix_success, _, _ = run_shell_command_sync(
                        gate.auto_fix_command,
                        cwd=str(self.config.project_root),
                        timeout=60
                    )
                    if fix_success:
                        # Re-run check
                        retry_success, _, _ = run_shell_command_sync(
                            gate.command,
                            cwd=str(self.config.project_root),
                            timeout=300
                        )
                        if retry_success:
                            passed.append(f"{gate.name} (auto-fixed)")
                            continue
                
                failed.append(gate.name)
                
                # Check failure action
                if gate.on_failure == "fatal_error" and gate.tier == 1:
                    return False, passed, failed, f"Tier 1 gate failed: {gate.name}\n{stderr[:200]}"
                elif gate.on_failure == "blocked" and gate.tier == 3:
                    return False, passed, failed, f"Safety gate failed: {gate.name} - needs human review"
        
        all_passed = len(failed) == 0
        error_msg = f"Gates failed: {', '.join(failed)}" if failed else ""
        
        return all_passed, passed, failed, error_msg
    
    # =========================================================================
    # Main Iteration Loop
    # =========================================================================
    
    def run_iteration(self, task: TaskDefinition) -> IterationResult:
        """Run a single iteration of the loop."""
        iteration_start = time.time()
        self.current_task = task
        state_path = []
        self.hints = []  # Clear hints from previous iteration
        
        # Initialize manifest for this task
        if self.config.enforce_read_before_write:
            task_dict = {
                "files_to_modify": task.files_to_modify,
                "files_to_create": task.files_to_create,
                "reference_files": task.reference_files,
            }
            self.current_manifest = ContextManifest.from_task(task_dict)
            self.manifest_enforcer.start_task(task.id, task_dict)
        
        # Start task in FSM (enables per-task retry tracking)
        self.loop.fsm.start_task(task.id)
        retry_count = self.loop.fsm.get_task_retry_count(task.id)
        
        # Update visualizer
        self.visualizer.update_task(task.id, TaskState.RUNNING)
        self.visualizer.update_fsm(
            self.loop.fsm.current_state.value,
            self.loop.fsm.iteration,
            self.loop.fsm.consecutive_failures
        )
        
        try:
            # PLAN state
            self.loop.step(LoopState.PLAN, f"Starting task {task.id}")
            state_path.append("plan")
            
            # Get context with system prompt
            system_prompt = self.render_system_prompt(task)
            context = self.context.get_context_for_agent(
                self.loop.fsm.get_compact_summary(),
                task.to_json() if hasattr(task, 'to_json') else json.dumps(task.__dict__)
            )
            full_context = f"{system_prompt}\n\n{context}"
            
            # EXECUTE state
            self.loop.step(LoopState.EXECUTE, "Running agent")
            state_path.append("execute")
            
            if not self.agent_executor:
                raise RuntimeError("No agent executor set")
            
            success, output, error = self.agent_executor(full_context, task.__dict__)
            
            self.context.record_step(
                state="EXECUTE",
                input_summary=f"Task: {task.description[:50]}",
                output_summary=output[:100] if output else "No output",
                files_touched=task.files_to_modify + task.files_to_create
            )
            
            if not success:
                return self._handle_failure(
                    task, state_path, iteration_start, retry_count,
                    error or "Agent execution failed"
                )
            
            # OBSERVE state
            self.loop.step(LoopState.OBSERVE, "Checking results")
            state_path.append("observe")
            
            # Run tiered quality gates
            gates_passed, passed_list, failed_list, gate_error = self._run_tiered_gates()
            
            self.context.record_step(
                state="OBSERVE",
                input_summary="Running quality gates",
                output_summary=f"Passed: {passed_list}, Failed: {failed_list}",
                files_touched=[]
            )
            
            # CRITIQUE state
            self.loop.step(LoopState.CRITIQUE, "Validating")
            state_path.append("critique")
            
            critique_verdict = None
            if self.critic:
                action = {"action": "complete_task", "target": task.id}
                should_proceed, critique_msg = quick_critique(
                    action, task.__dict__, self.context.window.goal
                )
                critique_verdict = "proceed" if should_proceed else "retry"
            
            if not gates_passed:
                return self._handle_failure(
                    task, state_path, iteration_start, retry_count,
                    gate_error, passed_list, failed_list, critique_verdict
                )
            
            # CHECKPOINT state
            self.loop.step(LoopState.CHECKPOINT, "Committing")
            state_path.append("checkpoint")
            
            # Commit changes
            commit_hash = self._commit_changes(task)
            
            # Record success in context
            self.context.checkpoint(
                iteration=self.loop.fsm.iteration,
                task_id=task.id,
                outcome="success",
                key_changes=task.files_to_modify + task.files_to_create,
                one_liner=f"Completed {task.id}: {task.description[:30]}",
                commit_hash=commit_hash
            )
            
            # Update visualizer
            self.visualizer.update_task(task.id, TaskState.COMPLETE, commit_hash=commit_hash)
            
            # Reset task retries on success
            self.loop.fsm.reset_task_retries(task.id)
            
            # Learn vocabulary associations for glossary
            task_terms = self._extract_task_terms(task)
            for term in task_terms:
                for file_path in task.files_to_modify + task.files_to_create:
                    self.semantic_expander.learn_from_success(term, file_path)
            
            return IterationResult(
                iteration=self.loop.fsm.iteration,
                task_id=task.id,
                success=True,
                state_path=state_path,
                files_changed=task.files_to_modify + task.files_to_create,
                commit_hash=commit_hash,
                duration_ms=int((time.time() - iteration_start) * 1000),
                critique_verdict=critique_verdict,
                gates_passed=passed_list,
                gates_failed=failed_list,
                retry_count=retry_count,
            )
            
        except InvalidTransitionError as e:
            return self._handle_failure(
                task, state_path, iteration_start, retry_count,
                f"Invalid state transition: {e}"
            )
        except Exception as e:
            return self._handle_failure(
                task, state_path, iteration_start, retry_count,
                str(e)
            )
    
    def _handle_failure(
        self,
        task: TaskDefinition,
        state_path: List[str],
        start_time: float,
        retry_count: int,
        error: str,
        gates_passed: List[str] = None,
        gates_failed: List[str] = None,
        critique_verdict: str = None
    ) -> IterationResult:
        """Handle task failure with circuit breaker logic."""
        
        # Use per-task circuit breaker
        next_state, message = self.loop.fsm.record_task_failure(error)
        state_path.append(next_state.value)
        
        # Generate hints for next attempt
        hints = []
        if self.current_manifest:
            for path in task.files_to_modify:
                hint = self.current_manifest.get_hint_for_failure(path)
                if hint:
                    hints.append(hint)
        
        self.hints = hints  # Store for next iteration
        
        # Update visualizer
        if next_state == LoopState.BLOCKED:
            self.visualizer.update_task(task.id, TaskState.BLOCKED, error=error)
        else:
            self.visualizer.update_task(task.id, TaskState.FAILED, error=error)
        
        return IterationResult(
            iteration=self.loop.fsm.iteration,
            task_id=task.id,
            success=False,
            state_path=state_path,
            files_changed=[],
            commit_hash=None,
            duration_ms=int((time.time() - start_time) * 1000),
            critique_verdict=critique_verdict,
            gates_passed=gates_passed or [],
            gates_failed=gates_failed or [],
            retry_count=retry_count + 1,
            error=f"{error} ({message})",
            hints=hints,
        )
    
    def _commit_changes(self, task: TaskDefinition) -> Optional[str]:
        """Commit changes to git."""
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.config.project_root,
                capture_output=True
            )
            result = subprocess.run(
                ["git", "commit", "-m", f"darkzloop: {task.id} - {task.description[:50]}"],
                cwd=self.config.project_root,
                capture_output=True
            )
            if result.returncode == 0:
                hash_result = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=self.config.project_root,
                    capture_output=True
                )
                return hash_result.stdout.decode().strip()
        except Exception:
            pass
        return None
    
    # =========================================================================
    # Full Loop Execution
    # =========================================================================
    
    def run(self) -> List[IterationResult]:
        """Run the full loop until completion or failure."""
        results = []
        
        if not self.dag:
            raise RuntimeError("No plan loaded")
        
        # Get execution order
        if self.config.enable_parallel and self.scheduler:
            groups = self.scheduler.reorder_execution_plan(
                self.dag.compute_execution_order()
            )
        else:
            groups = self.dag.compute_execution_order()
        
        for group in groups:
            for task_id in group:
                # Check if we should stop
                should_stop, reason = self.loop.fsm.should_stop()
                if should_stop:
                    print(f"Loop stopped: {reason}")
                    return results
                
                # Get task definition
                node = self.dag.nodes.get(task_id)
                if not node:
                    continue
                
                task = TaskDefinition(
                    id=task_id,
                    description=node.task_data.get("description", ""),
                    files_to_modify=node.task_data.get("files_to_modify", []),
                    files_to_create=node.task_data.get("files_to_create", []),
                    reference_files=node.task_data.get("reference_files", []),
                    spec_sections=node.task_data.get("spec_sections", []),
                    acceptance_criteria=node.task_data.get("acceptance_criteria", ""),
                )
                
                # Run iteration
                result = self.run_iteration(task)
                results.append(result)
                
                # Save visualization
                if self.config.auto_update_viz:
                    self._save_visualization()
                
                # If task failed and we should stop
                if not result.success and self.config.stop_on_failure:
                    if self.loop.fsm.current_state in {LoopState.BLOCKED, LoopState.FATAL_ERROR}:
                        return results
        
        # Mark complete
        self.loop.step(LoopState.COMPLETE, "All tasks done")
        return results
    
    def _save_visualization(self):
        """Save current visualization to file."""
        output_path = self.config.project_root / ".darkzloop" / "status"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.config.viz_format == "html":
            html = self.visualizer.get_human_view("html")
            (output_path.with_suffix(".html")).write_text(html, encoding="utf-8")
        elif self.config.viz_format == "mermaid":
            md = self.visualizer.get_human_view("mermaid")
            (output_path.with_suffix(".md")).write_text(md, encoding="utf-8")
        else:
            ascii_viz = self.visualizer.get_human_view("ascii")
            (output_path.with_suffix(".txt")).write_text(ascii_viz, encoding="utf-8")
    
    # =========================================================================
    # State Management
    # =========================================================================
    
    def get_status(self) -> dict:
        """Get current status as a dict."""
        return {
            "fsm": self.loop.fsm.to_dict(),
            "context": self.context.to_dict(),
            "iterations_completed": len(self.iteration_results),
            "last_result": self.iteration_results[-1].__dict__ if self.iteration_results else None,
            "should_stop": self.loop.fsm.should_stop(),
            "task_retries": dict(self.loop.fsm.task_retries),
        }
    
    def save_state(self, path: Path):
        """Save runtime state for resumption."""
        state = {
            "fsm": self.loop.fsm.to_dict(),
            "context": self.context.to_dict(),
            "task_retries": dict(self.loop.fsm.task_retries),
            "results": [r.__dict__ for r in self.iteration_results],
            "timestamp": datetime.now().isoformat(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self, path: Path):
        """Load runtime state for resumption."""
        with open(path) as f:
            state = json.load(f)
        
        self.loop.fsm = FSMContext.from_dict(state["fsm"])
        self.loop.fsm.task_retries = state.get("task_retries", {})


# =============================================================================
# Convenience Functions
# =============================================================================

def create_runtime(project_path: Path) -> DarkzloopRuntime:
    """Create a runtime from a project directory."""
    config_path = project_path / "darkzloop.json"
    
    if config_path.exists():
        config = LoopConfig.from_file(config_path)
    else:
        config = LoopConfig(
            spec_path=Path("DARKZLOOP_SPEC.md"),
            plan_path=Path("DARKZLOOP_PLAN.md"),
            project_root=project_path,
        )
    
    return DarkzloopRuntime(config)


def run_single_task(
    project_path: Path,
    task: TaskDefinition,
    agent_fn: Callable
) -> IterationResult:
    """Convenience function to run a single task."""
    runtime = create_runtime(project_path)
    runtime.set_agent_executor(agent_fn)
    return runtime.run_iteration(task)


if __name__ == "__main__":
    # Demo
    print("Darkzloop Runtime v2")
    print("=" * 40)
    
    config = LoopConfig(
        spec_path=Path("DARKZLOOP_SPEC.md"),
        plan_path=Path("DARKZLOOP_PLAN.md"),
        project_root=Path("."),
        gates=[
            GateConfig("test", "echo 'tests pass'", 1),
            GateConfig("lint", "echo 'lint pass'", 2),
        ],
    )
    
    runtime = DarkzloopRuntime(config)
    
    def dummy_agent(context: str, task: dict) -> Tuple[bool, str, str]:
        print(f"Agent received {len(context)} chars of context")
        return True, "Completed", ""
    
    runtime.set_agent_executor(dummy_agent)
    
    task = TaskDefinition(
        id="1.1",
        description="Test task",
        files_to_modify=[],
        files_to_create=["test.txt"],
        reference_files=[],
        spec_sections=["1"],
        acceptance_criteria="File exists",
    )
    
    result = runtime.run_iteration(task)
    print(f"\nResult: success={result.success}, retries={result.retry_count}")
    print(f"Gates passed: {result.gates_passed}")
