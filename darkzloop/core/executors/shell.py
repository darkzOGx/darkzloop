"""
Shell Executor - Native CLI Tool Integration

Executes prompts via native CLI tools like:
- Claude CLI (claude)
- GitHub Copilot CLI (gh copilot)
- Ollama (ollama)
- Simon Willison's llm CLI (llm)
- Any custom command

This enables "Bring Your Own Auth" (BYOA) - users leverage their
existing subscriptions without managing API keys.

Usage:
    executor = ShellExecutor(ExecutorConfig(
        type=ExecutorType.SHELL,
        command="claude",
        args=["--print"],
    ))
    response = executor.execute(prompt)
"""

import subprocess
import shutil
import time
import re
import os
from typing import Tuple, Optional, List
from dataclasses import dataclass

from darkzloop.core.executors import (
    BaseExecutor, ExecutorConfig, ExecutorResponse,
    ExecutorType, register_executor
)
from darkzloop.core.executors.presets import (
    PRESETS, get_preset, list_presets, detect_available_presets,
    ToolPreset, get_recommended_preset
)

# Backwards compatibility alias
NATIVE_PRESETS = PRESETS


# =============================================================================
# Shell Executor
# =============================================================================

# Re-export for backward compatibility
def detect_available_tools() -> list:
    """Detect which native tools are available."""
    results = []
    for name, preset, is_available in detect_available_presets():
        if is_available:
            results.append((name, preset.name, preset.command))
    return results


