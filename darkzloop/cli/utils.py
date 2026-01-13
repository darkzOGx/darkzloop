"""
Darkzloop CLI Utilities

Safety checks and debugging utilities for the CLI.

Key features:
- Git clean check (prevents loss of uncommitted work)
- Debug mode for stack traces
- Dry run simulation
- Backup creation
"""

import os
import sys
import shutil
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List
from dataclasses import dataclass

# Set up logging
logger = logging.getLogger("darkzloop")


# =============================================================================
# Console Unicode Support
# =============================================================================

def _supports_unicode() -> bool:
    """Check if the console supports Unicode output."""
    if sys.platform != "win32":
        return True

    # Check if running in a Unicode-capable terminal
    try:
        # Check stdout encoding
        if sys.stdout and hasattr(sys.stdout, 'encoding'):
            encoding = (sys.stdout.encoding or '').lower()
            if 'utf' in encoding:
                return True

        # Check environment variables that indicate Unicode support
        if os.environ.get('WT_SESSION'):  # Windows Terminal
            return True
        if os.environ.get('TERM_PROGRAM') in ('vscode', 'mintty'):
            return True
        if 'UTF' in os.environ.get('LANG', '').upper():
            return True

    except Exception:
        pass

    return False


# Cache the result
_UNICODE_SUPPORTED: Optional[bool] = None


def supports_unicode() -> bool:
    """Check if console supports Unicode (cached)."""
    global _UNICODE_SUPPORTED
    if _UNICODE_SUPPORTED is None:
        _UNICODE_SUPPORTED = _supports_unicode()
    return _UNICODE_SUPPORTED


# Emoji mappings with ASCII fallbacks
_EMOJI_FALLBACKS = {
    "🔄": "[~]",
    "✓": "[+]",
    "✗": "[x]",
    "⚠": "[!]",
    "🚀": "[>]",
    "📦": "[=]",
    "🛡️": "[#]",
    "💡": "[*]",
    "🔧": "[%]",
    "📊": "[|]",
}


def safe_emoji(emoji: str, fallback: str = None) -> str:
    """
    Return emoji if supported, otherwise return ASCII fallback.

    Args:
        emoji: The emoji character to display
        fallback: Optional custom fallback (uses default mapping if not provided)

    Returns:
        The emoji or its ASCII fallback
    """
    if supports_unicode():
        return emoji

    if fallback is not None:
        return fallback

    return _EMOJI_FALLBACKS.get(emoji, "")


def get_logo() -> str:
    """Get the Darkzloop logo character."""
    return safe_emoji("🔄", "[~]")


# =============================================================================
# Git Safety Checks
# =============================================================================

@dataclass
class GitStatus:
    """Status of the git repository."""
    is_repo: bool
    is_clean: bool
    branch: str
    uncommitted_files: List[str]
    untracked_files: List[str]
    has_remote: bool
    error: Optional[str] = None


