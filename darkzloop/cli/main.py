"""
Darkzloop CLI - Main Entry Point

The command-line interface for the Darkzloop agent orchestration framework.

Commands:
    init    - Initialize darkzloop in a project
    plan    - Generate an implementation plan with semantic expansion
    run     - Execute the plan using FSM control
    fix     - Fast-lane one-shot fixes (no spec file needed)
    graph   - View task DAG visualization
    status  - Show current loop state
    config  - Manage global configuration
"""

import sys
import os
import io
import json
import webbrowser
from pathlib import Path
from typing import Optional
from datetime import datetime


def _setup_windows_console():
    """Configure Windows console for Unicode support."""
    if sys.platform != "win32":
        return

    # Set environment variables for UTF-8 encoding
    os.environ['PYTHONIOENCODING'] = 'utf-8'

    # Try to enable UTF-8 mode on Windows
    try:
        # Reconfigure stdout/stderr to handle encoding errors gracefully
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        # Fallback: wrap stdout/stderr with error-tolerant encoding
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace'
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding='utf-8', errors='replace'
            )
        except Exception:
            pass


_setup_windows_console()

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.prompt import Prompt, Confirm

from darkzloop.cli.config import (
    load_config, GlobalConfig, LocalConfig, MergedConfig,
    get_global_config_path, get_api_key, set_api_key,
    get_state_path, ensure_global_config
)
from darkzloop.cli.setup import init_project, is_initialized, detect_stack
from darkzloop.cli.utils import (
    check_git_clean, prompt_git_safety, create_backup_branch,
    setup_debug_logging, enable_traceback, print_environment_check,
    DryRunContext, set_dry_run_context, check_git_status,
    get_logo, safe_emoji
)


# =============================================================================
# App Setup
# =============================================================================

app = typer.Typer(
    name="darkzloop",
    help="Darkzloop: Reliable Autonomous Coding Loops with Semantic Memory",
    add_completion=True,
    no_args_is_help=False,  # We handle no-args with interactive wizard
    invoke_without_command=True,
)

console = Console()


# =============================================================================
# Interactive Wizard (First Run / No Args)
# =============================================================================

@app.callback()
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """
    Darkzloop: Reliable Autonomous Coding Loops

    Run without arguments for interactive setup wizard.
    """
    if version:
        from darkzloop import __version__
        console.print(f"Darkzloop v{__version__}")
        raise typer.Exit()
    
    # If a subcommand was invoked, let it handle things
    if ctx.invoked_subcommand is not None:
        return
    
    # No subcommand = run interactive wizard
    run_interactive_wizard()


def run_interactive_wizard():
    """Interactive wizard for first-time users or when run without arguments."""
    from darkzloop.core.executors.presets import (
        detect_available_presets, get_preset, get_presets_by_category
    )
    
    console.print("")
    console.print(Panel.fit(
        "[bold blue]♾️  Welcome to Darkzloop[/bold blue]\n\n"
        "[dim]Reliable. Autonomous. Model-Agnostic.[/dim]",
        border_style="blue"
    ))
    console.print("")
    
    # Check if already configured
    global_config = GlobalConfig.load()
    is_configured = global_config.agent.command != "claude" or _check_tool_exists(global_config.agent.command)
    
    # Check if in a project
    in_project = is_initialized(Path.cwd())
    
    # Determine what to do
    if not is_configured:
        console.print("[yellow]First, let's set up your LLM backend.[/yellow]")
        console.print("")
        _interactive_configure_backend()
    
    if not in_project:
        console.print("")
        if Confirm.ask("Would you like to initialize Darkzloop in the current directory?"):
            init_project(Path.cwd(), console, interactive=True)
        else:
            console.print("")
            console.print("[dim]You can run [bold]darkzloop init[/bold] later in any project.[/dim]")
    
    # Ask what they want to do
    console.print("")
    console.print("[bold]What would you like to do?[/bold]")
    console.print("")
    console.print("  [cyan]1[/cyan]. Fix a bug or add a feature (quick)")
    console.print("  [cyan]2[/cyan]. Create a detailed plan first")
    console.print("  [cyan]3[/cyan]. Run diagnostics")
    console.print("  [cyan]4[/cyan]. Configure settings")
    console.print("  [cyan]5[/cyan]. Exit")
    console.print("")
    
    choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4", "5"], default="1")
    
    if choice == "1":
        _interactive_fix()
    elif choice == "2":
        _interactive_plan()
    elif choice == "3":
        _run_doctor()
    elif choice == "4":
        _interactive_configure_backend()
    else:
        console.print("")
        console.print("[dim]Run [bold]darkzloop --help[/bold] to see all commands.[/dim]")
        console.print("")


def _check_tool_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    import shutil
    return shutil.which(cmd) is not None


def _interactive_configure_backend():
    """Interactive backend configuration."""
    from darkzloop.core.executors.presets import (
        detect_available_presets, get_preset, PRESETS
    )
    
    console.print("[bold]Available LLM Backends:[/bold]")
    console.print("")
    
    # Detect what's installed
    available = []
    not_available = []
    
    for name, preset, is_available in detect_available_presets():
        if is_available:
            available.append((name, preset))
        else:
            not_available.append((name, preset))
    
    # Show available tools
    if available:
        console.print("[green]✓ Installed on your system:[/green]")
        for i, (name, preset) in enumerate(available, 1):
            console.print(f"  [cyan]{i}[/cyan]. {preset.name} ([bold]{name}[/bold])")
        console.print("")
    
    # Show not installed
    console.print("[dim]Not installed (but supported):[/dim]")
    for name, preset in not_available[:5]:  # Show top 5
        console.print(f"  • {preset.name} - {preset.description[:50]}...")
    console.print("")
    
    if not available:
        console.print("[yellow]No supported LLM tools detected![/yellow]")
        console.print("")
        console.print("Install one of these:")
        console.print("  • [bold]claude[/bold] - Claude CLI (claude.ai subscription)")
        console.print("  • [bold]ollama[/bold] - Local models, free (ollama.ai)")
        console.print("  • [bold]gh copilot[/bold] - GitHub Copilot CLI")
        console.print("")
        return
    
    # Let user choose
    choices = [str(i) for i in range(1, len(available) + 1)]
    choice = Prompt.ask(
        "Which backend would you like to use?",
        choices=choices,
        default="1"
    )
    
    selected_name, selected_preset = available[int(choice) - 1]
    
    # Save configuration
    global_config = GlobalConfig.load()
    global_config.agent.mode = "shell"
    global_config.agent.command = selected_preset.command
    global_config.agent.args = selected_preset.args
    global_config.save()
    
    console.print("")
    console.print(f"[green]✓ Configured: {selected_preset.name}[/green]")
    console.print(f"[dim]  Command: {selected_preset.command} {' '.join(selected_preset.args)}[/dim]")
    

