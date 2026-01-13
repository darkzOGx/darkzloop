"""
darkzloop Context Manifest

Enforces "read before write" - the agent must explicitly read a file
before it's allowed to modify it. This prevents the "context collapse"
problem where the agent tries to edit files it hasn't seen.

The Plan must declare a Context Manifest:
- files_to_read: Files that MUST be read before any writes
- files_to_write: Files that may be written/modified

The FSM blocks write actions to files not in the manifest or not yet read.
"""

from dataclasses import dataclass, field
from typing import Set, List, Dict, Optional
from enum import Enum
from pathlib import Path


class FileAccessType(Enum):
    """Type of file access."""
    READ = "read"
    WRITE = "write"
    CREATE = "create"


@dataclass
class FileAccess:
    """Record of a file access."""
    path: str
    access_type: FileAccessType
    timestamp: str
    success: bool


@dataclass
class ContextManifest:
    """
    Declares which files the task needs to access.
    
    The manifest is derived from the task definition:
    - files_to_read: Pattern files + files being modified (must read first)
    - files_to_write: Files being modified or created
    
    The FSM enforces that files are read before they're written.
    
    IMPORTANT: Tracks whether files are still in context window.
    If context compression removes a file, can_write flips to False.
    """
    
    # Required reads before any writes
    required_reads: Set[str] = field(default_factory=set)
    
    # Allowed writes (only after required reads are done)
    allowed_writes: Set[str] = field(default_factory=set)
    
    # Allowed creates (new files, no read required)
    allowed_creates: Set[str] = field(default_factory=set)
    
    # Tracking - files that HAVE been read
    files_read: Set[str] = field(default_factory=set)
    
    # Tracking - files currently IN CONTEXT (may be pruned)
    files_in_context: Set[str] = field(default_factory=set)
    
    # Tracking - files written this iteration
    files_written: Set[str] = field(default_factory=set)
    
    # Access log for audit
    access_log: List[FileAccess] = field(default_factory=list)
    
    # Context window integration
    context_token_budget: int = 4000  # If context exceeds this, oldest files are "pruned"
    file_token_counts: Dict[str, int] = field(default_factory=dict)  # path -> approx tokens
    
    @classmethod
    def from_task(cls, task: dict) -> "ContextManifest":
        """
        Build manifest from a task definition.
        
        Rules:
        - Pattern files (reference_files) must be read
        - Files to modify must be read before writing
        - Files to create can be written without reading
        """
        required_reads = set()
        allowed_writes = set()
        allowed_creates = set()
        
        # Pattern files must be read
        for f in task.get("reference_files", []):
            required_reads.add(f)
        
        # Files to modify: must read first, then can write
        for f in task.get("files_to_modify", []):
            required_reads.add(f)
            allowed_writes.add(f)
        
        # Files to create: can write directly
        for f in task.get("files_to_create", []):
            allowed_creates.add(f)
        
        return cls(
            required_reads=required_reads,
            allowed_writes=allowed_writes,
            allowed_creates=allowed_creates,
        )
    
    def record_read(self, path: str, success: bool = True, token_count: int = 0) -> bool:
        """
        Record a file read.
        
        Also adds file to context window tracking.
        """
        from datetime import datetime
        
        self.access_log.append(FileAccess(
            path=path,
            access_type=FileAccessType.READ,
            timestamp=datetime.now().isoformat(),
            success=success,
        ))
        
        if success:
            self.files_read.add(path)
            self.files_in_context.add(path)
            # Also add normalized versions
            normalized = str(Path(path))
            self.files_read.add(normalized)
            self.files_in_context.add(normalized)
            
            if token_count > 0:
                self.file_token_counts[path] = token_count
        
        return success
    
    def prune_from_context(self, path: str):
        """
        Mark a file as pruned from context window.
        
        Called by ContextManager when rolling window removes the file.
        After this, can_write will return False until file is re-read.
        """
        self.files_in_context.discard(path)
        self.files_in_context.discard(str(Path(path)))
    
    def is_in_context(self, path: str) -> bool:
        """Check if a file is currently in the context window."""
        normalized = str(Path(path))
        return path in self.files_in_context or normalized in self.files_in_context
    
    def can_write(self, path: str) -> tuple[bool, str]:
        """
        Check if writing to a path is allowed.
        
        Returns (allowed, reason).
        
        IMPORTANT: Checks if file is CURRENTLY in context, not just
        if it was ever read. If context was pruned, must re-read.
        """
        normalized = str(Path(path))
        
        # Check if it's a new file (create)
        if path in self.allowed_creates or normalized in self.allowed_creates:
            return True, "allowed_create"
        
        # Check if it's an allowed write
        if path not in self.allowed_writes and normalized not in self.allowed_writes:
            return False, f"file '{path}' not in allowed_writes manifest"
        
        # Check if we've read it
        if path not in self.files_read and normalized not in self.files_read:
            matching_reads = [r for r in self.required_reads if r in path or path in r]
            if matching_reads:
                return False, f"must read '{matching_reads[0]}' before writing '{path}'"
            return False, f"must read '{path}' before writing"
        
        # CRITICAL: Check if file is STILL in context
        if not self.is_in_context(path):
            return False, f"'{path}' was read but pruned from context - must re-read"
        
        return True, "allowed_write"
    
    def get_hint_for_failure(self, path: str) -> Optional[str]:
        """
        Generate a hint for the agent when can_write fails.
        
        This hint should be injected into the next prompt to help
        the agent understand why it failed and what to do.
        """
        allowed, reason = self.can_write(path)
        if allowed:
            return None
        
        if "pruned from context" in reason:
            return (
                f"⚠️ SYSTEM NOTE: You attempted to edit '{path}', but it fell out of "
                f"your context window. You MUST run `read_file {path}` again before editing."
            )
        elif "must read" in reason:
            return (
                f"⚠️ SYSTEM NOTE: You attempted to edit '{path}' without reading it first. "
                f"You MUST run `read_file {path}` before making any modifications."
            )
        elif "not in allowed_writes" in reason:
            return (
                f"⚠️ SYSTEM NOTE: You attempted to edit '{path}', but this file is not "
                f"in the task's allowed files. Check your task definition."
            )
        
        return f"⚠️ SYSTEM NOTE: Cannot write to '{path}': {reason}"
    
    def record_write(self, path: str, success: bool = True) -> tuple[bool, str]:
        """
        Attempt to record a file write.
        
        Returns (allowed, reason).
        Blocks if file hasn't been read first (for modifications).
        """
        from datetime import datetime
        
        allowed, reason = self.can_write(path)
        
        if not allowed:
            self.access_log.append(FileAccess(
                path=path,
                access_type=FileAccessType.WRITE,
                timestamp=datetime.now().isoformat(),
                success=False,
            ))
            return False, reason
        
        access_type = FileAccessType.CREATE if path in self.allowed_creates else FileAccessType.WRITE
        
        self.access_log.append(FileAccess(
            path=path,
            access_type=access_type,
            timestamp=datetime.now().isoformat(),
            success=success,
        ))
        
        if success:
            self.files_written.add(path)
        
        return True, reason
    
    def get_unread_required(self) -> List[str]:
        """Get list of required files that haven't been read yet."""
        return [f for f in self.required_reads if f not in self.files_read]
    
    def is_complete(self) -> bool:
        """Check if all required reads have been done."""
        return len(self.get_unread_required()) == 0
    
    def get_status(self) -> dict:
        """Get manifest status."""
        return {
            "required_reads": list(self.required_reads),
            "files_read": list(self.files_read),
            "unread_required": self.get_unread_required(),
            "allowed_writes": list(self.allowed_writes),
            "files_written": list(self.files_written),
            "allowed_creates": list(self.allowed_creates),
            "is_complete": self.is_complete(),
        }
    
    def to_prompt_fragment(self) -> str:
        """Generate prompt fragment for agent context."""
        unread = self.get_unread_required()
        
        lines = ["CONTEXT MANIFEST:"]
        
        if unread:
            lines.append(f"  ⚠️ MUST READ FIRST: {unread}")
        else:
            lines.append(f"  ✓ All required files read")
        
        lines.append(f"  Can modify: {list(self.allowed_writes)}")
        lines.append(f"  Can create: {list(self.allowed_creates)}")
        
        return "\n".join(lines)