def check_git_status(path: Path = None) -> GitStatus:
    """
    Check the git status of a directory.
    
    Returns detailed status including:
    - Whether it's a git repo
    - Whether the working tree is clean
    - Current branch
    - List of uncommitted/untracked files
    """
    cwd = path or Path.cwd()
    
    try:
        # Check if it's a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return GitStatus(
                is_repo=False,
                is_clean=True,  # Not a repo, so "clean" in the sense of no git state
                branch="",
                uncommitted_files=[],
                untracked_files=[],
                has_remote=False,
            )
        
        # Get current branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        branch = branch_result.stdout.strip() or "HEAD (detached)"
        
        # Check for uncommitted changes
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        
        uncommitted = []
        untracked = []
        
        for line in status_result.stdout.strip().split("\n"):
            if not line:
                continue
            status_code = line[:2]
            file_path = line[3:]
            
            if status_code == "??":
                untracked.append(file_path)
            else:
                uncommitted.append(file_path)
        
        # Check for remote
        remote_result = subprocess.run(
            ["git", "remote"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        has_remote = bool(remote_result.stdout.strip())
        
        is_clean = len(uncommitted) == 0
        
        return GitStatus(
            is_repo=True,
            is_clean=is_clean,
            branch=branch,
            uncommitted_files=uncommitted,
            untracked_files=untracked,
            has_remote=has_remote,
        )
        
    except FileNotFoundError:
        return GitStatus(
            is_repo=False,
            is_clean=True,
            branch="",
            uncommitted_files=[],
            untracked_files=[],
            has_remote=False,
            error="Git not installed",
        )
    except Exception as e:
        return GitStatus(
            is_repo=False,
            is_clean=True,
            branch="",
            uncommitted_files=[],
            untracked_files=[],
            has_remote=False,
            error=str(e),
        )


def check_git_clean(path: Path = None, console=None) -> Tuple[bool, str]:
    """
    Check if git working tree is clean.
    
    Returns:
        (is_safe, message)
        - is_safe: True if safe to proceed
        - message: Description of the status
    """
    status = check_git_status(path)
    
    if not status.is_repo:
        # Not a git repo - warn but allow
        return True, "Not a git repository (no safety net for rollback)"
    
    if status.is_clean:
        return True, f"Git tree clean on branch '{status.branch}'"
    
    # Dirty tree - this is the warning case
    files = status.uncommitted_files[:5]
    more = len(status.uncommitted_files) - 5
    
    msg = f"⚠️  Uncommitted changes detected ({len(status.uncommitted_files)} files):\n"
    for f in files:
        msg += f"   - {f}\n"
    if more > 0:
        msg += f"   ... and {more} more\n"
    msg += "\nIf darkzloop modifies these files, you may lose your work!"
    
    return False, msg


def prompt_git_safety(console, path: Path = None) -> bool:
    """
    Check git status and prompt user if tree is dirty.
    
    Returns True if safe to proceed, False if user aborted.
    """
    is_safe, message = check_git_clean(path)
    
    if is_safe:
        console.print(f"[green]✓[/green] {message}")
        return True
    
    console.print(f"[yellow]{message}[/yellow]")
    console.print("")
    
    # Import here to avoid circular deps
    try:
        from rich.prompt import Confirm
        proceed = Confirm.ask(
            "[bold yellow]Continue anyway?[/bold yellow]",
            default=False
        )
        return proceed
    except ImportError:
        # No rich, use basic input
        response = input("Continue anyway? [y/N] ").strip().lower()
        return response in ('y', 'yes')


def create_safety_commit(path: Path = None, message: str = None) -> Optional[str]:
    """
    Create a safety commit of current state before running.
    
    Returns commit hash if successful, None otherwise.
    """
    cwd = path or Path.cwd()
    commit_msg = message or f"darkzloop: safety checkpoint {datetime.now().isoformat()}"
    
    try:
        # Stage all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=cwd,
            capture_output=True,
            check=True
        )
        
        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return None
        
        # Get commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True
        )
        
        return hash_result.stdout.strip()
        
    except Exception:
        return None


def create_backup_branch(path: Path = None, prefix: str = "darkzloop-backup") -> Optional[str]:
    """
    Create a backup branch before running.
    
    Returns branch name if successful, None otherwise.
    """
    cwd = path or Path.cwd()
    branch_name = f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    try:
        result = subprocess.run(
            ["git", "branch", branch_name],
            cwd=cwd,
            capture_output=True
        )
        
        if result.returncode == 0:
            return branch_name
            
    except Exception:
        pass
    
    return None


# =============================================================================
# Debugging Utilities
# =============================================================================

def setup_debug_logging(debug: bool = False, verbose: bool = False):
    """Configure logging based on debug/verbose flags."""
    if debug:
        level = logging.DEBUG
        format_str = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
    elif verbose:
        level = logging.INFO
        format_str = "%(levelname)s: %(message)s"
    else:
        level = logging.WARNING
        format_str = "%(message)s"
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[logging.StreamHandler(sys.stderr)]
    )
    
    # Set for our logger
    logger.setLevel(level)