def _interactive_fix():
    """Interactive fix mode - ask what to fix."""
    console.print("")
    
    # Check if initialized
    if not is_initialized(Path.cwd()):
        console.print("[yellow]⚠️  Darkzloop not initialized in this directory.[/yellow]")
        if Confirm.ask("Initialize now?"):
            init_project(Path.cwd(), console, interactive=True)
        else:
            console.print("[dim]Run from a project directory or run [bold]darkzloop init[/bold] first.[/dim]")
            return
    
    console.print("[bold]Describe what you want to fix or build:[/bold]")
    console.print("[dim](Be specific - e.g., 'Add retry logic to the payment webhook when it gets a 429 error')[/dim]")
    console.print("")
    
    task = Prompt.ask("Task")
    
    if not task.strip():
        console.print("[red]No task provided.[/red]")
        return
    
    console.print("")
    console.print("[bold]How would you like to run this?[/bold]")
    console.print("  [cyan]1[/cyan]. Attended (approve each step)")
    console.print("  [cyan]2[/cyan]. Unattended (fully autonomous)")
    console.print("")
    
    mode = Prompt.ask("Mode", choices=["1", "2"], default="1")
    attended = (mode == "1")
    
    console.print("")
    if attended:
        console.print("[dim]Running in attended mode - you'll approve each step.[/dim]")
    else:
        console.print("[dim]Running in unattended mode - FSM + circuit breakers provide safety.[/dim]")
    console.print("")
    
    # Run the fix
    _run_fix_command(task, attended=attended)


def _run_fix_command(task: str, attended: bool = True):
    """Execute the fix command."""
    # This will call the actual fix logic
    # For now, show what would happen
    console.print(Panel(
        f"[bold]Task:[/bold] {task}\n"
        f"[bold]Mode:[/bold] {'Attended' if attended else 'Unattended'}",
        title="🔧 Starting Fix",
        border_style="green"
    ))
    console.print("")
    
    # Import and run the actual fix logic
    # This connects to the rest of the system
    console.print("[yellow]⚙️  Semantic expansion...[/yellow]")
    
    from darkzloop.core.semantic import SemanticExpander
    expander = SemanticExpander(Path.cwd())
    
    # Extract terms and expand
    terms = task.lower().split()
    key_terms = [t for t in terms if len(t) > 3][:5]
    
    for term in key_terms:
        expansion = expander.expand(term)
        synonyms = [k for k in list(expansion.keys())[:4] if k != term]
        if synonyms:
            console.print(f"  [dim]{term} → {synonyms}[/dim]")
    
    console.print("")
    console.print("[yellow]📂 Searching for relevant files...[/yellow]")
    
    matches = expander.search_files(key_terms)
    if matches:
        for match in matches[:5]:
            console.print(f"  [dim]• {match.path} ({match.confidence:.0%})[/dim]")
    else:
        console.print("  [dim]No direct matches - will search more broadly[/dim]")
    
    console.print("")
    
    # For now, explain next steps
    console.print("[bold green]Ready to execute![/bold green]")
    console.print("")
    console.print("The full execution would:")
    console.print("  1. Generate a plan using your configured LLM")
    console.print("  2. Execute each task with FSM control")
    console.print("  3. Run your quality gates (tests, lints)")
    console.print("  4. Commit the changes (if all gates pass)")
    console.print("")
    console.print("[dim]Full runtime integration coming in v0.7.0[/dim]")


def _interactive_plan():
    """Interactive plan creation."""
    console.print("")
    console.print("[bold]What feature or change do you want to plan?[/bold]")
    console.print("[dim](This creates a detailed DARKZLOOP_SPEC.md for complex changes)[/dim]")
    console.print("")
    
    task = Prompt.ask("Feature/Change")
    
    if not task.strip():
        console.print("[red]No task provided.[/red]")
        return
    
    console.print("")
    console.print(f"[dim]Would create a plan for: {task}[/dim]")
    console.print("[dim]Run [bold]darkzloop plan --task \"{task}\"[/bold] to generate.[/dim]")


def _run_doctor():
    """Run doctor diagnostics."""
    # Import and run doctor command
    console.print("")
    console.print("[bold]Running diagnostics...[/bold]")
    console.print("")
    
    # Inline doctor logic for interactive mode
    from darkzloop.core.executors.presets import get_preset, check_preset_auth
    
    global_config = GlobalConfig.load()
    
    console.print("[bold]Executor Configuration[/bold]")
    console.print(f"  Mode: [cyan]{global_config.agent.mode.upper()}[/cyan]")
    console.print(f"  Command: [cyan]{global_config.agent.command}[/cyan]")
    
    if _check_tool_exists(global_config.agent.command):
        console.print("  [green]✓ Command found[/green]")
        
        # Check auth
        preset = get_preset(global_config.agent.command)
        if preset and preset.auth_check:
            is_authed, msg = check_preset_auth(global_config.agent.command)
            if is_authed:
                console.print(f"  [green]✓ {msg}[/green]")
            else:
                console.print(f"  [yellow]⚠️  {msg}[/yellow]")
    else:
        console.print(f"  [red]✗ Command not found: {global_config.agent.command}[/red]")
    
    console.print("")
    
    # Project check
    if is_initialized(Path.cwd()):
        console.print("[bold]Project Configuration[/bold]")
        console.print(f"  [green]✓ Darkzloop initialized in {Path.cwd().name}[/green]")
    else:
        console.print("[bold]Project Configuration[/bold]")
        console.print("  [yellow]⚠️  Not in a Darkzloop project[/yellow]")
    
    console.print("")


