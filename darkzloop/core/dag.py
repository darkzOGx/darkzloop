"""
darkzloop DAG Executor

Enables parallel execution of independent tasks.
If the plan has tasks A, B, C where A->C and B->C,
A and B can run simultaneously.

Uses Mermaid to visualize the DAG and detect parallel branches.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Callable, Any
from enum import Enum
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import re


class NodeStatus(Enum):
    """Execution status of a DAG node."""
    PENDING = "pending"
    READY = "ready"      # Dependencies satisfied, can run
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DAGNode:
    """A node in the execution DAG."""
    id: str
    task_data: dict
    dependencies: List[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    duration_ms: int = 0
    
    def is_ready(self, completed: Set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed for dep in self.dependencies)


@dataclass
class DAGExecutionResult:
    """Result of executing the entire DAG."""
    success: bool
    completed_nodes: List[str]
    failed_nodes: List[str]
    skipped_nodes: List[str]
    total_duration_ms: int
    parallel_groups: List[List[str]]  # How tasks were grouped


class DAGExecutor:
    """
    Executes a DAG of tasks with parallel execution where possible.
    
    Usage:
        dag = DAGExecutor()
        dag.add_node("1.1", task_data, dependencies=[])
        dag.add_node("1.2", task_data, dependencies=[])
        dag.add_node("2.1", task_data, dependencies=["1.1", "1.2"])
        
        result = dag.execute(executor_fn)
    """
    
    def __init__(self, max_parallel: int = 4):
        self.nodes: Dict[str, DAGNode] = {}
        self.max_parallel = max_parallel
        self.execution_order: List[List[str]] = []
    
    def add_node(
        self,
        node_id: str,
        task_data: dict,
        dependencies: List[str] = None
    ):
        """Add a node to the DAG."""
        self.nodes[node_id] = DAGNode(
            id=node_id,
            task_data=task_data,
            dependencies=dependencies or []
        )
    
    def validate(self) -> tuple[bool, str]:
        """Validate the DAG structure."""
        # Check all dependencies exist
        for node_id, node in self.nodes.items():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    return False, f"Node {node_id} depends on non-existent {dep}"
        
        # Check for cycles (topological sort)
        visited = set()
        rec_stack = set()
        
        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for dep in self.nodes[node_id].dependencies:
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        for node_id in self.nodes:
            if node_id not in visited:
                if has_cycle(node_id):
                    return False, "DAG contains a cycle"
        
        return True, ""
    
    def compute_execution_order(self) -> List[List[str]]:
        """
        Compute execution order with parallel groups.
        Each inner list can be executed in parallel.
        """
        completed: Set[str] = set()
        groups: List[List[str]] = []
        remaining = set(self.nodes.keys())
        
        while remaining:
            # Find all nodes that are ready
            ready = [
                node_id for node_id in remaining
                if self.nodes[node_id].is_ready(completed)
            ]
            
            if not ready:
                # No progress possible - remaining nodes have unmet deps
                break
            
            groups.append(ready)
            completed.update(ready)
            remaining -= set(ready)
        
        self.execution_order = groups
        return groups
    
    def execute_sync(
        self,
        executor_fn: Callable[[str, dict], tuple[bool, Any, str]],
        stop_on_failure: bool = True
    ) -> DAGExecutionResult:
        """
        Execute the DAG synchronously (sequential within groups, parallel across groups).
        
        Args:
            executor_fn: Function(node_id, task_data) -> (success, result, error)
            stop_on_failure: Whether to stop on first failure
        """
        start_time = time.time()
        completed_nodes = []
        failed_nodes = []
        skipped_nodes = []
        
        groups = self.compute_execution_order()
        completed_set: Set[str] = set()
        
        for group in groups:
            # Execute nodes in this group
            # For sync execution, we do them sequentially
            # (async version would parallelize)
            
            for node_id in group:
                node = self.nodes[node_id]
                
                # Check if should skip due to failed dependency
                if any(dep in failed_nodes for dep in node.dependencies):
                    node.status = NodeStatus.SKIPPED
                    skipped_nodes.append(node_id)
                    continue
                
                # Execute
                node.status = NodeStatus.RUNNING
                node_start = time.time()
                
                try:
                    success, result, error = executor_fn(node_id, node.task_data)
                    node.duration_ms = int((time.time() - node_start) * 1000)
                    
                    if success:
                        node.status = NodeStatus.COMPLETE
                        node.result = result
                        completed_nodes.append(node_id)
                        completed_set.add(node_id)
                    else:
                        node.status = NodeStatus.FAILED
                        node.error = error
                        failed_nodes.append(node_id)
                        
                        if stop_on_failure:
                            # Skip remaining
                            for remaining_id in group:
                                if remaining_id != node_id and self.nodes[remaining_id].status == NodeStatus.PENDING:
                                    self.nodes[remaining_id].status = NodeStatus.SKIPPED
                                    skipped_nodes.append(remaining_id)
                            break
                            
                except Exception as e:
                    node.status = NodeStatus.FAILED
                    node.error = str(e)
                    failed_nodes.append(node_id)
                    
                    if stop_on_failure:
                        break
            
            if stop_on_failure and failed_nodes:
                # Mark all remaining as skipped
                for future_group in groups[groups.index(group) + 1:]:
                    for node_id in future_group:
                        if self.nodes[node_id].status == NodeStatus.PENDING:
                            self.nodes[node_id].status = NodeStatus.SKIPPED
                            skipped_nodes.append(node_id)
                break
        
        total_duration = int((time.time() - start_time) * 1000)
        
        return DAGExecutionResult(
            success=len(failed_nodes) == 0,
            completed_nodes=completed_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            total_duration_ms=total_duration,
            parallel_groups=groups
        )
    
    async def execute_async(
        self,
        executor_fn: Callable[[str, dict], tuple[bool, Any, str]],
        stop_on_failure: bool = True,
        use_process_pool: bool = False
    ) -> DAGExecutionResult:
        """
        Execute the DAG with true parallelism using asyncio.
        
        Args:
            executor_fn: Function(node_id, task_data) -> (success, result, error)
            stop_on_failure: Whether to stop on first failure
            use_process_pool: Use ProcessPoolExecutor for CPU-bound tasks.
                             Default False uses ThreadPoolExecutor (better for I/O-bound
                             like LLM API calls).
        
        Note on Python's GIL:
        - ThreadPoolExecutor: Good for I/O-bound (API calls, file reads)
        - ProcessPoolExecutor: Good for CPU-bound (local analysis, compilation)
        
        For darkzloop, most executor_fn calls are LLM API requests (I/O-bound),
        so ThreadPoolExecutor is the default.
        """
        from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
        
        start_time = time.time()
        completed_nodes = []
        failed_nodes = []
        skipped_nodes = []
        
        groups = self.compute_execution_order()
        completed_set: Set[str] = set()
        should_stop = False
        
        # Choose executor based on task type
        PoolExecutor = ProcessPoolExecutor if use_process_pool else ThreadPoolExecutor
        
        for group in groups:
            if should_stop:
                for node_id in group:
                    self.nodes[node_id].status = NodeStatus.SKIPPED
                    skipped_nodes.append(node_id)
                continue
            
            # Run this group in parallel
            tasks = []
            for node_id in group:
                node = self.nodes[node_id]
                if any(dep in failed_nodes for dep in node.dependencies):
                    node.status = NodeStatus.SKIPPED
                    skipped_nodes.append(node_id)
                else:
                    tasks.append(self._execute_node_async(node, executor_fn, PoolExecutor))
            
            # Wait for all tasks in group
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        failed_nodes.append(str(result))
                        if stop_on_failure:
                            should_stop = True
                    elif result[0]:  # success
                        completed_nodes.append(result[1])
                        completed_set.add(result[1])
                    else:
                        failed_nodes.append(result[1])
                        if stop_on_failure:
                            should_stop = True
        
        total_duration = int((time.time() - start_time) * 1000)
        
        return DAGExecutionResult(
            success=len(failed_nodes) == 0,
            completed_nodes=completed_nodes,
            failed_nodes=failed_nodes,
            skipped_nodes=skipped_nodes,
            total_duration_ms=total_duration,
            parallel_groups=groups
        )
    
    async def _execute_node_async(
        self,
        node: DAGNode,
        executor_fn: Callable,
        PoolExecutor: type
    ) -> tuple[bool, str]:
        """Execute a single node asynchronously."""
        node.status = NodeStatus.RUNNING
        start = time.time()
        
        try:
            # Run in appropriate pool to not block event loop
            loop = asyncio.get_event_loop()
            with PoolExecutor(max_workers=1) as pool:
                success, result, error = await loop.run_in_executor(
                    pool, executor_fn, node.id, node.task_data
                )
            
            node.duration_ms = int((time.time() - start) * 1000)
            
            if success:
                node.status = NodeStatus.COMPLETE
                node.result = result
                return True, node.id
            else:
                node.status = NodeStatus.FAILED
                node.error = error
                return False, node.id
                
        except Exception as e:
            node.status = NodeStatus.FAILED
            node.error = str(e)
            return False, node.id
    
    def to_mermaid(self) -> str:
        """Generate Mermaid diagram of the DAG."""
        lines = ["graph TD"]
        
        for node_id, node in self.nodes.items():
            # Style based on status
            if node.status == NodeStatus.COMPLETE:
                lines.append(f"    {node_id}[✅ {node_id}]:::complete")
            elif node.status == NodeStatus.RUNNING:
                lines.append(f"    {node_id}[⏳ {node_id}]:::running")
            elif node.status == NodeStatus.FAILED:
                lines.append(f"    {node_id}[❌ {node_id}]:::failed")
            elif node.status == NodeStatus.READY:
                lines.append(f"    {node_id}[🔜 {node_id}]:::ready")
            else:
                lines.append(f"    {node_id}[{node_id}]")
            
            # Add edges for dependencies
            for dep in node.dependencies:
                lines.append(f"    {dep} --> {node_id}")
        
        # Add styles
        lines.extend([
            "    classDef complete fill:#90EE90",
            "    classDef running fill:#FFD700",
            "    classDef failed fill:#FF6B6B",
            "    classDef ready fill:#87CEEB",
        ])
        
        return "\n".join(lines)
    
    def get_parallel_summary(self) -> str:
        """Get a summary of parallelization opportunities."""
        groups = self.compute_execution_order()
        
        lines = ["Parallel Execution Groups:"]
        for i, group in enumerate(groups):
            parallelism = f"({len(group)} parallel)" if len(group) > 1 else "(sequential)"
            lines.append(f"  Stage {i + 1}: {group} {parallelism}")
        
        max_parallel = max(len(g) for g in groups) if groups else 0
        sequential_time = len(self.nodes)
        parallel_time = len(groups)
        speedup = sequential_time / parallel_time if parallel_time > 0 else 1
        
        lines.append(f"\nMax parallelism: {max_parallel}")
        lines.append(f"Theoretical speedup: {speedup:.1f}x")
        
        return "\n".join(lines)


# =============================================================================
# Plan Parser - Extract DAG from Markdown Plan
# =============================================================================

def parse_plan_to_dag(plan_content: str) -> DAGExecutor:
    """
    Parse a DARKZLOOP_PLAN.md file into a DAG.
    
    Looks for task patterns like:
    - [ ] **Task 1.1**: Description
      - Modify: file.py
      - Dependencies: 1.0
    """
    dag = DAGExecutor()
    
    # Pattern 1: Bold ID (Legacy) - e.g. "**1.1**: Description"
    # Pattern 2: HTML Comment ID - e.g. "Description <!-- id: 1.1 -->"
    
    # We'll split the plan into lines/blocks to handle both
    
    # First, try to find tasks with explicit bold IDs
    bold_pattern = r'-\s*\[\s*[x ]?\s*\]\s*\*\*(?:Task\s+)?(\d+\.\d+)\*\*:\s*(.+?)(?=\n-\s*\[|\n##|\Z)'
    bold_matches = re.findall(bold_pattern, plan_content, re.DOTALL | re.IGNORECASE)
    
    for task_id, task_block in bold_matches:
        _add_node_from_match(dag, task_id, task_block, task_block)

    # Next, find tasks with HTML comments (if no bold IDs found or mixed - avoid duplicates)
    # This regex looks for: - [ ] Description <!-- id: X -->
    comment_pattern = r'-\s*\[\s*[x ]?\s*\]\s*(.+?)<!--\s*id:\s*([a-zA-Z0-9\._-]+)\s*-->'
    comment_matches = re.findall(comment_pattern, plan_content)
    
    for description, task_id in comment_matches:
        if task_id not in dag.nodes:
            # For comment matches, we don't capture the full block easily with finding all
            # So we assume dependencies are also in comments or simple structure
            # To get full block including nested bullets, we might need a more complex parse
            # For now, we use the description as the block for extraction
            _add_node_from_match(dag, task_id, description, description)
            
    return dag

def _add_node_from_match(dag: DAGExecutor, task_id: str, description_text: str, full_block: str):
    """Helper to add a node to DAG from parsed components."""
    # Extract files to modify/create
    files_modify = re.findall(r'Modify:\s*`([^`]+)`', full_block)
    files_create = re.findall(r'New file:\s*`([^`]+)`', full_block)
    
    # Extract dependencies
    deps = []
    # explicit "Dependencies: 1, 2"
    explicit_deps = re.findall(r'Dependencies?:\s*([\d\., ]+)', full_block)
    if explicit_deps:
        deps = [d.strip() for d in explicit_deps[0].split(',')]
    
    # infer from ID (X.Y -> X.Y-1)
    if not deps and '.' in task_id:
        try:
            parts = task_id.split('.')
            if len(parts) == 2 and int(parts[1]) > 1:
                prev = f"{parts[0]}.{int(parts[1]) - 1}"
                deps = [prev]
        except ValueError:
            pass

    dag.add_node(
        task_id,
        {
            "id": task_id,
            "description": description_text.strip(),
            "files_to_modify": files_modify,
            "files_to_create": files_create,
        },
        dependencies=deps
    )


async def run_shell_command_async(
    command: str,
    cwd: str = None,
    timeout: int = 300
) -> tuple[bool, str, str]:
    """
    Run a shell command asynchronously without blocking.
    
    Use this for quality gates (cargo test, npm lint) which are CPU-bound
    and should not block the event loop.
    
    Args:
        command: Shell command to run
        cwd: Working directory
        timeout: Timeout in seconds
        
    Returns:
        (success, stdout, stderr)
    """
    import asyncio.subprocess
    
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            return False, "", f"Command timed out after {timeout}s"
        
        success = proc.returncode == 0
        return success, stdout.decode()[:5000], stderr.decode()[:2000]
        
    except Exception as e:
        return False, "", str(e)


def run_shell_command_sync(
    command: str,
    cwd: str = None,
    timeout: int = 300
) -> tuple[bool, str, str]:
    """
    Run a shell command synchronously.
    
    Use this when not in async context.
    """
    import subprocess
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            timeout=timeout
        )
        
        success = result.returncode == 0
        return success, result.stdout.decode()[:5000], result.stderr.decode()[:2000]
        
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return False, "", str(e)


if __name__ == "__main__":
    # Demo DAG execution
    dag = DAGExecutor()
    
    # Create a sample DAG:
    # 1.1 and 1.2 can run in parallel (no deps)
    # 2.1 depends on both
    # 2.2 depends on 2.1
    
    dag.add_node("1.1", {"description": "Create migration"}, [])
    dag.add_node("1.2", {"description": "Create model"}, [])
    dag.add_node("2.1", {"description": "Create handler"}, ["1.1", "1.2"])
    dag.add_node("2.2", {"description": "Add route"}, ["2.1"])
    
    print("DAG Mermaid:")
    print(dag.to_mermaid())
    
    print("\n" + dag.get_parallel_summary())
    
    # Execute with dummy function
    def dummy_executor(node_id: str, data: dict) -> tuple[bool, str, str]:
        print(f"  Executing {node_id}: {data['description']}")
        time.sleep(0.1)  # Simulate work
        return True, f"Result of {node_id}", ""
    
    print("\nExecuting DAG...")
    result = dag.execute_sync(dummy_executor)
    
    print(f"\nResult: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Completed: {result.completed_nodes}")
    print(f"Duration: {result.total_duration_ms}ms")