def enable_traceback():
    """Enable full Python tracebacks on error."""
    # This is useful when we want to see the full stack trace
    # instead of pretty-printed errors
    import traceback
    sys.excepthook = lambda *args: traceback.print_exception(*args)


# =============================================================================
# File Safety
# =============================================================================

def backup_file(path: Path) -> Optional[Path]:
    """Create a backup of a file before modifying."""
    if not path.exists():
        return None
    
    backup_dir = path.parent / ".darkzloop" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"{path.name}.{timestamp}.bak"
    
    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except Exception:
        return None


def restore_from_backup(backup_path: Path, original_path: Path) -> bool:
    """Restore a file from backup."""
    try:
        shutil.copy2(backup_path, original_path)
        return True
    except Exception:
        return False


# =============================================================================
# Environment Checks
# =============================================================================

def check_environment() -> List[Tuple[str, bool, str]]:
    """
    Check the environment for required tools.
    
    Returns list of (tool_name, is_available, message).
    """
    checks = []
    
    # Git
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            checks.append(("git", True, version))
        else:
            checks.append(("git", False, "Git not working"))
    except FileNotFoundError:
        checks.append(("git", False, "Git not installed"))
    
    # Python version
    py_version = f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    checks.append(("python", py_ok, py_version))
    
    # API key
    has_anthropic_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))
    
    if has_anthropic_key:
        checks.append(("api_key", True, "ANTHROPIC_API_KEY set"))
    elif has_openai_key:
        checks.append(("api_key", True, "OPENAI_API_KEY set"))
    else:
        # Check config file
        from darkzloop.cli.config import get_api_key
        if get_api_key():
            checks.append(("api_key", True, "Key in config file"))
        else:
            checks.append(("api_key", False, "No API key configured"))
    
    return checks


def print_environment_check(console):
    """Print environment check results."""
    checks = check_environment()
    
    console.print("[bold]Environment Check[/bold]")
    
    for tool, ok, message in checks:
        icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
        console.print(f"  {icon} {tool}: {message}")
    
    all_ok = all(ok for _, ok, _ in checks)
    return all_ok


# =============================================================================
# Dry Run Support
# =============================================================================

class DryRunContext:
    """
    Context manager for dry run mode.
    
    Captures what would happen without actually doing it.
    """
    
    def __init__(self):
        self.actions: List[dict] = []
        self.files_would_create: List[str] = []
        self.files_would_modify: List[str] = []
        self.commands_would_run: List[str] = []
    
    def log_action(self, action_type: str, target: str, details: str = ""):
        """Log an action that would be taken."""
        self.actions.append({
            "type": action_type,
            "target": target,
            "details": details,
        })
        
        if action_type == "create_file":
            self.files_would_create.append(target)
        elif action_type == "modify_file":
            self.files_would_modify.append(target)
        elif action_type == "run_command":
            self.commands_would_run.append(target)
    
    def summary(self) -> str:
        """Generate a summary of what would happen."""
        lines = ["[bold]Dry Run Summary[/bold]", ""]
        
        if self.files_would_create:
            lines.append(f"Would create {len(self.files_would_create)} files:")
            for f in self.files_would_create[:10]:
                lines.append(f"  + {f}")
        
        if self.files_would_modify:
            lines.append(f"Would modify {len(self.files_would_modify)} files:")
            for f in self.files_would_modify[:10]:
                lines.append(f"  ~ {f}")
        
        if self.commands_would_run:
            lines.append(f"Would run {len(self.commands_would_run)} commands:")
            for c in self.commands_would_run[:10]:
                lines.append(f"  $ {c}")
        
        return "\n".join(lines)


# Global dry run context (set when --dry-run is used)
_dry_run_context: Optional[DryRunContext] = None


def is_dry_run() -> bool:
    """Check if we're in dry run mode."""
    return _dry_run_context is not None


def get_dry_run_context() -> Optional[DryRunContext]:
    """Get the current dry run context."""
    return _dry_run_context


def set_dry_run_context(ctx: Optional[DryRunContext]):
    """Set the dry run context."""
    global _dry_run_context
    _dry_run_context = ctx