# =============================================================================
# Helper Functions
# =============================================================================

def require_init(path: Path = None):
    """Ensure darkzloop is initialized in the project."""
    root = path or Path.cwd()
    if not is_initialized(root):
        console.print("[red]❌ Darkzloop not initialized in this project.[/red]")
        console.print("")
        console.print("Run [bold]darkzloop init[/bold] first to:")
        console.print("  • Detect your tech stack (Rust/Python/Node/Go)")
        console.print("  • Configure quality gates")
        console.print("  • Create spec templates")
        raise typer.Exit(1)


def require_executor():
    """
    Ensure an executor (native tool or API) is configured.
    
    BYOA mode: Just needs a native tool installed
    API mode: Needs API key
    """
    global_config = GlobalConfig.load()
    
    if global_config.agent.mode == "shell":
        # BYOA mode - check if tool exists
        import shutil
        cmd = global_config.agent.command
        if not shutil.which(cmd):
            console.print(f"[red]❌ Native tool not found: {cmd}[/red]")
            console.print("")
            console.print("Options:")
            console.print("  1. Install the tool and authenticate:")
            console.print(f"     • [bold]{cmd}[/bold] (install, then run authentication)")
            console.print("")
            console.print("  2. Switch to a different tool:")
            console.print("     • [bold]darkzloop config native ollama[/bold] (local, free)")
            console.print("     • [bold]darkzloop config native claude[/bold] (requires Claude CLI)")
            console.print("")
            console.print("  3. Use direct API:")
            console.print("     • [bold]darkzloop config api anthropic --api-key KEY[/bold]")
            console.print("")
            console.print("Run [bold]darkzloop doctor[/bold] to diagnose.")
            raise typer.Exit(1)
        return "shell", cmd
    else:
        # API mode - need API key
        key = get_api_key(global_config.agent.provider)
        if not key:
            provider = global_config.agent.provider
            env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
            console.print(f"[red]❌ No API key for {provider}[/red]")
            console.print("")
            console.print("Options:")
            console.print(f"  • Set environment variable: [bold]export {env_var}=sk-...[/bold]")
            console.print(f"  • Or configure directly: [bold]darkzloop config api {provider} --api-key KEY[/bold]")
            console.print("")
            console.print("Or switch to BYOA mode (no API key needed):")
            console.print("  • [bold]darkzloop config native claude[/bold]")
            console.print("  • [bold]darkzloop config native ollama[/bold]")
            raise typer.Exit(1)
        return "api", key


def require_api_key():
    """Legacy function - use require_executor instead."""
    return require_executor()


def print_version():
    """Print version information."""
    from darkzloop import __version__
    console.print(f"Darkzloop v{__version__}")


# =============================================================================
# Commands
# =============================================================================

@app.command()
def init(
    path: Path = typer.Argument(
        None,
        help="Project root directory (defaults to current directory)"
    ),
    non_interactive: bool = typer.Option(
        False, "--yes", "-y",
        help="Skip interactive prompts"
    ),
):
    """
    🚀 Initialize darkzloop in a project.
    
    Detects your tech stack (Rust, Node, Python, Go) and creates:
    - darkzloop.json (configuration)
    - DARKZLOOP_SPEC.md (spec template)
    - .darkzloop/ (local state directory)
    """
    target = path or Path.cwd()
    
    console.print(f"[bold]Initializing Darkzloop in:[/bold] {target}")
    console.print("")
    
    init_project(target, console, interactive=not non_interactive)


@app.command()
def plan(
    task: Optional[str] = typer.Option(
        None, "--task", "-t",
        help="Quick task description (skips spec editing)"
    ),
    expand: bool = typer.Option(
        True, "--expand/--no-expand",
        help="Run semantic expansion on keywords"
    ),
):
    """
    📝 Generate an implementation plan.
    
    Analyzes the spec, runs semantic expansion, and creates a task DAG.
    """
    require_init()
    config = load_config()
    
    # Import runtime components
    from darkzloop.core.semantic import SemanticExpander
    
    console.print("[bold blue]📝 Planning Phase[/bold blue]")
    console.print("")
    
    # Check spec exists
    spec_path = config.project_root / config.local_config.spec_path
    if not spec_path.exists() and not task:
        console.print(f"[red]❌ Spec not found:[/red] {spec_path}")
        console.print("Edit your spec or use [bold]--task[/bold] for quick tasks.")
        raise typer.Exit(1)
    
    # Semantic expansion
    if expand:
        console.print("[bold]🔍 Running Semantic Expansion...[/bold]")
        expander = SemanticExpander(config.project_root)
        
        if task:
            # Extract terms from task description
            import re
            terms = [w for w in re.findall(r'\b[a-z]{3,}\b', task.lower()) 
                    if w not in {'the', 'and', 'for', 'with'}]
        else:
            # Extract terms from spec
            spec_content = spec_path.read_text()
            terms = expander.extract_spec_terms(spec_content)
        
        # Expand and display
        table = Table(title="Synonym Clusters")
        table.add_column("Term", style="cyan")
        table.add_column("Synonyms", style="green")
        
        for term in terms[:10]:
            expansion = expander.expand(term)
            top_synonyms = [t for t, c in sorted(expansion.items(), key=lambda x: -x[1])
                          if t != term][:5]
            if top_synonyms:
                table.add_row(term, ", ".join(top_synonyms))
        
        console.print(table)
        console.print("")
    
    # Generate plan (placeholder - would call LLM)
    if task:
        console.print(f"[bold]Task:[/bold] {task}")
        console.print("")
        console.print("[yellow]⚠️  Plan generation requires LLM integration.[/yellow]")
        console.print("For now, create [bold]DARKZLOOP_PLAN.md[/bold] manually.")
    else:
        console.print(f"[bold]Spec:[/bold] {spec_path}")
        console.print("")
        console.print("[yellow]⚠️  Plan generation requires LLM integration.[/yellow]")
        console.print("For now, create [bold]DARKZLOOP_PLAN.md[/bold] manually.")


