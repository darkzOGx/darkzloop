"""
Darkzloop CLI Module

Command-line interface for the Darkzloop agent orchestration framework.

Commands:
    init    - Initialize darkzloop in a project
    plan    - Generate an implementation plan
    run     - Execute the plan with FSM control
    fix     - Fast-lane one-shot fixes
    graph   - View task DAG visualization
    status  - Show current loop state
"""

try:
    from darkzloop.cli.main import app
    __all__ = ["app"]
except ImportError:
    # typer not installed - CLI not available
    app = None
    __all__ = []