class ManifestEnforcer:
    """
    Enforces context manifest rules in the FSM.
    
    Integrates with the loop to block invalid file operations.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.manifests: Dict[str, ContextManifest] = {}  # task_id -> manifest
        self.current_task_id: Optional[str] = None
    
    def start_task(self, task_id: str, task: dict):
        """Start tracking a new task."""
        self.current_task_id = task_id
        self.manifests[task_id] = ContextManifest.from_task(task)
    
    def get_current_manifest(self) -> Optional[ContextManifest]:
        """Get the current task's manifest."""
        if not self.current_task_id:
            return None
        return self.manifests.get(self.current_task_id)
    
    def validate_action(self, action: dict) -> tuple[bool, str]:
        """
        Validate an action against the manifest.
        
        Args:
            action: AgentAction dict with 'action' and 'target'
            
        Returns:
            (valid, reason)
        """
        manifest = self.get_current_manifest()
        if not manifest:
            return True, "no_manifest"  # No enforcement if no manifest
        
        action_type = action.get("action", "")
        target = action.get("target", "")
        
        if action_type == "read_file":
            manifest.record_read(target)
            return True, "read_recorded"
        
        elif action_type in ["write_file", "modify_file"]:
            return manifest.record_write(target)
        
        elif action_type == "search_code":
            # Search is always allowed
            return True, "search_allowed"
        
        elif action_type == "run_command":
            # Commands are allowed (tests, etc.)
            return True, "command_allowed"
        
        return True, "other_action"
    
    def get_blocking_reads(self) -> List[str]:
        """Get files that must be read before the task can write."""
        manifest = self.get_current_manifest()
        if not manifest:
            return []
        return manifest.get_unread_required()
    
    def get_enforcement_prompt(self) -> str:
        """Get prompt fragment explaining manifest enforcement."""
        manifest = self.get_current_manifest()
        if not manifest:
            return ""
        
        blocking = self.get_blocking_reads()
        
        if blocking:
            return (
                f"\n⚠️ CONTEXT MANIFEST ENFORCEMENT:\n"
                f"You MUST read these files before any writes:\n"
                f"  {blocking}\n"
                f"The FSM will block write attempts until these are read.\n"
            )
        
        return manifest.to_prompt_fragment()