@app.command()
def run(
    attended: bool = typer.Option(
        True, "--attended/--unattended",
        help="Require approval before each write operation"
    ),
    visualize: bool = typer.Option(
        False, "--visualize", "-v",
        help="Open visualization in browser"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Show what would happen without executing"
    ),
    resume: bool = typer.Option(
        False, "--resume",
        help="Resume from saved state"
    ),
    skip_git_check: bool = typer.Option(
        False, "--skip-git-check",
        help="Skip the git clean check (dangerous!)"
    ),
    backup: bool = typer.Option(
        True, "--backup/--no-backup",
        help="Create a backup branch before running"
    ),
):
    """
    🚀 Execute the implementation plan.
    
    Runs the FSM-controlled loop with quality gates and circuit breakers.
    
    Safety features:
    - Checks for uncommitted changes before running
    - Creates a backup branch by default
    - Supports dry-run mode to preview changes
    """
    require_init()
    config = load_config()
    
    # Check plan exists
    plan_path = config.project_root / config.local_config.plan_path
    if not plan_path.exists():
        console.print(f"[red]❌ Plan not found:[/red] {plan_path}")
        console.print("Run [bold]darkzloop plan[/bold] first.")
        raise typer.Exit(1)
    
    # === PRE-FLIGHT SAFETY CHECKS ===
    console.print("[bold]🛡️  Pre-flight Safety Checks[/bold]")
    console.print("")
    
    # Git status check
    if not skip_git_check:
        if not prompt_git_safety(console, config.project_root):
            console.print("[yellow]Aborted by user.[/yellow]")
            raise typer.Exit(0)
    else:
        console.print("[yellow]⚠️  Git check skipped (--skip-git-check)[/yellow]")
    
    # Create backup branch
    if backup and not dry_run:
        git_status = check_git_status(config.project_root)
        if git_status.is_repo:
            branch = create_backup_branch(config.project_root)
            if branch:
                console.print(f"[green]✓[/green] Created backup branch: [bold]{branch}[/bold]")
                console.print(f"   To restore: [dim]git checkout {branch}[/dim]")
            else:
                console.print("[yellow]⚠️  Could not create backup branch[/yellow]")
    
    console.print("")
    
    # === EXECUTION ===
    console.print(Panel(
        f"[bold green]🚀 Starting Darkzloop[/bold green]\n\n"
        f"Mode: {'Attended' if attended else 'Unattended'}\n"
        f"Plan: {plan_path.name}\n"
        f"Dry Run: {dry_run}",
        title="Execution",
        border_style="green"
    ))
    
    if dry_run:
        console.print("[yellow]Dry run mode - no changes will be made.[/yellow]")
        console.print("")
        
        # Set up dry run context
        ctx = DryRunContext()
        set_dry_run_context(ctx)
        
        # Show plan summary
        plan_content = plan_path.read_text()
        console.print(Syntax(plan_content[:2000], "markdown", theme="monokai"))
        
        # Clear dry run context
        set_dry_run_context(None)
        return
    
    # Import runtime
    try:
        from darkzloop.core.runtime import DarkzloopRuntime
        
        runtime_config = config.to_runtime_config()
        runtime = DarkzloopRuntime(runtime_config)

        # Set up agent executor from config
        from darkzloop.core.executors.shell import create_shell_executor
        from darkzloop.core.executors import ExecutorConfig, ExecutorType

        agent_config = config.agent

        if agent_config.mode == "shell":
            # Create shell executor with project root as cwd
            from darkzloop.core.executors import ExecutorConfig as ExecConfig, ExecutorType as ExecType
            from darkzloop.core.executors.shell import ShellExecutor
            from darkzloop.core.executors.presets import get_preset

            preset = get_preset(agent_config.command)
            exec_config = ExecConfig(
                type=ExecType.SHELL,
                command=agent_config.command,
                args=agent_config.args if agent_config.args else (preset.args if preset else []),
                cwd=str(config.project_root),
            )
            executor = ShellExecutor(exec_config)

            # Create wrapper function for runtime
            def shell_agent_executor(context: str, task: dict) -> tuple:
                """Execute via shell command."""
                response = executor.execute(context)
                if response.success:
                    return True, response.content, None
                else:
                    return False, "", response.error

            runtime.set_agent_executor(shell_agent_executor)
            console.print(f"[green]✓ Agent executor configured:[/green] {agent_config.command}")
        else:
            console.print("[yellow]⚠️  Agent executor not configured.[/yellow]")
            console.print("The runtime is ready but needs an LLM integration.")
            console.print("")
            console.print("To integrate:")
            console.print("  runtime.set_agent_executor(your_agent_function)")
            raise typer.Exit(1)

        # Actually run the loop
        console.print("")
        console.print("[bold]Starting execution loop...[/bold]")
        results = runtime.run()

        # Report results
        console.print("")
        if results:
            success_count = sum(1 for r in results if r.success)
            console.print(f"[green]✓ Completed {success_count}/{len(results)} iterations[/green]")
        else:
            console.print("[yellow]No iterations executed[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Error initializing runtime:[/red] {e}")
        raise typer.Exit(1)

    if visualize:
        viz_path = config.project_root / ".darkzloop" / "status.html"
        if viz_path.exists():
            webbrowser.open(f"file://{viz_path}")


