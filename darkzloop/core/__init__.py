"""
darkzloop Core Module

The computational engine for efficient agentic loops.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                    DARKZLOOP ARCHITECTURE                    │
    ├─────────────────────────────────────────────────────────────┤
    │                                                             │
    │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
    │   │   VISUAL    │    │  EXECUTION  │    │    DATA     │   │
    │   │   LAYER     │    │   LAYER     │    │   LAYER     │   │
    │   │  (Mermaid)  │    │  (Python)   │    │   (JSON)    │   │
    │   │             │    │             │    │             │   │
    │   │  The Map    │    │ The Engine  │    │  The Fuel   │   │
    │   └─────────────┘    └─────────────┘    └─────────────┘   │
    │          │                  │                  │           │
    │          └──────────────────┼──────────────────┘           │
    │                             │                               │
    │                    ┌────────▼────────┐                     │
    │                    │  CONTROL LAYER  │                     │
    │                    │     (FSM)       │                     │
    │                    │                 │                     │
    │                    │   The Rails     │                     │
    │                    └─────────────────┘                     │
    │                                                             │
    └─────────────────────────────────────────────────────────────┘

Components:
    - FSM: Finite State Machine preventing invalid transitions
    - Schemas: Strict JSON schemas for agent I/O
    - Context: Token pruning and rolling window management
    - Critic: Reflection checkpoints for self-correction
    - DAG: Parallel execution of independent tasks
"""

from .fsm import (
    LoopState,
    FSMContext,
    LoopController,
    InvalidTransitionError,
    create_loop,
    VALID_TRANSITIONS,
)

from .schemas import (
    ActionType,
    TaskStatus,
    TaskDefinition,
    LoopInput,
    AgentAction,
    ExecutionResult,
    Observation,
    CritiqueResult,
    CheckpointData,
    PlanNode,
    ExecutionPlan,
    validate_agent_output,
    extract_json_from_response,
    compact_serialize,
)

from .context import (
    IterationSummary,
    DetailedStep,
    ContextWindow,
    ContextManager,
    create_iteration_summary,
    extract_relevant_spec_sections,
)

from .critic import (
    CritiqueVerdict,
    CritiqueCheck,
    CritiqueReport,
    Critic,
    RuleBasedCritic,
    create_critic,
    quick_critique,
)

from .dag import (
    NodeStatus,
    DAGNode,
    DAGExecutionResult,
    DAGExecutor,
    parse_plan_to_dag,
    run_shell_command_async,
    run_shell_command_sync,
)

from .runtime import (
    GateConfig,
    LoopConfig,
    IterationResult,
    DarkzloopRuntime,
    create_runtime,
    run_single_task,
)

from .manifest import (
    FileAccessType,
    FileAccess,
    ContextManifest,
    ManifestEnforcer,
    create_enforcer,
)

from .locks import (
    LockType,
    FileLock,
    TaskFileClaims,
    FileLockManager,
    FileAwareDAGScheduler,
    create_file_aware_scheduler,
)

from .visualize import (
    TaskState,
    TaskNode,
    LoopVisualization,
    Visualizer,
    render_for_agent,
    render_dag_for_agent,
    render_mermaid_flowchart,
    render_fsm_diagram,
    render_ascii,
    render_html,
)

from .semantic import (
    SemanticMatch,
    Glossary,
    SemanticExpander,
    BUILTIN_SYNONYMS,
    create_expander,
    quick_expand,
    generate_synonyms_prompt,
    parse_llm_synonyms,
)

__all__ = [
    # FSM
    "LoopState",
    "FSMContext", 
    "LoopController",
    "InvalidTransitionError",
    "create_loop",
    "VALID_TRANSITIONS",
    
    # Schemas
    "ActionType",
    "TaskStatus",
    "TaskDefinition",
    "LoopInput",
    "AgentAction",
    "ExecutionResult",
    "Observation",
    "CritiqueResult",
    "CheckpointData",
    "PlanNode",
    "ExecutionPlan",
    "validate_agent_output",
    "extract_json_from_response",
    "compact_serialize",
    
    # Context
    "IterationSummary",
    "DetailedStep",
    "ContextWindow",
    "ContextManager",
    "create_iteration_summary",
    "extract_relevant_spec_sections",
    
    # Critic
    "CritiqueVerdict",
    "CritiqueCheck",
    "CritiqueReport",
    "Critic",
    "RuleBasedCritic",
    "create_critic",
    "quick_critique",
    
    # DAG
    "NodeStatus",
    "DAGNode",
    "DAGExecutionResult",
    "DAGExecutor",
    "parse_plan_to_dag",
    "run_shell_command_async",
    "run_shell_command_sync",
    
    # Runtime
    "GateConfig",
    "LoopConfig",
    "IterationResult",
    "DarkzloopRuntime",
    "create_runtime",
    "run_single_task",
    
    # Manifest (read-before-write)
    "FileAccessType",
    "FileAccess",
    "ContextManifest",
    "ManifestEnforcer",
    "create_enforcer",
    
    # File Locks (parallel safety)
    "LockType",
    "FileLock",
    "TaskFileClaims",
    "FileLockManager",
    "FileAwareDAGScheduler",
    "create_file_aware_scheduler",
    
    # Visualization (dual-mode)
    "TaskState",
    "TaskNode",
    "LoopVisualization",
    "Visualizer",
    "render_for_agent",
    "render_dag_for_agent",
    "render_mermaid_flowchart",
    "render_fsm_diagram",
    "render_ascii",
    "render_html",
    
    # Semantic Expansion (vocabulary gap)
    "SemanticMatch",
    "Glossary",
    "SemanticExpander",
    "BUILTIN_SYNONYMS",
    "create_expander",
    "quick_expand",
    "generate_synonyms_prompt",
    "parse_llm_synonyms",
]

__version__ = "0.6.0"
