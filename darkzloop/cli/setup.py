"""
Darkzloop Project Setup and Stack Detection

Automatically detects project type and configures appropriate quality gates.

Supported stacks:
- Rust (Cargo.toml)
- Node.js (package.json)
- Python (pyproject.toml, requirements.txt)
- Go (go.mod)
- Generic fallback
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

# Rich is optional - only needed for interactive init
try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = None


# =============================================================================
# Stack Definitions
# =============================================================================

@dataclass
class StackConfig:
    """Configuration for a detected stack."""
    name: str
    display_name: str
    tier1_commands: List[str]
    tier2_commands: List[str]
    tier2_auto_fix: List[str]
    tier3_commands: List[str]
    file_extensions: List[str]
    src_dirs: List[str]


STACKS: Dict[str, StackConfig] = {
    "rust": StackConfig(
        name="rust",
        display_name="Rust",
        tier1_commands=["cargo check", "cargo test"],
        tier2_commands=["cargo fmt --check", "cargo clippy -- -D warnings"],
        tier2_auto_fix=["cargo fmt"],
        tier3_commands=["cargo audit"],
        file_extensions=[".rs"],
        src_dirs=["src"],
    ),
    "node": StackConfig(
        name="node",
        display_name="Node.js",
        tier1_commands=["npm test"],
        tier2_commands=["npm run lint"],
        tier2_auto_fix=["npm run format"],
        tier3_commands=["npm audit"],
        file_extensions=[".ts", ".tsx", ".js", ".jsx"],
        src_dirs=["src", "lib", "app"],
    ),
    "node-pnpm": StackConfig(
        name="node-pnpm",
        display_name="Node.js (pnpm)",
        tier1_commands=["pnpm test"],
        tier2_commands=["pnpm run lint"],
        tier2_auto_fix=["pnpm run format"],
        tier3_commands=["pnpm audit"],
        file_extensions=[".ts", ".tsx", ".js", ".jsx"],
        src_dirs=["src", "lib", "app"],
    ),
    "node-yarn": StackConfig(
        name="node-yarn",
        display_name="Node.js (yarn)",
        tier1_commands=["yarn test"],
        tier2_commands=["yarn lint"],
        tier2_auto_fix=["yarn format"],
        tier3_commands=["yarn audit"],
        file_extensions=[".ts", ".tsx", ".js", ".jsx"],
        src_dirs=["src", "lib", "app"],
    ),
    "python": StackConfig(
        name="python",
        display_name="Python",
        tier1_commands=["pytest"],
        tier2_commands=["ruff check .", "black --check ."],
        tier2_auto_fix=["ruff check . --fix", "black ."],
        tier3_commands=["bandit -r ."],
        file_extensions=[".py"],
        src_dirs=["src", "lib", "app"],
    ),
    "python-poetry": StackConfig(
        name="python-poetry",
        display_name="Python (Poetry)",
        tier1_commands=["poetry run pytest"],
        tier2_commands=["poetry run ruff check .", "poetry run black --check ."],
        tier2_auto_fix=["poetry run ruff check . --fix", "poetry run black ."],
        tier3_commands=["poetry run bandit -r ."],
        file_extensions=[".py"],
        src_dirs=["src", "lib", "app"],
    ),
    "go": StackConfig(
        name="go",
        display_name="Go",
        tier1_commands=["go build ./...", "go test ./..."],
        tier2_commands=["go vet ./...", "golangci-lint run"],
        tier2_auto_fix=["gofmt -w ."],
        tier3_commands=["govulncheck ./..."],
        file_extensions=[".go"],
        src_dirs=["cmd", "internal", "pkg"],
    ),
    "generic": StackConfig(
        name="generic",
        display_name="Generic",
        tier1_commands=[],
        tier2_commands=[],
        tier2_auto_fix=[],
        tier3_commands=[],
        file_extensions=[],
        src_dirs=["src"],
    ),
}


# =============================================================================
# Stack Detection
# =============================================================================

def detect_stack(path: Path) -> StackConfig:
    """
    Detect the project stack by examining marker files.
    
    Priority:
    1. Rust (Cargo.toml)
    2. Go (go.mod)
    3. Node (package.json) - check for pnpm/yarn
    4. Python (pyproject.toml, setup.py, requirements.txt)
    5. Generic fallback
    """
    # Rust
    if (path / "Cargo.toml").exists():
        return STACKS["rust"]
    
    # Go
    if (path / "go.mod").exists():
        return STACKS["go"]
    
    # Node.js - check package manager
    if (path / "package.json").exists():
        if (path / "pnpm-lock.yaml").exists():
            return STACKS["node-pnpm"]
        elif (path / "yarn.lock").exists():
            return STACKS["node-yarn"]
        return STACKS["node"]
    
    # Python - check package manager
    if (path / "pyproject.toml").exists():
        # Check if it's poetry
        try:
            content = (path / "pyproject.toml").read_text()
            if "[tool.poetry]" in content:
                return STACKS["python-poetry"]
        except Exception:
            pass
        return STACKS["python"]
    
    if (path / "setup.py").exists() or (path / "requirements.txt").exists():
        return STACKS["python"]
    
    # Fallback
    return STACKS["generic"]


def detect_project_name(path: Path, stack: StackConfig) -> str:
    """Try to extract project name from config files."""
    try:
        if stack.name == "rust":
            cargo = (path / "Cargo.toml").read_text()
            for line in cargo.split("\n"):
                if line.startswith("name"):
                    return line.split("=")[1].strip().strip('"')
        
        elif stack.name.startswith("node"):
            pkg = json.loads((path / "package.json").read_text())
            return pkg.get("name", "")
        
        elif stack.name.startswith("python"):
            if (path / "pyproject.toml").exists():
                content = (path / "pyproject.toml").read_text()
                for line in content.split("\n"):
                    if line.startswith("name"):
                        return line.split("=")[1].strip().strip('"')
    except Exception:
        pass
    
    return path.name


def detect_test_command(path: Path, stack: StackConfig) -> Optional[str]:
    """Try to detect the actual test command from config files."""
    try:
        if stack.name.startswith("node"):
            pkg = json.loads((path / "package.json").read_text())
            scripts = pkg.get("scripts", {})
            if "test" in scripts:
                return f"npm test" if stack.name == "node" else f"{stack.name.split('-')[1]} test"
    except Exception:
        pass
    
    return stack.tier1_commands[0] if stack.tier1_commands else None


# =============================================================================
# Project Initialization
# =============================================================================

def init_project(path: Path, console=None, interactive: bool = True):
    """
    Initialize darkzloop in a project.
    
    1. Detect stack
    2. Create darkzloop.json
    3. Create DARKZLOOP_SPEC.md template
    4. Create .darkzloop/ directory
    """
    # Handle missing rich
    if console is None and HAS_RICH:
        console = Console()
    
    def print_msg(msg: str, style: str = None):
        if console and HAS_RICH:
            console.print(msg)
        else:
            # Strip rich markup for plain print
            import re
            plain = re.sub(r'\[.*?\]', '', msg)
            print(plain)
    
    def ask_confirm(msg: str, default: bool = False) -> bool:
        if HAS_RICH and interactive:
            return Confirm.ask(msg, default=default)
        return default
    
    # Check if already initialized
    if (path / "darkzloop.json").exists():
        print_msg("[yellow]⚠️  Darkzloop already initialized in this project.[/yellow]")
        if interactive and HAS_RICH:
            overwrite = ask_confirm("Overwrite existing configuration?", default=False)
            if not overwrite:
                return
        else:
            return
    
    # Detect stack
    stack = detect_stack(path)
    project_name = detect_project_name(path, stack)
    
    if HAS_RICH and console:
        console.print(Panel(
            f"[bold green]Detected:[/bold green] {stack.display_name}\n"
            f"[bold blue]Project:[/bold blue] {project_name}",
            title="Stack Detection",
            border_style="green"
        ))
    else:
        print_msg(f"Detected: {stack.display_name}")
        print_msg(f"Project: {project_name}")
    
    # Confirm or override
    if interactive and stack.name == "generic" and HAS_RICH:
        print_msg("[yellow]Could not auto-detect stack. Using generic configuration.[/yellow]")
        custom = Prompt.ask(
            "Enter stack type",
            choices=list(STACKS.keys()),
            default="generic"
        )
        stack = STACKS[custom]
    
    # Create configuration
    config = {
        "version": "1.0",
        "project": {
            "name": project_name,
            "type": stack.name,
        },
        "paths": {
            "spec": "DARKZLOOP_SPEC.md",
            "plan": "DARKZLOOP_PLAN.md",
        },
        "gates": {
            "tier1": {
                "enabled": bool(stack.tier1_commands),
                "commands": stack.tier1_commands,
                "on_failure": "task_failure",
            },
            "tier2": {
                "enabled": bool(stack.tier2_commands),
                "commands": stack.tier2_commands,
                "auto_fix_commands": stack.tier2_auto_fix,
                "on_failure": "task_failure",
            },
            "tier3": {
                "enabled": False,  # Disabled by default
                "commands": stack.tier3_commands,
                "on_failure": "blocked",
            },
        },
        "loop": {
            "max_iterations": 100,
            "max_consecutive_failures": 3,
            "max_task_retries": 3,
        },
        "features": {
            "semantic_memory": True,
            "enforce_read_before_write": True,
            "parallel_enabled": False,
            "auto_commit": True,
        },
    }
    
    # Write config
    with open(path / "darkzloop.json", "w") as f:
        json.dump(config, f, indent=2)
    print_msg("✅ Created [bold]darkzloop.json[/bold]")
    
    # Create spec template
    spec_content = create_spec_template(project_name, stack)
    with open(path / "DARKZLOOP_SPEC.md", "w") as f:
        f.write(spec_content)
    print_msg("✅ Created [bold]DARKZLOOP_SPEC.md[/bold] template")
    
    # Create .darkzloop directory
    darkzloop_dir = path / ".darkzloop"
    darkzloop_dir.mkdir(exist_ok=True)
    
    # Create .gitignore for .darkzloop
    gitignore = darkzloop_dir / ".gitignore"
    gitignore.write_text("# Darkzloop local state\nstate.json\n*.log\n")
    
    # Add to project .gitignore if exists
    project_gitignore = path / ".gitignore"
    if project_gitignore.exists():
        content = project_gitignore.read_text()
        if ".darkzloop/state.json" not in content:
            with open(project_gitignore, "a") as f:
                f.write("\n# Darkzloop\n.darkzloop/state.json\n")
            print_msg("✅ Updated [bold].gitignore[/bold]")
    
    print_msg("")
    if HAS_RICH and console:
        console.print(Panel(
            "[green]Darkzloop initialized successfully![/green]\n\n"
            "Next steps:\n"
            "1. Edit [bold]DARKZLOOP_SPEC.md[/bold] to describe your goal\n"
            "2. Run [bold]darkzloop plan[/bold] to generate tasks\n"
            "3. Run [bold]darkzloop run[/bold] to execute",
            title="Ready",
            border_style="green"
        ))
    else:
        print_msg("Darkzloop initialized successfully!")
        print_msg("")
        print_msg("Next steps:")
        print_msg("1. Edit DARKZLOOP_SPEC.md to describe your goal")
        print_msg("2. Run 'darkzloop plan' to generate tasks")
        print_msg("3. Run 'darkzloop run' to execute")


def create_spec_template(project_name: str, stack: StackConfig) -> str:
    """Create a spec template appropriate for the stack."""
    extensions = ", ".join(stack.file_extensions) if stack.file_extensions else "various"
    
    return f"""# {project_name} - Project Specification

## Objective

[Describe your goal here. Be specific about what you want to build or fix.]

Example:
- "Add user authentication using JWT tokens"
- "Fix the bug where checkout fails for guest users"
- "Refactor the payment module to use the Strategy pattern"

## Current State

[Describe what exists now. What files are relevant?]

## Desired Outcome

[Describe what should exist after this task is complete.]

### Acceptance Criteria

- [ ] All tests pass
- [ ] Code follows existing patterns
- [ ] [Add your own criteria]

## Technical Context

### Stack
- Type: {stack.display_name}
- File extensions: {extensions}

### Key Files
- [List important files the agent should understand]

### Patterns to Follow
- [Reference existing code patterns]

## Constraints

- [Any limitations or requirements]
- Do not modify [files that shouldn't be touched]

## Notes

[Any additional context that would help the agent]
"""


# =============================================================================
# Convenience Functions
# =============================================================================

def is_initialized(path: Path = None) -> bool:
    """Check if darkzloop is initialized in the project."""
    root = path or Path.cwd()
    return (root / "darkzloop.json").exists()


def get_stack(path: Path = None) -> StackConfig:
    """Get the stack for a project."""
    root = path or Path.cwd()
    return detect_stack(root)