@app.command()
def fix(
    issue: Optional[str] = typer.Argument(
        None,
        help="Description of the bug or feature to fix"
    ),
    files: Optional[str] = typer.Option(
        None, "--files", "-f",
        help="Comma-separated list of files to focus on"
    ),
    auto: bool = typer.Option(
        False, "--auto",
        help="Run unattended (no approval prompts)"
    ),
    skip_git_check: bool = typer.Option(
        False, "--skip-git-check",
        help="Skip the git clean check (dangerous!)"
    ),
    backup: bool = typer.Option(
        True, "--backup/--no-backup",
        help="Create a backup branch before running"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Show what would happen without executing"
    ),
):
    """
    ⚡ Fast Lane: One-shot fix without editing a spec file.
    
    Ideal for quick bug fixes and small features.
    
    Examples:
        darkzloop fix "Login button not responding"
        darkzloop fix "Add pagination to user list" --files src/api/users.rs
        darkzloop fix "Update dependencies" --auto
        darkzloop fix  # Interactive mode - prompts for issue
    
    Safety features:
    - Checks for uncommitted changes before running
    - Creates a backup branch by default
    - Supports dry-run mode to preview changes
    """
    require_init()
    config = load_config()
    
    # Interactive mode if no issue provided
    if not issue:
        console.print("")
        console.print("[bold]⚡ Fast Lane Fix[/bold]")
        console.print("")
        console.print("[bold]Describe the bug or feature you want to fix:[/bold]")
        console.print("[dim](Be specific - e.g., 'Login button not responding on mobile Safari')[/dim]")
        console.print("")
        
        issue = Prompt.ask("What needs fixing?")
        
        if not issue.strip():
            console.print("[red]No issue provided. Aborting.[/red]")
            raise typer.Exit(1)
        
        console.print("")
        
        # Ask about mode
        if not auto:
            run_auto = Confirm.ask("Run unattended (fully autonomous)?", default=False)
            auto = run_auto
        
        console.print("")
    
    console.print(Panel(
        f"[bold yellow]⚡ Fast Lane Fix[/bold yellow]\n\n"
        f"Issue: {issue}",
        title="Quick Fix",
        border_style="yellow"
    ))
    
    # === PRE-FLIGHT SAFETY CHECKS ===
    console.print("")
    console.print("[bold]🛡️  Pre-flight Safety Checks[/bold]")
    console.print("")
    
    # Git status check
    if not skip_git_check:
        if not prompt_git_safety(console, config.project_root):
            console.print("[yellow]Aborted by user.[/yellow]")
            raise typer.Exit(0)
    else:
        console.print("[yellow]⚠️  Git check skipped (--skip-git-check)[/yellow]")
    
    # Create backup branch
    if backup and not dry_run:
        git_status = check_git_status(config.project_root)
        if git_status.is_repo:
            branch = create_backup_branch(config.project_root, prefix="darkzloop-fix")
            if branch:
                console.print(f"[green]✓[/green] Created backup branch: [bold]{branch}[/bold]")
            else:
                console.print("[yellow]⚠️  Could not create backup branch[/yellow]")
    
    console.print("")
    
    # === SEMANTIC EXPANSION ===
    # Import components
    from darkzloop.core.semantic import SemanticExpander
    
    # 1. Semantic expansion
    console.print("[bold]🔍 Analyzing issue...[/bold]")
    expander = SemanticExpander(config.project_root)
    
    import re
    terms = [w for w in re.findall(r'\b[a-z]{3,}\b', issue.lower())
            if w not in {'the', 'and', 'for', 'with', 'fix', 'bug', 'add', 'update'}]
    
    all_synonyms = set()
    for term in terms:
        expansion = expander.expand(term)
        all_synonyms.update(expansion.keys())
    
    console.print(f"   Keywords: [cyan]{', '.join(terms)}[/cyan]")
    console.print(f"   Expanded: [green]{', '.join(list(all_synonyms)[:10])}[/green]")
    
    # 2. Find relevant files
    console.print("\n[bold]📁 Finding relevant files...[/bold]")
    
    if files:
        target_files = [f.strip() for f in files.split(",")]
    else:
        matches = expander.search_files(terms)
        target_files = [m.path for m in matches[:5]]
    
    if target_files:
        for f in target_files:
            console.print(f"   [green]✓[/green] {f}")
    else:
        console.print("   [yellow]No matching files found. Agent will search.[/yellow]")
    
    # 3. Generate temporary spec
    console.print("\n[bold]📝 Generating temporary spec...[/bold]")
    
    temp_spec = f"""# Quick Fix Specification

## Objective

{issue}

## Target Files

{chr(10).join(f"- {f}" for f in target_files) if target_files else "- Agent will determine"}

## Keywords

{', '.join(terms)}

## Acceptance Criteria

- [ ] Issue is resolved
- [ ] All tests pass
- [ ] No regressions introduced
"""
    
    temp_spec_path = config.project_root / ".darkzloop" / "quick_spec.md"
    temp_spec_path.parent.mkdir(exist_ok=True)
    
    if not dry_run:
        temp_spec_path.write_text(temp_spec)
        console.print(f"   Created: {temp_spec_path}")
    else:
        console.print(f"   Would create: {temp_spec_path}")
    
    # 4. Generate temporary plan
    console.print("\n[bold]📋 Generating task plan...[/bold]")
    
    temp_plan = f"""# Quick Fix Plan

Generated: {datetime.now().isoformat()}

## Task 1.1: Investigate Issue

**Description:** Understand the root cause of: "{issue}"

**Files to Read:**
{chr(10).join(f"- {f}" for f in target_files) if target_files else "- Search codebase"}

**Acceptance Criteria:** Root cause identified

---

## Task 1.2: Implement Fix

**Description:** Fix the issue

**Files to Modify:**
{chr(10).join(f"- {f}" for f in target_files) if target_files else "- To be determined"}

**Acceptance Criteria:** Issue resolved, tests pass
"""
    
    temp_plan_path = config.project_root / ".darkzloop" / "quick_plan.md"
    
    if not dry_run:
        temp_plan_path.write_text(temp_plan)
        console.print(f"   Created: {temp_plan_path}")
    else:
        console.print(f"   Would create: {temp_plan_path}")
    
    # 5. Ready to execute
    console.print("")
    
    if dry_run:
        console.print(Panel(
            "[yellow]DRY RUN - No changes made[/yellow]\n\n"
            f"Would analyze: {issue}\n"
            f"Would target: {len(target_files)} files\n"
            f"Would create temp spec and plan",
            title="Dry Run Summary",
            border_style="yellow"
        ))
    else:
        console.print(Panel(
            "[green]✅ Ready to execute[/green]\n\n"
            f"Mode: {'Unattended' if auto else 'Attended'}\n\n"
            "Run [bold]darkzloop run[/bold] to execute, or review the generated plan first.",
            title="Next Steps",
            border_style="green"
        ))
    
    # In a full implementation, we would:
    # - Initialize the runtime with temp spec/plan
    # - Set up the agent executor
    # - Run the loop
    # - Learn from success (update glossary)