@register_executor(ExecutorType.SHELL)
class ShellExecutor(BaseExecutor):
    """
    Executes prompts via native CLI tools.
    
    Supports:
    - Stdin mode: Pipes prompt to tool's stdin (recommended)
    - Argument mode: Passes prompt as command argument
    
    Features:
    - ANSI code stripping (removes colors/spinners)
    - Timeout handling
    - Error recovery
    """
    
    # Headless mode instruction - prevents interactive behavior
    HEADLESS_PREFIX = """You are running in HEADLESS MODE inside Darkzloop.

CRITICAL INSTRUCTIONS:
1. Do NOT ask for confirmation or clarification
2. Do NOT emit conversational filler ("Sure!", "Let me...", etc.)
3. Output ONLY the requested JSON/code
4. If uncertain, make the most reasonable choice and proceed

Your response must be valid JSON with this structure:
{
  "thinking": "Brief reasoning",
  "action": "action_name",
  "parameters": {...}
}
"""
    
    def __init__(self, config: ExecutorConfig):
        super().__init__(config)
        self.preset = get_preset(config.command)
        
        # Apply preset if available
        if self.preset and not config.args:
            config.args = self.preset.args
    
    def execute(self, prompt: str, system_prompt: str = "") -> ExecutorResponse:
        """
        Execute prompt via shell command.

        Supports two modes:
        - stdin_mode: Pipes prompt to tool's stdin (safer, no length limits)
        - argument_mode: Passes prompt as command-line argument
        """
        start_time = time.time()

        # For agentic tools that edit files directly, use a simpler prompt
        if self.preset and not self.preset.stdin_mode:
            # Agentic mode - tool will edit files directly
            full_prompt = prompt  # Don't add HEADLESS_PREFIX for agentic tools
        else:
            # Print mode - expect structured JSON output
            full_system = self.HEADLESS_PREFIX
            if system_prompt:
                full_system += "\n" + system_prompt
            full_prompt = self.prepare_prompt(prompt, full_system)

        # Build command
        cmd = [self.config.command] + self.config.args

        # Determine if we're using stdin or argument mode
        use_stdin = True
        if self.preset and not self.preset.stdin_mode and self.preset.prompt_arg:
            # Argument mode: append prompt as command-line argument
            cmd.append(full_prompt)
            use_stdin = False

        try:
            # Execute command
            if use_stdin:
                # Stdin mode: pipe prompt to stdin (UTF-8 encoded for Windows)
                result = subprocess.run(
                    cmd,
                    input=full_prompt.encode('utf-8'),
                    capture_output=True,
                    timeout=self.config.timeout_seconds,
                    env=self._get_env(),
                    cwd=self.config.cwd if hasattr(self.config, 'cwd') else None,
                )
            else:
                # Argument mode: for agentic tools, don't capture output so they can edit files
                # Run with stdin/stdout inherited for tool use
                result = subprocess.run(
                    cmd,
                    capture_output=False,  # Let Claude CLI use tools
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=self.config.timeout_seconds,
                    env=self._get_env(),
                    cwd=self.config.cwd if self.config.cwd else None,
                )

            # Decode output as UTF-8
            result_stdout = result.stdout.decode('utf-8', errors='replace')
            result_stderr = result.stderr.decode('utf-8', errors='replace')

            duration_ms = int((time.time() - start_time) * 1000)
            raw_output = result_stdout

            # Strip ANSI codes if configured
            if self.config.strip_ansi:
                output = self._strip_ansi_codes(raw_output)
            else:
                output = raw_output

            # Clean up output
            output = self._clean_output(output)

            # Check for errors
            if result.returncode != 0:
                return ExecutorResponse(
                    success=False,
                    content="",
                    raw_output=raw_output,
                    error=f"Command failed (exit {result.returncode}): {result_stderr}",
                    duration_ms=duration_ms,
                )

            # Try to parse JSON action from output
            action = self._extract_action(output)

            return ExecutorResponse(
                success=True,
                content=output,
                raw_output=raw_output,
                action=action,
                duration_ms=duration_ms,
            )
            
        except subprocess.TimeoutExpired:
            return ExecutorResponse(
                success=False,
                content="",
                raw_output="",
                error=f"Command timed out after {self.config.timeout_seconds}s",
                duration_ms=int((time.time() - start_time) * 1000),
            )
        except FileNotFoundError:
            return ExecutorResponse(
                success=False,
                content="",
                raw_output="",
                error=f"Command not found: {self.config.command}",
            )
        except Exception as e:
            return ExecutorResponse(
                success=False,
                content="",
                raw_output="",
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )
    
    def is_available(self) -> Tuple[bool, str]:
        """Check if the shell command is available."""
        # Check if command exists
        if not shutil.which(self.config.command):
            hint = ""
            if self.preset:
                hint = f" ({self.preset.auth_command or 'install the tool'})"
            return False, f"Command not found: {self.config.command}{hint}"
        
        # Try to run check command if we have a preset
        if self.preset and self.preset.check_command:
            try:
                result = subprocess.run(
                    self.preset.check_command,  # Already a list
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return True, f"{self.preset.name} available"
                else:
                    return False, f"{self.preset.name} check failed: {result.stderr.decode()[:100]}"
            except Exception as e:
                return False, f"Check failed: {e}"
        
        return True, f"Command available: {self.config.command}"
    
    def _get_env(self) -> dict:
        """Get environment variables for subprocess."""
        env = os.environ.copy()
        
        # Disable interactive features
        env["TERM"] = "dumb"
        env["NO_COLOR"] = "1"
        env["FORCE_COLOR"] = "0"
        
        # Tool-specific settings
        if self.config.command == "claude":
            env["CLAUDE_OUTPUT_FORMAT"] = "text"
        
        return env
    
    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape codes (colors, cursor movement, etc.)."""
        # Standard ANSI escape sequences
        ansi_escape = re.compile(r'''
            \x1B  # ESC
            (?:   # 7-bit C1 Fe (except CSI)
                [@-Z\\-_]
            |     # or [ for CSI, followed by a control sequence
                \[
                [0-?]*  # Parameter bytes
                [ -/]*  # Intermediate bytes
                [@-~]   # Final byte
            )
        ''', re.VERBOSE)
        
        text = ansi_escape.sub('', text)
        
        # Also remove carriage returns and clear line sequences
        text = re.sub(r'\r', '', text)
        
        return text
    
    def _clean_output(self, text: str) -> str:
        """Clean up output from CLI tools."""
        lines = text.split('\n')
        cleaned = []
        
        for line in lines:
            # Skip common CLI noise
            if any(skip in line.lower() for skip in [
                'loading',
                'thinking',
                'processing',
                '...',
                'streaming',
            ]):
                continue
            
            # Skip empty lines at start
            if not cleaned and not line.strip():
                continue
            
            cleaned.append(line)
        
        # Remove trailing empty lines
        while cleaned and not cleaned[-1].strip():
            cleaned.pop()
        
        return '\n'.join(cleaned)
    
    def _extract_action(self, text: str) -> Optional[dict]:
        """
        Extract JSON action from response text.
        
        Native CLIs love to chat. We only want the JSON.
        Strategy:
        1. Find ```json ... ``` Markdown blocks
        2. Find raw {...} structures
        3. Parse and validate
        """
        import json
        
        # Strategy 1: Markdown JSON block (most reliable)
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Strategy 2: Generic code block with JSON
        code_match = re.search(r'```\s*(\{[\s\S]*?\})\s*```', text)
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Find balanced braces containing "action"
        # This handles chatty responses like "Here's what I'll do: {...}"
        action_match = re.search(r'(\{[^{}]*"action"[^{}]*\})', text)
        if action_match:
            try:
                return json.loads(action_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Strategy 4: Greedy brace matching (last resort)
        # Find the outermost {...} structure
        brace_count = 0
        start_idx = -1
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    try:
                        return json.loads(text[start_idx:i+1])
                    except json.JSONDecodeError:
                        start_idx = -1  # Reset and try next block
        
        return None


# =============================================================================
# Convenience Functions
# =============================================================================

def create_shell_executor(
    tool: str = "claude",
    custom_args: list = None,
) -> ShellExecutor:
    """
    Create a shell executor for a native tool.
    
    Args:
        tool: Preset name or command (claude, ollama, gh-copilot, llm)
        custom_args: Override default arguments
        
    Returns:
        Configured ShellExecutor
    """
    preset = get_preset(tool)
    
    if preset:
        config = ExecutorConfig(
            type=ExecutorType.SHELL,
            command=preset.command,
            args=custom_args or preset.args,
        )
    else:
        config = ExecutorConfig(
            type=ExecutorType.SHELL,
            command=tool,
            args=custom_args or [],
        )
    
    return ShellExecutor(config)


def detect_available_tools() -> list:
    """Detect which native tools are available."""
    available = []
    
    for name, preset in NATIVE_PRESETS.items():
        if shutil.which(preset.command):
            available.append((name, preset.name, preset.command))
    
    return available
