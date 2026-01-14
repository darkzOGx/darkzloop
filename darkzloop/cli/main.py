"""
Darkzloop CLI - Zero Config Entry Point

Usage:
    darkzloop "fix the login bug"              # Just works
    darkzloop run "fix the login bug"          # Explicit run
    darkzloop "task" --backend ollama          # Override backend
    darkzloop doctor                           # Check environment
"""

import sys
import os
import json
import subprocess
import shutil
import glob
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.box import ROUNDED

from darkzloop.cli.detection import detect_configuration, ProjectConfig

app = typer.Typer(
    name="darkzloop",
    help="Reliable autonomous coding. Just tell it what to fix.",
    add_completion=False,
    no_args_is_help=False,
)
console = Console()


# =============================================================================
# Backend Detection
# =============================================================================

def detect_backend() -> Tuple[str, List[str]]:
    """Auto-detect available LLM backend."""
    if shutil.which("claude"):
        return "claude", ["--dangerously-skip-permissions", "--print", "--output-format", "json"]
    if shutil.which("ollama"):
        return "ollama", ["run", "llama3.1"]
    if shutil.which("gh"):
        return "gh", ["copilot", "suggest"]
    if shutil.which("llm"):
        return "llm", []
    return "", []


def get_backend_args(backend: str) -> List[str]:
    """Get default args for a backend."""
    return {
        "claude": ["--dangerously-skip-permissions", "--print", "--output-format", "json"],
        "ollama": ["run", "llama3.1"],
        "gh": ["copilot", "suggest"],
        "llm": [],
    }.get(backend, [])


# =============================================================================
# Git Safety
# =============================================================================

def ensure_git_clean() -> Tuple[bool, List[str]]:
    """Check for uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return True, []
        changed = [line[3:] for line in result.stdout.strip().split("\n") if line]
        return len(changed) == 0, changed
    except Exception:
        return True, []


def create_backup() -> Optional[str]:
    """Create a backup branch."""
    name = f"darkzloop-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    try:
        subprocess.run(["git", "branch", name], capture_output=True)
        return name
    except Exception:
        return None


# =============================================================================
# Run State (Crash Recovery)
# =============================================================================

STATE_DIR = Path(".darkzloop")
STATE_FILE = STATE_DIR / "run_state.json"


def save_state(task: str, iteration: int, state: str):
    STATE_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps({
        "task": task, "iteration": iteration, "state": state
    }))


def load_state() -> Optional[dict]:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return None


def clear_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()


# =============================================================================
# Context Reminder (The Key Feature)
# =============================================================================

def render_context_reminder(state: str, iteration: int, fails: int, tasks_done: int = 0):
    """Render the compressed state summary."""
    icons = {
        "planning": "🔵", "executing": "🟡", "testing": "🟡",
        "observe": "👀", "critique": "🧠", "done": "🟢", "failed": "🔴"
    }
    icon = icons.get(state.lower(), "⚪")
    console.print(f"{icon} [bold][{state.upper()}][/bold] iter={iteration} fails={fails}")


# =============================================================================
# Agent Execution
# =============================================================================

def run_agent(cmd: str, args: List[str], prompt: str, cwd: Path) -> Tuple[bool, str]:
    """Execute the agent command with prompt via stdin to avoid shell escaping issues."""
    try:
        # Build command as a list (no shell=True needed)
        # On Windows, we need to find the actual executable
        import shutil
        cmd_path = shutil.which(cmd)
        if not cmd_path:
            return False, f"Command not found: {cmd}"
        
        # Use Rich spinner to show activity while Claude processes
        with console.status("[bold cyan]🔄 Darkz Looping...[/bold cyan]", spinner="dots") as status:
            # Pass prompt via stdin to bypass shell escaping entirely
            # Claude with --print mode reads from stdin when no prompt arg is given
            result = subprocess.run(
                [cmd_path] + args,
                input=prompt,  # Prompt goes to stdin - no escaping needed
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300,
                encoding='utf-8',
                errors='replace'
            )
        
        # Combine stdout and stderr for complete output
        output = result.stdout + result.stderr
        
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Timeout after 300s"
    except FileNotFoundError as e:
        return False, f"Command not found: {e}"
    except Exception as e:
        return False, str(e)


def run_gate(cmd: str, cwd: Path) -> Tuple[bool, str]:
    """Run a quality gate command."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, 
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace'  # UTF-8 for consistent encoding
        )
        return result.returncode == 0, result.stdout or result.stderr
    except Exception as e:
        return False, str(e)