@app.command()
def graph(
    format: str = typer.Option(
        "ascii", "--format", "-f",
        help="Output format: ascii, html, mermaid"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output file path"
    ),
):
    """
    📊 View the task DAG visualization.
    
    Shows task dependencies, completion status, and blockers.
    """
    require_init()
    config = load_config()
    
    # Check if state exists
    state_path = config.project_root / ".darkzloop" / "state.json"
    
    if not state_path.exists():
        console.print("[yellow]No execution state found.[/yellow]")
        console.print("Run [bold]darkzloop run[/bold] to start execution.")
        return
    
    # Load and display visualization
    try:
        from darkzloop.core.visualize import Visualizer, render_ascii, render_html
        
        viz = Visualizer(config.project_root)
        viz.load()
        
        if format == "ascii":
            result = viz.get_human_view("ascii")
            console.print(result)
        elif format == "html":
            result = viz.get_human_view("html")
            if output:
                output.write_text(result)
                console.print(f"Saved to: {output}")
                webbrowser.open(f"file://{output}")
            else:
                default_path = config.project_root / ".darkzloop" / "graph.html"
                default_path.write_text(result)
                console.print(f"Saved to: {default_path}")
                webbrowser.open(f"file://{default_path}")
        elif format == "mermaid":
            result = viz.get_human_view("mermaid")
            console.print(Syntax(result, "text", theme="monokai"))
            if output:
                output.write_text(result)
        
    except Exception as e:
        console.print(f"[red]Error loading visualization:[/red] {e}")


@app.command()
def status():
    """
    📈 Show current loop status.
    
    Displays FSM state, task progress, and circuit breaker status.
    """
    require_init()
    config = load_config()
    
    state_path = config.project_root / ".darkzloop" / "state.json"
    
    if not state_path.exists():
        console.print("[yellow]No execution state found.[/yellow]")
        console.print("Run [bold]darkzloop run[/bold] to start execution.")
        return
    
    try:
        with open(state_path) as f:
            state = json.load(f)
        
        fsm = state.get("fsm", {})
        
        table = Table(title="Loop Status")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("State", fsm.get("current_state", "unknown"))
        table.add_row("Iteration", str(fsm.get("iteration", 0)))
        table.add_row("Consecutive Failures", str(fsm.get("consecutive_failures", 0)))
        table.add_row("Last Updated", state.get("timestamp", "unknown"))
        
        console.print(table)
        
        # Task retries
        task_retries = state.get("task_retries", {})
        if task_retries:
            console.print("")
            retry_table = Table(title="Task Retry Counts")
            retry_table.add_column("Task", style="cyan")
            retry_table.add_column("Retries", style="yellow")
            
            for task_id, count in task_retries.items():
                retry_table.add_row(task_id, str(count))
            
            console.print(retry_table)
        
    except Exception as e:
        console.print(f"[red]Error loading state:[/red] {e}")


# =============================================================================
# Config Subcommand
# =============================================================================

config_app = typer.Typer(help="⚙️  Manage global configuration")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show():
    """Show current configuration."""
    global_config = GlobalConfig.load()
    
    console.print("[bold]Global Configuration[/bold]")
    console.print(f"  Path: {get_global_config_path()}")
    console.print("")
    
    table = Table()
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    # Mode
    table.add_row("Mode", global_config.agent.mode.upper())
    
    if global_config.agent.mode == "shell":
        table.add_row("Command", global_config.agent.command)
        table.add_row("Args", " ".join(global_config.agent.args))
    else:
        table.add_row("Provider", global_config.agent.provider)
        table.add_row("Model", global_config.agent.model)
        table.add_row("API Key", "***" if global_config.agent.api_key else "[red]Not set[/red]")
    
    table.add_row("Default Mode", "Attended" if global_config.default_attended else "Unattended")
    table.add_row("Auto Commit", "Yes" if global_config.default_auto_commit else "No")
    table.add_row("Editor", global_config.editor)
    
    console.print(table)


@config_app.command("set")
def config_set(
    api_key: Optional[str] = typer.Option(
        None, "--api-key",
        help="Set API key for LLM provider"
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider",
        help="Set LLM provider (anthropic, openai)"
    ),
    model: Optional[str] = typer.Option(
        None, "--model",
        help="Set model name"
    ),
    attended: Optional[bool] = typer.Option(
        None, "--attended/--unattended",
        help="Set default execution mode"
    ),
):
    """Set configuration values."""
    config = GlobalConfig.load()
    changed = False
    
    if api_key:
        config.agent.api_key = api_key
        console.print("[green]✓[/green] API key saved")
        changed = True
    
    if provider:
        config.agent.provider = provider
        console.print(f"[green]✓[/green] Provider set to: {provider}")
        changed = True
    
    if model:
        config.agent.model = model
        console.print(f"[green]✓[/green] Model set to: {model}")
        changed = True
    
    if attended is not None:
        config.default_attended = attended
        console.print(f"[green]✓[/green] Default mode: {'Attended' if attended else 'Unattended'}")
        changed = True
    
    if changed:
        config.save()
        console.print("")
        console.print(f"Configuration saved to: {get_global_config_path()}")
    else:
        console.print("No changes made. Use --help to see options.")