def create_enforcer() -> ManifestEnforcer:
    """Factory function for manifest enforcer."""
    return ManifestEnforcer()


if __name__ == "__main__":
    # Demo
    task = {
        "id": "2.1",
        "description": "Create events handler",
        "files_to_modify": ["src/api/routes.rs"],
        "files_to_create": ["src/api/handlers/events.rs"],
        "reference_files": ["src/api/handlers/users.rs"],
        "spec_sections": ["3.1"],
        "acceptance_criteria": "Handler compiles",
    }
    
    manifest = ContextManifest.from_task(task)
    
    print("Initial manifest:")
    print(manifest.to_prompt_fragment())
    print()
    
    # Try to write without reading - should fail
    allowed, reason = manifest.can_write("src/api/routes.rs")
    print(f"Can write routes.rs before reading? {allowed} ({reason})")
    
    # Read the required files
    manifest.record_read("src/api/handlers/users.rs")
    manifest.record_read("src/api/routes.rs")
    
    print("\nAfter reading required files:")
    print(manifest.to_prompt_fragment())
    
    # Now try to write - should succeed
    allowed, reason = manifest.can_write("src/api/routes.rs")
    print(f"\nCan write routes.rs after reading? {allowed} ({reason})")
    
    # Creating new file - should work without read
    allowed, reason = manifest.can_write("src/api/handlers/events.rs")
    print(f"Can create events.rs? {allowed} ({reason})")
