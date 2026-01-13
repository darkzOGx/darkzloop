"""
Darkzloop Configuration Management

Handles merging of:
1. Global config (~/.darkzloop/config.json) - API keys, preferences
2. Local config (./darkzloop.json) - Project-specific settings

Global config is never committed to git.
Local config is project-specific and should be committed.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List


# =============================================================================
# Paths
# =============================================================================

def get_global_config_dir() -> Path:
    """Get the global config directory (~/.darkzloop/)."""
    # Respect XDG on Linux
    if os.name == "posix":
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / "darkzloop"
    
    return Path.home() / ".darkzloop"


def get_global_config_path() -> Path:
    """Get path to global config file."""
    return get_global_config_dir() / "config.json"


def get_local_config_path(project_root: Path = None) -> Path:
    """Get path to local config file."""
    root = project_root or Path.cwd()
    return root / "darkzloop.json"


def get_glossary_path(project_root: Path = None) -> Path:
    """Get path to semantic glossary."""
    root = project_root or Path.cwd()
    return root / ".darkzloop" / "glossary.json"


def get_state_path(project_root: Path = None) -> Path:
    """Get path to loop state file."""
    root = project_root or Path.cwd()
    return root / ".darkzloop" / "state.json"


# =============================================================================
# Configuration Classes
# =============================================================================

@dataclass
class AgentConfig:
    """Configuration for the agent/LLM."""
    # Executor mode: "shell" (native CLI) or "api" (direct SDK)
    mode: str = "shell"  # shell, api
    
    # Shell executor settings (native CLI tools)
    command: str = "claude"  # claude, ollama, gh, llm
    args: List[str] = field(default_factory=lambda: ["--print"])
    
    # API executor settings (direct SDK)
    provider: str = "anthropic"  # anthropic, openai
    model: str = "claude-sonnet-4-20250514"
    api_key: Optional[str] = None  # If None, reads from env
    base_url: Optional[str] = None  # For custom endpoints
    
    # Common settings
    timeout_seconds: int = 300
    max_tokens: int = 4096
    temperature: float = 0.0


@dataclass
class GlobalConfig:
    """
    Global configuration stored in ~/.darkzloop/config.json
    
    Contains sensitive data (API keys) and user preferences.
    Never committed to git.
    """
    # Agent settings
    agent: AgentConfig = field(default_factory=AgentConfig)
    
    # Default preferences
    default_attended: bool = True
    default_auto_commit: bool = True
    
    # Editor integration
    editor: str = "code"  # code, vim, nano, etc.
    
    # Telemetry (opt-in)
    telemetry_enabled: bool = False
    
    @classmethod
    def load(cls) -> "GlobalConfig":
        """Load global config from file or return defaults."""
        path = get_global_config_path()
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                return cls.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return cls()
    
    def save(self):
        """Save global config to file."""
        path = get_global_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def to_dict(self) -> dict:
        return {
            "agent": {
                "mode": self.agent.mode,
                "command": self.agent.command,
                "args": self.agent.args,
                "provider": self.agent.provider,
                "model": self.agent.model,
                "api_key": self.agent.api_key,
                "base_url": self.agent.base_url,
                "timeout_seconds": self.agent.timeout_seconds,
                "max_tokens": self.agent.max_tokens,
                "temperature": self.agent.temperature,
            },
            "default_attended": self.default_attended,
            "default_auto_commit": self.default_auto_commit,
            "editor": self.editor,
            "telemetry_enabled": self.telemetry_enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "GlobalConfig":
        agent_data = data.get("agent", {})
        return cls(
            agent=AgentConfig(
                mode=agent_data.get("mode", "shell"),
                command=agent_data.get("command", "claude"),
                args=agent_data.get("args", ["--print"]),
                provider=agent_data.get("provider", "anthropic"),
                model=agent_data.get("model", "claude-sonnet-4-20250514"),
                api_key=agent_data.get("api_key"),
                base_url=agent_data.get("base_url"),
                timeout_seconds=agent_data.get("timeout_seconds", 300),
                max_tokens=agent_data.get("max_tokens", 4096),
                temperature=agent_data.get("temperature", 0.0),
            ),
            default_attended=data.get("default_attended", True),
            default_auto_commit=data.get("default_auto_commit", True),
            editor=data.get("editor", "code"),
            telemetry_enabled=data.get("telemetry_enabled", False),
        )


@dataclass
class GateConfig:
    """Configuration for a quality gate tier."""
    enabled: bool = True
    commands: List[str] = field(default_factory=list)
    auto_fix_commands: List[str] = field(default_factory=list)
    on_failure: str = "task_failure"


@dataclass
class LocalConfig:
    """
    Project-specific configuration stored in ./darkzloop.json
    
    Defines project structure, gates, and execution settings.
    Should be committed to git.
    """
    # Project info
    project_name: str = ""
    project_type: str = "generic"  # rust, node, python, go, generic
    
    # Paths
    spec_path: str = "DARKZLOOP_SPEC.md"
    plan_path: str = "DARKZLOOP_PLAN.md"
    
    # Tiered gates
    tier1: GateConfig = field(default_factory=lambda: GateConfig(enabled=True))
    tier2: GateConfig = field(default_factory=lambda: GateConfig(enabled=True))
    tier3: GateConfig = field(default_factory=lambda: GateConfig(enabled=False))
    
    # Loop settings
    max_iterations: int = 100
    max_consecutive_failures: int = 3
    max_task_retries: int = 3
    
    # Features
    semantic_memory: bool = True
    enforce_read_before_write: bool = True
    parallel_enabled: bool = False
    auto_commit: bool = True
    
    @classmethod
    def load(cls, project_root: Path = None) -> "LocalConfig":
        """Load local config from file or return defaults."""
        path = get_local_config_path(project_root)
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                return cls.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return cls()
    
    def save(self, project_root: Path = None):
        """Save local config to file."""
        path = get_local_config_path(project_root)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def to_dict(self) -> dict:
        return {
            "version": "1.0",
            "project": {
                "name": self.project_name,
                "type": self.project_type,
            },
            "paths": {
                "spec": self.spec_path,
                "plan": self.plan_path,
            },
            "gates": {
                "tier1": {
                    "enabled": self.tier1.enabled,
                    "commands": self.tier1.commands,
                    "on_failure": self.tier1.on_failure,
                },
                "tier2": {
                    "enabled": self.tier2.enabled,
                    "commands": self.tier2.commands,
                    "auto_fix_commands": self.tier2.auto_fix_commands,
                    "on_failure": self.tier2.on_failure,
                },
                "tier3": {
                    "enabled": self.tier3.enabled,
                    "commands": self.tier3.commands,
                    "on_failure": self.tier3.on_failure,
                },
            },
            "loop": {
                "max_iterations": self.max_iterations,
                "max_consecutive_failures": self.max_consecutive_failures,
                "max_task_retries": self.max_task_retries,
            },
            "features": {
                "semantic_memory": self.semantic_memory,
                "enforce_read_before_write": self.enforce_read_before_write,
                "parallel_enabled": self.parallel_enabled,
                "auto_commit": self.auto_commit,
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "LocalConfig":
        project = data.get("project", {})
        paths = data.get("paths", {})
        gates = data.get("gates", {})
        loop = data.get("loop", {})
        features = data.get("features", {})
        
        def parse_gate(g: dict) -> GateConfig:
            return GateConfig(
                enabled=g.get("enabled", True),
                commands=g.get("commands", []),
                auto_fix_commands=g.get("auto_fix_commands", []),
                on_failure=g.get("on_failure", "task_failure"),
            )
        
        return cls(
            project_name=project.get("name", ""),
            project_type=project.get("type", "generic"),
            spec_path=paths.get("spec", "DARKZLOOP_SPEC.md"),
            plan_path=paths.get("plan", "DARKZLOOP_PLAN.md"),
            tier1=parse_gate(gates.get("tier1", {})),
            tier2=parse_gate(gates.get("tier2", {})),
            tier3=parse_gate(gates.get("tier3", {})),
            max_iterations=loop.get("max_iterations", 100),
            max_consecutive_failures=loop.get("max_consecutive_failures", 3),
            max_task_retries=loop.get("max_task_retries", 3),
            semantic_memory=features.get("semantic_memory", True),
            enforce_read_before_write=features.get("enforce_read_before_write", True),
            parallel_enabled=features.get("parallel_enabled", False),
            auto_commit=features.get("auto_commit", True),
        )


@dataclass
class MergedConfig:
    """
    Merged configuration combining global and local settings.
    
    Local settings override global defaults.
    """
    global_config: GlobalConfig
    local_config: LocalConfig
    project_root: Path
    
    @property
    def agent(self) -> AgentConfig:
        """Get agent configuration with env var fallbacks."""
        agent = self.global_config.agent
        
        # API key fallback to environment
        if not agent.api_key:
            if agent.provider == "anthropic":
                agent.api_key = os.environ.get("ANTHROPIC_API_KEY")
            elif agent.provider == "openai":
                agent.api_key = os.environ.get("OPENAI_API_KEY")
        
        return agent
    
    @property
    def attended(self) -> bool:
        return self.global_config.default_attended
    
    @property
    def auto_commit(self) -> bool:
        return self.local_config.auto_commit
    
    def to_runtime_config(self):
        """Convert to a LoopConfig for the runtime."""
        from darkzloop.core.runtime import LoopConfig, GateConfig as RuntimeGateConfig
        
        gates = []
        
        for tier_num, tier in [(1, self.local_config.tier1), 
                               (2, self.local_config.tier2),
                               (3, self.local_config.tier3)]:
            if tier.enabled:
                for i, cmd in enumerate(tier.commands):
                    auto_fix = tier.auto_fix_commands[i] if i < len(tier.auto_fix_commands) else None
                    gates.append(RuntimeGateConfig(
                        name=f"tier{tier_num}_{i}",
                        command=cmd,
                        tier=tier_num,
                        auto_fix_command=auto_fix,
                        on_failure=tier.on_failure,
                    ))
        
        return LoopConfig(
            spec_path=Path(self.local_config.spec_path),
            plan_path=Path(self.local_config.plan_path),
            project_root=self.project_root,
            max_iterations=self.local_config.max_iterations,
            max_consecutive_failures=self.local_config.max_consecutive_failures,
            max_task_retries=self.local_config.max_task_retries,
            gates=gates,
            enforce_read_before_write=self.local_config.enforce_read_before_write,
            enable_parallel=self.local_config.parallel_enabled,
        )


# =============================================================================
# Convenience Functions
# =============================================================================

def load_config(project_root: Path = None) -> MergedConfig:
    """Load and merge global + local configuration."""
    root = project_root or Path.cwd()
    return MergedConfig(
        global_config=GlobalConfig.load(),
        local_config=LocalConfig.load(root),
        project_root=root,
    )


def ensure_global_config() -> GlobalConfig:
    """Ensure global config exists, create if not."""
    config = GlobalConfig.load()
    if not get_global_config_path().exists():
        config.save()
    return config


def get_api_key(provider: str = "anthropic") -> Optional[str]:
    """Get API key from config or environment."""
    config = GlobalConfig.load()
    
    if config.agent.api_key:
        return config.agent.api_key
    
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY")
    elif provider == "openai":
        return os.environ.get("OPENAI_API_KEY")
    
    return None


def set_api_key(key: str, provider: str = "anthropic"):
    """Save API key to global config."""
    config = GlobalConfig.load()
    config.agent.api_key = key
    config.agent.provider = provider
    config.save()