@config_app.command("init")
def config_init():
    """Initialize global configuration interactively."""
    console.print("[bold]Darkzloop Configuration Setup[/bold]")
    console.print("")
    
    config = GlobalConfig.load()
    
    # Provider
    provider = Prompt.ask(
        "LLM Provider",
        choices=["anthropic", "openai"],
        default=config.agent.provider
    )
    config.agent.provider = provider
    
    # Model
    if provider == "anthropic":
        default_model = "claude-sonnet-4-20250514"
    else:
        default_model = "gpt-4"
    
    model = Prompt.ask(
        "Model",
        default=config.agent.model or default_model
    )
    config.agent.model = model
    
    # API Key
    current_key = get_api_key(provider)
    if current_key:
        console.print(f"[green]✓[/green] API key already set (from env or config)")
    else:
        api_key = Prompt.ask(
            f"API Key for {provider}",
            password=True
        )
        if api_key:
            config.agent.api_key = api_key
    
    # Defaults
    config.default_attended = Confirm.ask(
        "Default to attended mode?",
        default=True
    )
    
    config.default_auto_commit = Confirm.ask(
        "Auto-commit on success?",
        default=True
    )
    
    config.save()
    
    console.print("")
    console.print("[green]✓ Configuration saved![/green]")
    console.print(f"  Path: {get_global_config_path()}")


@config_app.command("native")
def config_native(
    tool: Optional[str] = typer.Argument(
        None,
        help="Tool preset: claude, ollama, gh-copilot, llm, llm-gpt4"
    ),
):
    """
    🔌 Configure native CLI tool (BYOA mode).
    
    Use your existing subscriptions without API keys!
    
    Examples:
        darkzloop config native claude      # Use Claude CLI
        darkzloop config native ollama      # Use local Ollama
        darkzloop config native gh-copilot  # Use GitHub Copilot
        darkzloop config native llm         # Use Simon Willison's llm
    
    This is the recommended setup for most users.
    """
    try:
        from darkzloop.core.executors.shell import (
            NATIVE_PRESETS, detect_available_tools, get_preset
        )
    except ImportError:
        console.print("[red]Error: Executor module not found[/red]")
        raise typer.Exit(1)
    
    config = GlobalConfig.load()
    
    if not tool:
        # Interactive selection
        console.print("[bold]🔌 Native Tool Setup (Bring Your Own Auth)[/bold]")
        console.print("")
        console.print("Darkzloop can use your existing CLI tools instead of API keys.")
        console.print("")
        
        # Detect available tools
        available = detect_available_tools()
        
        console.print("[bold]Available tools:[/bold]")
        for i, (name, display_name, cmd) in enumerate(available, 1):
            console.print(f"  {i}. {display_name} ({cmd})")
        
        console.print("")
        console.print("[bold]All presets:[/bold]")
        for name, preset in NATIVE_PRESETS.items():
            status = "[green]✓[/green]" if any(n == name for n, _, _ in available) else "[dim]○[/dim]"
            console.print(f"  {status} {name}: {preset.name}")
        
        console.print("")
        tool = Prompt.ask(
            "Select tool",
            default="claude" if any(n == "claude" for n, _, _ in available) else "ollama"
        )
    
    # Get preset
    preset = get_preset(tool)
    
    if not preset:
        console.print(f"[yellow]Unknown preset: {tool}[/yellow]")
        console.print("Using custom command mode.")
        config.agent.mode = "shell"
        config.agent.command = tool
        config.agent.args = []
    else:
        config.agent.mode = "shell"
        config.agent.command = preset.command
        config.agent.args = preset.args
        
        console.print(f"[green]✓[/green] Configured: {preset.name}")
        console.print(f"   Command: {preset.command} {' '.join(preset.args)}")
        console.print("")
        console.print(f"[dim]Auth hint: {preset.auth_command}[/dim]")
    
    config.save()
    
    console.print("")
    console.print("[green]✓ Configuration saved![/green]")
    console.print("")
    console.print("Test with: [bold]darkzloop doctor[/bold]")


@config_app.command("api")
def config_api(
    provider: str = typer.Argument(
        "anthropic",
        help="API provider: anthropic, openai"
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k",
        help="API key (or set via environment)"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model name"
    ),
):
    """
    🔑 Configure direct API access.
    
    Use this if you have API keys and want direct SDK access.
    
    Examples:
        darkzloop config api anthropic --api-key sk-ant-xxx
        darkzloop config api openai --model gpt-4o
    """
    config = GlobalConfig.load()
    
    config.agent.mode = "api"
    config.agent.provider = provider
    
    if api_key:
        config.agent.api_key = api_key
    
    if model:
        config.agent.model = model
    elif provider == "anthropic":
        config.agent.model = "claude-sonnet-4-20250514"
    elif provider == "openai":
        config.agent.model = "gpt-4o"
    
    config.save()
    
    console.print(f"[green]✓[/green] Configured API mode: {provider}")
    console.print(f"   Model: {config.agent.model}")
    
    if not api_key and not get_api_key(provider):
        env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
        console.print(f"[yellow]⚠️  No API key set. Set {env_var} or use --api-key[/yellow]")


# =============================================================================
# Version and Debug
# =============================================================================

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V",
        help="Show version and exit"
    ),
    debug: bool = typer.Option(
        False, "--debug",
        help="Enable debug mode with full stack traces"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Enable verbose output"
    ),
):
    """
    Darkzloop: Reliable Autonomous Coding Loops with Semantic Memory

    A production-grade agent orchestration framework that prevents common
    agent failures through FSM control, semantic expansion, and circuit breakers.

    Quick start:
        darkzloop init              # Initialize in a project
        darkzloop plan              # Generate task plan
        darkzloop run               # Execute with safety checks
        darkzloop fix "bug desc"    # One-shot fixes
    """
    if version:
        print_version()
        raise typer.Exit()
    
    # Set up debugging
    if debug:
        enable_traceback()
        setup_debug_logging(debug=True)
        console.print("[dim]Debug mode enabled[/dim]")
    elif verbose:
        setup_debug_logging(verbose=True)


