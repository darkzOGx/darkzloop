"""
Agent Executor Module

Handles invoking the configured LLM agent (Claude, Ollama, etc.) 
to generate plans or execute tasks.
"""
import subprocess
import sys
from typing import Optional, List, Tuple
from pathlib import Path
from rich.console import Console

from darkzloop.cli.config import load_config
from darkzloop.core.executors.presets import get_preset

console = Console()

def run_agent_command(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """
    Run the configured agent with a prompt.
    
    Args:
        prompt: The user prompt or task description.
        system_prompt: Optional system context (e.g., "You are a planning assistant")
        
    Returns:
        The text output from the agent, or None if failed.
    """
    config = load_config()
    agent_config = config.agent
    
    if agent_config.mode != "shell":
        # API mode not fully supported in this simplified executor yet
        console.print("[yellow]⚠️  Only 'shell' mode is currently supported for plan generation.[/yellow]")
        return None
        
    preset = get_preset(agent_config.command)
    if not preset:
        # Try matching by filename (e.g. C:\...\claude.cmd -> claude)
        cmd_path = Path(agent_config.command)
        preset = get_preset(cmd_path.stem)
        
    if not preset:
        # If still not found, try stripping extension for cases like 'claude.cmd' -> 'claude'
        if cmd_path.suffix in {'.exe', '.cmd', '.bat'}:
             preset = get_preset(cmd_path.stem)

    if not preset:
        console.print(f"[red]❌ Unknown command preset: {agent_config.command}[/red]")
        console.print("[dim]Use 'darkzloop config native <preset>' to reset configuration.[/dim]")
        return None
        
    start_cmd = [agent_config.command] + agent_config.args
    
    full_prompt = prompt
    if system_prompt:
        # Prepend system prompt if supported, or just add to prompt
        full_prompt = f"{system_prompt}\n\n{prompt}"
        
    try:
        # If the tool supports stdin (like 'claude' or 'ollama')
        if preset.stdin_mode:
            # We assume it takes prompt via stdin
            process = subprocess.run(
                start_cmd,
                input=full_prompt.encode('utf-8'),
                capture_output=True,
                check=False
            )
        else:
            # Pass via argument (like 'gh copilot suggest -t shell "prompt"')
            # This is trickier as argument position varies.
            # For now, simplistic appending if prompt_arg is configured
            if preset.prompt_arg:
                cmd = start_cmd + [preset.prompt_arg, full_prompt]
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    check=False
                )
            else:
                console.print(f"[red]❌ Preset {preset.name} does not support stdin or known prompt arg.[/red]")
                return None

        if process.returncode != 0:
            console.print(f"[red]❌ Agent command failed (Exit {process.returncode})[/red]")
            console.print(process.stderr.decode('utf-8', errors='replace'))
            return None
            
        return process.stdout.decode('utf-8', errors='replace')
        
    except FileNotFoundError:
        console.print(f"[red]❌ Command not found: {agent_config.command}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]❌ Error executing agent: {e}[/red]")
        return None

def execute_agent_task(prompt: str, context: dict = None) -> Tuple[bool, str, str]:
    """
    Adapter for DarkzloopRuntime.set_agent_executor.
    
    Args:
        prompt: The full prompt (system + context already rendered by runtime)
        context: Task dictionary (unused here as it's in the prompt)
        
    Returns:
        (success, output, error_message)
    """
    output = run_agent_command(prompt)
    if output:
        return True, output, ""
    return False, "", "Agent execution failed (check logs)"
