"""
Darkzloop Native Tool Presets

Pre-configured settings for popular CLI tools.

This enables one-command setup:
    darkzloop config native claude
    darkzloop config native ollama

Each preset includes:
- Command and arguments for headless/batch mode
- Auth verification commands
- Model selection (where applicable)
- Platform-specific adjustments

Adding a new tool:
1. Add a ToolPreset entry
2. Implement any special handling in ShellExecutor if needed
3. Test with: darkzloop doctor
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import shutil
import subprocess
import platform


@dataclass
class ToolPreset:
    """Configuration preset for a native CLI tool."""
    
    # Basic identity
    name: str                           # Human-readable name
    description: str                    # What this tool is
    command: str                        # Executable name
    
    # Invocation
    args: List[str]                     # Default arguments for batch mode
    stdin_mode: bool = True             # Whether to pipe prompt via stdin
    prompt_arg: Optional[str] = None    # Argument name for prompt (if not stdin)
    
    # Output handling
    output_format: str = "text"         # Expected output: text, json, streaming
    needs_json_extraction: bool = True  # Whether to extract JSON from chatty output
    
    # Auth & availability
    check_command: List[str] = field(default_factory=list)  # Command to verify availability
    auth_command: Optional[str] = None  # How to authenticate
    auth_check: Optional[str] = None    # Command to check auth status
    
    # Model selection (for tools with multiple models)
    default_model: Optional[str] = None
    model_arg: Optional[str] = None     # Argument to specify model
    
    # Platform-specific
    platforms: List[str] = field(default_factory=lambda: ["linux", "darwin", "win32"])
    
    # Links
    install_url: Optional[str] = None
    docs_url: Optional[str] = None


# =============================================================================
# Tool Presets Registry
# =============================================================================

PRESETS: Dict[str, ToolPreset] = {
    
    # =========================================================================
    # Anthropic Claude CLI
    # =========================================================================
    "claude": ToolPreset(
        name="Claude CLI (Agentic)",
        description="Claude CLI in agentic mode - directly edits files via stdin",
        command="claude",
        args=["--dangerously-skip-permissions"],
        stdin_mode=True,  # Use stdin for prompts - allows file editing
        prompt_arg=None,
        output_format="text",
        needs_json_extraction=False,  # Claude directly edits, no JSON parsing needed
        check_command=["claude", "--version"],
        auth_command="claude login",
        auth_check="claude whoami",
        install_url="https://docs.anthropic.com/claude/cli",
        docs_url="https://docs.anthropic.com/claude/cli",
    ),

    "claude-print": ToolPreset(
        name="Claude CLI (Print Mode)",
        description="Claude CLI print mode - outputs text only, no file edits",
        command="claude",
        args=["--print", "--output-format", "text"],
        stdin_mode=True,
        output_format="text",
        needs_json_extraction=True,
        check_command=["claude", "--version"],
        auth_command="claude login",
        auth_check="claude whoami",
        install_url="https://docs.anthropic.com/claude/cli",
        docs_url="https://docs.anthropic.com/claude/cli",
    ),

    "claude-json": ToolPreset(
        name="Claude CLI (JSON Mode)",
        description="Claude CLI configured to output structured JSON",
        command="claude",
        args=["--print", "--output-format", "json"],
        stdin_mode=True,
        output_format="json",
        needs_json_extraction=False,
        check_command=["claude", "--version"],
        auth_command="claude login",
    ),
    
    # =========================================================================
    # GitHub Copilot
    # =========================================================================
    "gh-copilot": ToolPreset(
        name="GitHub Copilot CLI",
        description="GitHub Copilot via gh CLI extension (requires Copilot license)",
        command="gh",
        args=["copilot", "suggest", "-t", "shell"],
        stdin_mode=False,
        prompt_arg=None,  # Copilot uses interactive mode by default
        output_format="text",
        needs_json_extraction=True,
        check_command=["gh", "--version"],
        auth_command="gh auth login",
        auth_check="gh auth status",
        install_url="https://cli.github.com/",
        docs_url="https://docs.github.com/en/copilot/github-copilot-in-the-cli",
    ),
    
    # =========================================================================
    # Ollama (Local LLMs)
    # =========================================================================
    "ollama": ToolPreset(
        name="Ollama",
        description="Run local LLMs (Llama, CodeLlama, Mistral) - 100% offline & free",
        command="ollama",
        args=["run", "llama3.1"],
        stdin_mode=True,
        output_format="text",
        needs_json_extraction=True,
        check_command=["ollama", "--version"],
        auth_command="ollama serve",
        default_model="llama3.1",
        model_arg="run",
        install_url="https://ollama.ai/download",
        docs_url="https://github.com/ollama/ollama",
    ),
    
    "ollama-codellama": ToolPreset(
        name="Ollama CodeLlama",
        description="CodeLlama via Ollama - optimized for coding tasks",
        command="ollama",
        args=["run", "codellama:34b"],
        stdin_mode=True,
        output_format="text",
        needs_json_extraction=True,
        check_command=["ollama", "--version"],
        default_model="codellama:34b",
        install_url="https://ollama.ai/download",
    ),
    
    "ollama-deepseek": ToolPreset(
        name="Ollama DeepSeek Coder",
        description="DeepSeek Coder via Ollama - excellent for code generation",
        command="ollama",
        args=["run", "deepseek-coder:33b"],
        stdin_mode=True,
        output_format="text",
        needs_json_extraction=True,
        check_command=["ollama", "--version"],
        default_model="deepseek-coder:33b",
        install_url="https://ollama.ai/download",
    ),
    
    # =========================================================================
    # Simon Willison's llm CLI (Universal)
    # =========================================================================
    "llm": ToolPreset(
        name="llm CLI",
        description="Universal LLM CLI by Simon Willison - supports 50+ providers via plugins",
        command="llm",
        args=["-m", "claude-3-sonnet"],
        stdin_mode=True,
        output_format="text",
        needs_json_extraction=True,
        check_command=["llm", "--version"],
        auth_command="llm keys set anthropic",
        default_model="claude-3-sonnet",
        model_arg="-m",
        install_url="https://llm.datasette.io/en/stable/setup.html",
        docs_url="https://llm.datasette.io/",
    ),
    
    "llm-gpt4": ToolPreset(
        name="llm CLI (GPT-4)",
        description="OpenAI GPT-4 via llm CLI",
        command="llm",
        args=["-m", "gpt-4o"],
        stdin_mode=True,
        output_format="text",
        needs_json_extraction=True,
        check_command=["llm", "--version"],
        auth_command="llm keys set openai",
        default_model="gpt-4o",
        model_arg="-m",
    ),
    
    "llm-gemini": ToolPreset(
        name="llm CLI (Gemini)",
        description="Google Gemini via llm CLI",
        command="llm",
        args=["-m", "gemini-pro"],
        stdin_mode=True,
        output_format="text",
        needs_json_extraction=True,
        check_command=["llm", "--version"],
        auth_command="llm install llm-gemini && llm keys set gemini",
        default_model="gemini-pro",
        model_arg="-m",
    ),
    
    # =========================================================================
    # Aider
    # =========================================================================
    "aider": ToolPreset(
        name="Aider",
        description="AI pair programming in your terminal",
        command="aider",
        args=["--yes-always", "--no-git", "--message"],
        stdin_mode=False,
        prompt_arg="--message",
        output_format="text",
        needs_json_extraction=True,
        check_command=["aider", "--version"],
        auth_command="Set ANTHROPIC_API_KEY or OPENAI_API_KEY",
        install_url="https://aider.chat/docs/install.html",
        docs_url="https://aider.chat/",
    ),
    
    # =========================================================================
    # OpenAI CLI (Official)
    # =========================================================================
    "openai": ToolPreset(
        name="OpenAI CLI",
        description="Official OpenAI command-line tool",
        command="openai",
        args=["api", "chat.completions.create", "-m", "gpt-4o", "-g", "user"],
        stdin_mode=False,
        prompt_arg="-g",
        output_format="json",
        needs_json_extraction=True,
        check_command=["openai", "--version"],
        auth_command="export OPENAI_API_KEY=sk-...",
        default_model="gpt-4o",
        install_url="https://github.com/openai/openai-python",
    ),
    
    # =========================================================================
    # Anthropic CLI (If/When Released)
    # =========================================================================
    "anthropic": ToolPreset(
        name="Anthropic CLI",
        description="Official Anthropic command-line tool (if available)",
        command="anthropic",
        args=["messages", "create", "-m", "claude-sonnet-4-20250514"],
        stdin_mode=True,
        output_format="json",
        needs_json_extraction=False,
        check_command=["anthropic", "--version"],
        auth_command="export ANTHROPIC_API_KEY=sk-ant-...",
        default_model="claude-sonnet-4-20250514",
    ),
}


# =============================================================================
# Preset Discovery & Utilities
# =============================================================================

def get_preset(name: str) -> Optional[ToolPreset]:
    """Get a preset by name (case-insensitive)."""
    return PRESETS.get(name.lower())


def list_presets() -> List[str]:
    """List all available preset names."""
    return list(PRESETS.keys())


def get_preset_info(name: str) -> Optional[Dict]:
    """Get human-readable info about a preset."""
    preset = get_preset(name)
    if not preset:
        return None
    
    return {
        "name": preset.name,
        "description": preset.description,
        "command": preset.command,
        "args": preset.args,
        "auth": preset.auth_command,
        "docs": preset.docs_url,
    }


def detect_available_presets() -> List[Tuple[str, ToolPreset, bool]]:
    """
    Detect which presets are available on this system.
    
    Returns: [(preset_name, preset, is_available)]
    """
    results = []
    current_platform = platform.system().lower()
    
    # Map platform names
    platform_map = {
        "linux": "linux",
        "darwin": "darwin",
        "windows": "win32",
    }
    current_platform = platform_map.get(current_platform, current_platform)
    
    for name, preset in PRESETS.items():
        # Check platform compatibility
        if current_platform not in preset.platforms:
            results.append((name, preset, False))
            continue
        
        # Check if command exists
        is_available = shutil.which(preset.command) is not None
        results.append((name, preset, is_available))
    
    return results


def check_preset_auth(name: str) -> Tuple[bool, str]:
    """
    Check if a preset's auth is configured.
    
    Returns: (is_authed, message)
    """
    preset = get_preset(name)
    if not preset:
        return False, f"Unknown preset: {name}"
    
    # Check if command exists
    if not shutil.which(preset.command):
        return False, f"Command not found: {preset.command}"
    
    # Run auth check if available
    if preset.auth_check:
        try:
            result = subprocess.run(
                preset.auth_check.split(),
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, f"{preset.name}: Authenticated"
            else:
                return False, f"{preset.name}: Not authenticated. Run: {preset.auth_command}"
        except Exception as e:
            return False, f"Auth check failed: {e}"
    
    # No auth check available, assume OK if command exists
    return True, f"{preset.name}: Available (auth status unknown)"


def get_recommended_preset() -> Optional[str]:
    """
    Get the recommended preset for this system.
    
    Priority:
    1. claude (if available and authed)
    2. ollama (if available)
    3. llm (if available)
    4. gh-copilot (if available)
    """
    priority = ["claude", "ollama", "llm", "gh-copilot"]
    
    for name in priority:
        preset = get_preset(name)
        if preset and shutil.which(preset.command):
            return name
    
    return None


def get_presets_by_category() -> Dict[str, List[str]]:
    """Group presets by category."""
    return {
        "Cloud (Requires Auth)": ["claude", "claude-json", "gh-copilot", "llm", "llm-gpt4", "llm-gemini"],
        "Local (Free & Offline)": ["ollama", "ollama-codellama", "ollama-deepseek"],
        "Direct API": ["openai", "anthropic"],
        "Pair Programming": ["aider"],
    }


# =============================================================================
# Preset Validation
# =============================================================================

def validate_preset_config(name: str, custom_args: List[str] = None) -> Tuple[bool, str, Dict]:
    """
    Validate a preset configuration before use.
    
    Returns: (is_valid, message, config_dict)
    """
    preset = get_preset(name)
    if not preset:
        return False, f"Unknown preset: {name}", {}
    
    # Check command exists
    if not shutil.which(preset.command):
        install_hint = f"\nInstall: {preset.install_url}" if preset.install_url else ""
        return False, f"Command '{preset.command}' not found.{install_hint}", {}
    
    # Build config
    config = {
        "command": preset.command,
        "args": custom_args or preset.args,
        "stdin_mode": preset.stdin_mode,
        "needs_json_extraction": preset.needs_json_extraction,
        "output_format": preset.output_format,
    }
    
    return True, f"{preset.name} configured successfully", config


# =============================================================================
# Quick Setup Helpers
# =============================================================================

def generate_setup_instructions(name: str) -> str:
    """Generate setup instructions for a preset."""
    preset = get_preset(name)
    if not preset:
        return f"Unknown preset: {name}"
    
    lines = [
        f"# {preset.name} Setup",
        f"",
        f"## Description",
        f"{preset.description}",
        f"",
        f"## Installation",
    ]
    
    if preset.install_url:
        lines.append(f"Visit: {preset.install_url}")
    
    lines.extend([
        f"",
        f"## Authentication",
        f"```bash",
        f"{preset.auth_command or 'No authentication required'}",
        f"```",
        f"",
        f"## Configure Darkzloop",
        f"```bash",
        f"darkzloop config native {name}",
        f"```",
        f"",
        f"## Verify",
        f"```bash",
        f"darkzloop doctor",
        f"```",
    ])
    
    if preset.docs_url:
        lines.extend([
            f"",
            f"## Documentation",
            f"{preset.docs_url}",
        ])
    
    return "\n".join(lines)
