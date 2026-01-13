"""
Darkzloop - Reliable Autonomous Coding Loops with Semantic Memory

A production-grade agent orchestration framework that prevents common
agent failures through:

1. FSM State Control - Prevents state hallucination
2. Context Manifest - Read-before-write enforcement  
3. Semantic Expansion - Vocabulary gap bridging
4. Tiered Gates - Quality enforcement with circuit breakers
5. Dual-Mode Visualization - For agents and humans

Usage:
    # CLI
    $ darkzloop init
    $ darkzloop plan --task "Add user authentication"
    $ darkzloop run --attended
    $ darkzloop fix "Login button not working"
    
    # Python API
    from darkzloop import DarkzloopRuntime, LoopConfig
    
    runtime = DarkzloopRuntime(config)
    runtime.set_agent_executor(my_agent_fn)
    results = runtime.run()
"""

from darkzloop.core import (
    # FSM
    LoopState,
    FSMContext,
    LoopController,
    create_loop,
    
    # Runtime
    GateConfig,
    LoopConfig,
    IterationResult,
    DarkzloopRuntime,
    create_runtime,
    
    # Schemas
    TaskDefinition,
    AgentAction,
    
    # Semantic
    SemanticExpander,
    quick_expand,
    
    # Visualization
    Visualizer,
    render_for_agent,
)

__version__ = "0.6.0"
__all__ = [
    # Core
    "LoopState",
    "FSMContext", 
    "LoopController",
    "create_loop",
    
    # Runtime
    "GateConfig",
    "LoopConfig",
    "IterationResult",
    "DarkzloopRuntime",
    "create_runtime",
    
    # Schemas
    "TaskDefinition",
    "AgentAction",
    
    # Semantic
    "SemanticExpander",
    "quick_expand",
    
    # Visualization
    "Visualizer",
    "render_for_agent",
]