# =============================================================================
# Doctor Command (Environment Check)
# =============================================================================

@app.command()
def doctor():
    """
    🩺 Check environment and configuration.
    
    Verifies that all required tools are installed and configured.
    """
    console.print("[bold]🩺 Darkzloop Doctor[/bold]")
    console.print("")
    
    all_ok = print_environment_check(console)
    
    console.print("")
    
    # Check executor configuration
    global_config = GlobalConfig.load()
    console.print("[bold]Executor Configuration[/bold]")
    console.print(f"  Mode: {global_config.agent.mode.upper()}")
    
    if global_config.agent.mode == "shell":
        cmd = global_config.agent.command
        console.print(f"  Command: {cmd}")
        
        # Check if command exists
        import shutil
        import subprocess
        
        if not shutil.which(cmd):
            console.print(f"  [red]✗ Command not found in PATH[/red]")
            all_ok = False
        else:
            console.print(f"  [green]✓[/green] Command found")
            
            # Tool-specific auth checks
            try:
                if cmd == "claude":
                    # Check Claude CLI login status
                    result = subprocess.run(
                        ["claude", "whoami"],
                        capture_output=True,
                        timeout=10,
                        text=True,
                    )
                    if result.returncode == 0:
                        # Extract username if available
                        who = result.stdout.strip().split('\n')[0][:50]
                        console.print(f"  [green]✓[/green] Authenticated: {who}")
                    else:
                        console.print(f"  [yellow]⚠️  Not logged in. Run: claude login[/yellow]")
                        all_ok = False
                        
                elif cmd == "gh":
                    # Check GitHub CLI auth
                    result = subprocess.run(
                        ["gh", "auth", "status"],
                        capture_output=True,
                        timeout=10,
                        text=True,
                    )
                    if result.returncode == 0:
                        console.print(f"  [green]✓[/green] GitHub authenticated")
                    else:
                        console.print(f"  [yellow]⚠️  Not logged in. Run: gh auth login[/yellow]")
                        all_ok = False
                        
                elif cmd == "ollama":
                    # Check if Ollama server is running
                    result = subprocess.run(
                        ["ollama", "list"],
                        capture_output=True,
                        timeout=10,
                        text=True,
                    )
                    if result.returncode == 0:
                        models = [l.split()[0] for l in result.stdout.strip().split('\n')[1:] if l.strip()]
                        if models:
                            console.print(f"  [green]✓[/green] Ollama running. Models: {', '.join(models[:3])}")
                        else:
                            console.print(f"  [yellow]⚠️  No models installed. Run: ollama pull llama3.1[/yellow]")
                    else:
                        console.print(f"  [yellow]⚠️  Ollama not running. Run: ollama serve[/yellow]")
                        all_ok = False
                        
                elif cmd == "llm":
                    # Check llm CLI
                    result = subprocess.run(
                        ["llm", "models", "list"],
                        capture_output=True,
                        timeout=10,
                        text=True,
                    )
                    if result.returncode == 0:
                        console.print(f"  [green]✓[/green] llm CLI configured")
                    else:
                        console.print(f"  [yellow]⚠️  llm CLI issue. Run: llm keys set anthropic[/yellow]")
                        
                elif cmd == "aider":
                    result = subprocess.run(
                        ["aider", "--version"],
                        capture_output=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        console.print(f"  [green]✓[/green] Aider available")
                    else:
                        console.print(f"  [yellow]⚠️  Aider not working[/yellow]")
                        all_ok = False
                else:
                    # Generic check - just verify command runs
                    console.print(f"  [dim]Custom command - no specific auth check[/dim]")
                    
            except subprocess.TimeoutExpired:
                console.print(f"  [yellow]⚠️  Command timed out[/yellow]")
                all_ok = False
            except Exception as e:
                console.print(f"  [red]✗ Error checking: {e}[/red]")
                all_ok = False
    else:
        # API mode
        provider = global_config.agent.provider
        api_key = get_api_key(provider)
        console.print(f"  Provider: {provider}")
        console.print(f"  Model: {global_config.agent.model}")
        if api_key:
            console.print(f"  [green]✓[/green] API key configured")
        else:
            env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
            console.print(f"  [red]✗[/red] No API key. Set {env_var}")
            all_ok = False
    
    console.print("")
    
    # Check local config if in a project
    if is_initialized():
        config = load_config()
        console.print("[bold]Project Configuration[/bold]")
        console.print(f"  Project: {config.local_config.project_name}")
        console.print(f"  Type: {config.local_config.project_type}")
        console.print(f"  Spec: {config.local_config.spec_path}")
        console.print(f"  Plan: {config.local_config.plan_path}")
        
        # Check gates
        gates = []
        if config.local_config.tier1.enabled:
            gates.extend(config.local_config.tier1.commands)
        if config.local_config.tier2.enabled:
            gates.extend(config.local_config.tier2.commands)
        
        console.print(f"  Gates: {len(gates)} configured")
        
        # Verify gate commands exist
        import shutil
        for gate_cmd in gates[:5]:  # Check first 5
            cmd_name = gate_cmd.split()[0]
            if shutil.which(cmd_name):
                console.print(f"    [green]✓[/green] {cmd_name}")
            else:
                console.print(f"    [yellow]⚠️[/yellow] {cmd_name} not found")
    else:
        console.print("[yellow]Not in a darkzloop project[/yellow]")
        console.print("Run [bold]darkzloop init[/bold] to initialize")
    
    console.print("")
    if all_ok:
        console.print("[green]✓ All systems operational. Ready for flight! 🚀[/green]")
    else:
        console.print("[yellow]⚠️  Some checks failed. See above for details.[/yellow]")


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    app()
