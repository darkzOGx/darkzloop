"""
Darkzloop Executors - Model-Agnostic Agent Execution

This module provides a unified interface for executing prompts against
various LLM backends, making darkzloop truly model-agnostic.

Supported backends:
- Shell/Native: Claude CLI, GitHub Copilot, Ollama, llm CLI
- API: Anthropic, OpenAI (requires API keys)
- Custom: Any executable that accepts prompts via stdin

The "Bring Your Own Auth" (BYOA) pattern allows users to leverage
existing subscriptions without managing separate API keys.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
import json
import re


class ExecutorType(Enum):
    """Types of executors available."""
    SHELL = "shell"      # Native CLI tools (claude, gh, ollama)
    API = "api"          # Direct SDK (anthropic, openai)
    MOCK = "mock"        # For testing


@dataclass
class ExecutorConfig:
    """Configuration for an executor."""
    type: ExecutorType = ExecutorType.SHELL

    # Shell executor settings
    command: str = "claude"
    args: List[str] = field(default_factory=lambda: ["--print"])
    strip_ansi: bool = True
    timeout_seconds: int = 300
    cwd: Optional[str] = None  # Working directory for shell commands
    
    # API executor settings
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.0
    
    # Common settings
    system_prompt_prefix: str = ""
    retry_attempts: int = 2
    
    @classmethod
    def from_dict(cls, data: dict) -> "ExecutorConfig":
        """Create config from dictionary."""
        exec_type = data.get("type", "shell")
        if exec_type == "shell":
            exec_type = ExecutorType.SHELL
        elif exec_type == "api":
            exec_type = ExecutorType.API
        else:
            exec_type = ExecutorType.MOCK
        
        return cls(
            type=exec_type,
            command=data.get("command", "claude"),
            args=data.get("args", ["--print"]),
            strip_ansi=data.get("strip_ansi", True),
            timeout_seconds=data.get("timeout_seconds", 300),
            cwd=data.get("cwd"),
            provider=data.get("provider", "anthropic"),
            model=data.get("model", "claude-sonnet-4-20250514"),
            api_key=data.get("api_key"),
            base_url=data.get("base_url"),
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 0.0),
            system_prompt_prefix=data.get("system_prompt_prefix", ""),
            retry_attempts=data.get("retry_attempts", 2),
        )
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "command": self.command,
            "args": self.args,
            "strip_ansi": self.strip_ansi,
            "timeout_seconds": self.timeout_seconds,
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system_prompt_prefix": self.system_prompt_prefix,
            "retry_attempts": self.retry_attempts,
        }


@dataclass
class ExecutorResponse:
    """Response from an executor."""
    success: bool
    content: str
    raw_output: str
    
    # Parsed action (if response contains JSON)
    action: Optional[Dict[str, Any]] = None
    
    # Metadata
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    
    def get_action(self) -> Optional[Dict[str, Any]]:
        """Extract action from response content."""
        if self.action:
            return self.action
        
        # Try to parse JSON from content
        try:
            # Look for JSON block
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', self.content)
            if json_match:
                return json.loads(json_match.group(1))
            
            # Try to parse entire content as JSON
            return json.loads(self.content)
        except (json.JSONDecodeError, AttributeError):
            return None


class BaseExecutor(ABC):
    """
    Abstract base class for all executors.
    
    Executors are responsible for:
    1. Taking a prompt (system + user context)
    2. Sending it to an LLM backend
    3. Parsing and returning the response
    """
    
    def __init__(self, config: ExecutorConfig):
        self.config = config
    
    @abstractmethod
    def execute(self, prompt: str, system_prompt: str = "") -> ExecutorResponse:
        """
        Execute a prompt and return the response.
        
        Args:
            prompt: The user prompt (context + task)
            system_prompt: Optional system instructions
            
        Returns:
            ExecutorResponse with the result
        """
        pass
    
    @abstractmethod
    def is_available(self) -> Tuple[bool, str]:
        """
        Check if this executor is available/configured.
        
        Returns:
            (is_available, message)
        """
        pass
    
    def prepare_prompt(self, prompt: str, system_prompt: str = "") -> str:
        """Prepare the full prompt with any prefixes."""
        full_system = ""
        
        if self.config.system_prompt_prefix:
            full_system += self.config.system_prompt_prefix + "\n\n"
        
        if system_prompt:
            full_system += system_prompt
        
        if full_system:
            return f"{full_system}\n\n---\n\n{prompt}"
        
        return prompt


# =============================================================================
# Executor Registry
# =============================================================================

_executor_registry: Dict[ExecutorType, type] = {}


def register_executor(executor_type: ExecutorType):
    """Decorator to register an executor class."""
    def decorator(cls):
        _executor_registry[executor_type] = cls
        return cls
    return decorator


def create_executor(config: ExecutorConfig) -> BaseExecutor:
    """Factory function to create the appropriate executor."""
    executor_class = _executor_registry.get(config.type)
    
    if executor_class is None:
        raise ValueError(f"No executor registered for type: {config.type}")
    
    return executor_class(config)


def get_available_executors() -> List[Tuple[ExecutorType, str]]:
    """List all registered executor types."""
    return [(t, c.__name__) for t, c in _executor_registry.items()]


# Import concrete implementations to register them
from darkzloop.core.executors.shell import ShellExecutor
from darkzloop.core.executors.api import APIExecutor
from darkzloop.core.executors.mock import MockExecutor

__all__ = [
    "ExecutorType",
    "ExecutorConfig", 
    "ExecutorResponse",
    "BaseExecutor",
    "create_executor",
    "get_available_executors",
    "ShellExecutor",
    "APIExecutor",
    "MockExecutor",
]