# =============================================================================
# Main Loop
# =============================================================================

def run_loop(task: str, backend: str, backend_args: List[str], config: ProjectConfig) -> bool:
    """Execute the FSM loop."""
    from darkzloop.core.fsm import FSMContext, LoopState
    
    cwd = Path.cwd()
    fsm = FSMContext(max_iterations=10, max_consecutive_failures=3)
    iteration = 0
    
    console.print(Panel(f"[bold]{task}[/bold]", title="🎯 Task", border_style="blue"))
    
    while not fsm.is_terminal() and iteration < 10:
        iteration += 1
        
        # Check if we should stop (e.g., max failures reached)
        should_halt, halt_reason = fsm.should_stop()
        if should_halt:
            console.print(f"[yellow]Stopping: {halt_reason}[/yellow]")
            break
        
        try:
            # PLAN
            fsm.transition(LoopState.PLAN, "Planning")
            render_context_reminder("planning", iteration, fsm.consecutive_failures)
            
            # Build RALPH context with FSM state and Mermaid diagram
            mermaid_diagram = fsm.to_mermaid()
            fsm_summary = fsm.get_compact_summary()
            
            context = f"""# DARKZLOOP AGENT CONTEXT
{fsm_summary}

## FSM State Diagram
```mermaid
{mermaid_diagram}
```

## Current Task
{task}

## Instructions
You are inside a Ralph Wiggum loop. Your changes persist between iterations.
- Make targeted, focused changes to accomplish the task
- Use file editing tools to modify code
- Run tests/commands to verify your changes work
- The loop will continue until the task is complete or max iterations reached

Iteration {iteration} of 10. Previous failures: {fsm.consecutive_failures}
"""

            save_state(task, iteration, "execute")
            
            # EXECUTE
            fsm.transition(LoopState.EXECUTE, "Executing")
            render_context_reminder("executing", iteration, fsm.consecutive_failures)
            
            success, output = run_agent(backend, backend_args, context, cwd)
            
            if not success:
                console.print(f"[red dim]Agent error: {output[:300] if output else '(no output)'}[/red dim]")
                fsm.fail_task(f"Agent error: {output[:100]}")
                render_context_reminder("failed", iteration, fsm.consecutive_failures)
                continue
            
            if output:
                console.print(Panel(output[:1500] + ("..." if len(output) > 1500 else ""),
                                   title="Agent Response", border_style="green"))
            
            # OBSERVE
            fsm.transition(LoopState.OBSERVE, "Observing")
            
            # Run Tier 1 gates (fast)
            gates_passed = True
            for gate in config.tier1_gates:
                render_context_reminder("testing", iteration, fsm.consecutive_failures)
                console.print(f"  Running: {gate}")
                passed, gate_output = run_gate(gate, cwd)
                if not passed:
                    console.print(f"  [red]✗ {gate} failed[/red]")
                    gates_passed = False
                    break
                console.print(f"  [green]✓ {gate}[/green]")
            
            if not gates_passed:
                fsm.fail_task("Gate failed")
                continue
            
            # CRITIQUE -> CHECKPOINT
            fsm.transition(LoopState.CRITIQUE, "Validating")
            fsm.transition(LoopState.CHECKPOINT, "Complete")
            
            render_context_reminder("done", iteration, fsm.consecutive_failures, tasks_done=1)
            break
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            fsm.fail_task(str(e))
    
    if fsm.current_state == LoopState.CHECKPOINT or fsm.current_state == LoopState.COMPLETE:
        clear_state()
        return True
    return False


# =============================================================================
# CLI - Main execution function
# =============================================================================

def execute_task(
    task: str,
    backend: Optional[str] = None,
    unattended: bool = False,
    no_gates: bool = False,
    workers: int = 1,
):
    """Execute a task. If workers > 1, uses parallel batch processing."""
    # Auto-detect project
    config = detect_configuration()
    
    # Skip gates if requested
    if no_gates:
        config.tier1_gates = []
        config.tier2_gates = []
        console.print("[yellow]⚠️ Quality gates disabled[/yellow]")
    elif config.type == "unknown" and not unattended:
        console.print("[yellow]⚠️ Could not detect project type. Running without gates.[/yellow]")
    else:
        console.print(f"[green]✓ Detected: {config.type.capitalize()}[/green]")
    
    # Auto-detect or use specified backend
    if backend:
        backend_cmd = backend
        backend_args = get_backend_args(backend)
    else:
        backend_cmd, backend_args = detect_backend()
    
    if not backend_cmd:
        console.print("[red]❌ No LLM backend found.[/red]")
        console.print("\nInstall: claude, ollama, or gh copilot")
        raise typer.Exit(1)
    
    console.print(f"[dim]Backend: {backend_cmd}[/dim]")
    
    # Git safety
    if not unattended:
        is_clean, dirty = ensure_git_clean()
        if not is_clean:
            console.print(f"\n[yellow]⚠️ Uncommitted changes in {len(dirty)} files[/yellow]")
            if not Confirm.ask("Continue anyway?", default=False):
                raise typer.Exit(0)
            backup = create_backup()
            if backup:
                console.print(f"[green]✓ Backup: {backup}[/green]")
    
    console.print()
    
    # Initialize results for session summary
    results = {"success": 0, "failed": 0}
    
    # Parallel mode: auto-detect files and process in parallel
    if workers > 1:
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        
        # Find source files
        extensions = {
            "python": ["*.py"],
            "node": ["*.js", "*.ts", "*.jsx", "*.tsx"],
            "rust": ["*.rs"],
            "go": ["*.go"],
        }.get(config.type, ["*.py", "*.js", "*.ts"])
        
        files = []
        for ext in extensions:
            files.extend(glob.glob(f"**/{ext}", recursive=True))
        
        # Filter out common non-source directories
        files = [f for f in files if not any(x in f for x in ['node_modules', '__pycache__', '.git', 'venv', '.venv', 'dist', 'build'])]
        
        if not files:
            console.print("[yellow]No source files found for parallel processing[/yellow]")
            console.print("[dim]Falling back to single-threaded mode...[/dim]")
            success = run_loop(task, backend_cmd, backend_args, config)
        else:
            console.print(f"[bold]⚡ Parallel Mode: {len(files)} files with {workers} workers[/bold]\n")
            
            cwd = Path.cwd()
            results = {"success": 0, "failed": 0}
            
            def process_file(filepath: str) -> Tuple[str, bool, str]:
                try:
                    prompt = f"Fix this file: {filepath}\nTask: {task}\nMake targeted fixes."
                    success, output = run_agent(backend_cmd, backend_args, prompt, cwd)
                    return filepath, success, output[:100] if output else ""
                except Exception as e:
                    return filepath, False, str(e)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task_id = progress.add_task("[cyan]Darkz Looping...", total=len(files))
                
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {executor.submit(process_file, f): f for f in files}
                    
                    for future in as_completed(futures):
                        filepath, ok, _ = future.result()
                        filename = os.path.basename(filepath)
                        
                        if ok:
                            results["success"] += 1
                            progress.console.print(f"  [green]✓[/green] {filename}")
                        else:
                            results["failed"] += 1
                            progress.console.print(f"  [red]✗[/red] {filename}")
                        
                        progress.advance(task_id)
            
            console.print(f"\n[bold]Results:[/bold]")
            console.print(f"  [green]✓ Success:[/green] {results['success']}")
            console.print(f"  [red]✗ Failed:[/red] {results['failed']}")
            total = results['success'] + results['failed']
            if total > 0:
                rate = (results['success'] / total) * 100
                console.print(f"  [cyan]Success Rate:[/cyan] {rate:.1f}%")
            success = results["failed"] == 0
    else:
        # Standard single-threaded mode
        success = run_loop(task, backend_cmd, backend_args, config)
    
    # Session Summary: Show all changes made with premium styling
    console.print()
    console.print(Panel.fit(
        "[bold white]📊 SESSION SUMMARY[/bold white]",
        border_style="cyan",
        padding=(0, 2)
    ))
    
    # Get git changes
    changed_files = []
    try:
        # Check for unstaged changes first
        diff_result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, cwd=Path.cwd(),
            encoding='utf-8', errors='replace'
        )
        if diff_result.stdout.strip():
            changed_files = diff_result.stdout.strip().split('\n')
        
        # Also check staged changes
        diff_staged = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            capture_output=True, text=True, cwd=Path.cwd(),
            encoding='utf-8', errors='replace'
        )
        if diff_staged.stdout.strip():
            changed_files.extend(diff_staged.stdout.strip().split('\n'))
        
        changed_files = list(set(changed_files))  # Remove duplicates
    except Exception:
        pass
    
    # Build stats table
    stats_table = Table(box=ROUNDED, show_header=False, border_style="dim")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="white")
    
    if workers > 1:
        total = results.get('success', 0) + results.get('failed', 0)
        success_count = results.get('success', 0)
        failed_count = results.get('failed', 0)
        rate = (success_count / total * 100) if total > 0 else 0
        
        # ASCII progress bar for success rate
        bar_width = 20
        filled = int(bar_width * rate / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        stats_table.add_row("Files Processed", str(total))
        stats_table.add_row("✓ Successful", f"[green]{success_count}[/green]")
        stats_table.add_row("✗ Failed", f"[red]{failed_count}[/red]")
        stats_table.add_row("Success Rate", f"[cyan]{bar}[/cyan] {rate:.1f}%")
    
    stats_table.add_row("Files Changed", str(len(changed_files)) if changed_files else "0")
    
    console.print(stats_table)
    
    # Show changed files in a nice table
    if changed_files:
        console.print()
        files_table = Table(title="[bold]Modified Files[/bold]", box=ROUNDED, border_style="green")
        files_table.add_column("#", style="dim", width=4)
        files_table.add_column("File", style="white")
        files_table.add_column("Status", style="green", width=10)
        
        for i, f in enumerate(changed_files[:15], 1):  # Show max 15 files
            files_table.add_row(str(i), f, "Modified")
        
        if len(changed_files) > 15:
            files_table.add_row("...", f"[dim]+{len(changed_files) - 15} more[/dim]", "")
        
        console.print(files_table)
    
    console.print()
    if success:
        console.print("\n[bold green]✓ Done![/bold green]")
    else:
        console.print("\n[yellow]Run ended with issues.[/yellow]")
        raise typer.Exit(1)


# =============================================================================
# CLI Commands
# =============================================================================

@app.command("run")
def run_cmd(
    task: str = typer.Argument(..., help="What to fix or build"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b", help="LLM backend"),
    unattended: bool = typer.Option(False, "--unattended", "-y", help="Skip prompts"),
    no_gates: bool = typer.Option(False, "--no-gates", help="Skip quality gates"),
    workers: int = typer.Option(1, "--workers", "-w", help="Parallel workers (auto-detects files)"),
):
    """🚀 Run a task."""
    execute_task(task, backend, unattended, no_gates, workers)


@app.command("doctor")
def doctor():
    """🩺 Check environment."""
    console.print("\n[bold]Darkzloop Doctor[/bold]\n")
    
    # Backend
    cmd, _ = detect_backend()
    if cmd:
        console.print(f"[green]✓[/green] Backend: {cmd}")
    else:
        console.print("[red]✗[/red] No backend found")
    
    # Project
    config = detect_configuration()
    if config.type != "unknown":
        console.print(f"[green]✓[/green] Project: {config.type.capitalize()}")
        if config.tier1_gates:
            console.print(f"  Tier 1: {config.tier1_gates}")
        if config.tier2_gates:
            console.print(f"  Tier 2: {config.tier2_gates}")
    else:
        console.print("[yellow]⚠[/yellow] Project type unknown")
    
    # Git
    is_clean, dirty = ensure_git_clean()
    console.print(f"{'[green]✓' if is_clean else '[yellow]⚠'}[/] Git: {'clean' if is_clean else f'{len(dirty)} changes'}")
    
    console.print()


@app.command("batch")
def batch_cmd(
    path: str = typer.Argument(..., help="File or directory to process"),
    task: str = typer.Option("Fix all security vulnerabilities", "--task", "-t", help="Task to apply to each file"),
    workers: int = typer.Option(4, "--workers", "-w", help="Number of parallel workers"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b", help="LLM backend"),
):
    """⚡ Batch process files in parallel with multiple Ralph workers."""
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    
    # Find files
    if os.path.isdir(path):
        files = [f for f in glob.glob(f"{path}/**/*", recursive=True) if os.path.isfile(f)]
    elif os.path.isfile(path):
        files = [path]
    else:
        console.print(f"[red]Path not found: {path}[/red]")
        raise typer.Exit(1)
    
    if not files:
        console.print("[yellow]No files found[/yellow]")
        raise typer.Exit(0)
    
    console.print(f"\n[bold]⚡ Batch Processing: {len(files)} files with {workers} workers[/bold]\n")
    
    # Detect backend
    if backend:
        backend_cmd = backend
        backend_args = get_backend_args(backend)
    else:
        backend_cmd, backend_args = detect_backend()
    
    if not backend_cmd:
        console.print("[red]No LLM backend found[/red]")
        raise typer.Exit(1)
    
    cwd = Path.cwd()
    results = {"success": 0, "failed": 0, "errors": []}
    
    def process_file(filepath: str) -> Tuple[str, bool, str]:
        """Process a single file - runs in a thread."""
        try:
            prompt = f"""Fix this file: {filepath}
Task: {task}
Make targeted fixes. Be concise."""
            
            success, output = run_agent(backend_cmd, backend_args, prompt, cwd)
            return filepath, success, output[:200] if output else ""
        except Exception as e:
            return filepath, False, str(e)
    
    # Process files in parallel with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task_id = progress.add_task("[cyan]Processing...", total=len(files))
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_file, f): f for f in files}
            
            for future in as_completed(futures):
                filepath, success, output = future.result()
                filename = os.path.basename(filepath)
                
                if success:
                    results["success"] += 1
                    progress.console.print(f"  [green]✓[/green] {filename}")
                else:
                    results["failed"] += 1
                    results["errors"].append((filename, output))
                    progress.console.print(f"  [red]✗[/red] {filename}")
                
                progress.advance(task_id)
    
    # Summary
    console.print(f"\n[bold]Results:[/bold]")
    console.print(f"  [green]✓ Success:[/green] {results['success']}")
    console.print(f"  [red]✗ Failed:[/red] {results['failed']}")
    
    if results["errors"]:
        console.print(f"\n[dim]Errors (first 5):[/dim]")
        for filename, error in results["errors"][:5]:
            console.print(f"  {filename}: {error[:50]}...")


# =============================================================================
# Entry Point Wrapper
# =============================================================================

def cli():
    """
    Main entry point for the CLI.
    Handles the magic: 'darkzloop "task"' works like 'darkzloop run "task"'
    """
    args = sys.argv[1:]
    known_commands = ["run", "batch", "doctor", "--help", "-h", "--version"]
    
    if args and args[0] not in known_commands and not args[0].startswith("-"):
        # Insert "run" before the task
        sys.argv.insert(1, "run")
    
    app()


if __name__ == "__main__":
    cli()

