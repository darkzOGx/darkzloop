"""
darkzloop File Locking for DAG Parallelism

When running tasks in parallel, multiple branches might try to edit
the same file, causing merge conflicts the agent can't solve.

Solution: File-aware task scheduling.
- Each task claims the files it needs
- The DAG scheduler respects file locks
- Tasks that need the same file run sequentially

Rule: "If Branch A claims routes.rs, Branch B acts on auth.rs.
       If both need routes.rs, they must run sequentially."
"""

from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional, Tuple
from enum import Enum
from datetime import datetime
import threading


class LockType(Enum):
    """Type of file lock."""
    READ = "read"      # Multiple readers allowed
    WRITE = "write"    # Exclusive access required


@dataclass
class FileLock:
    """A lock on a file."""
    path: str
    lock_type: LockType
    holder: str  # task_id
    acquired_at: str
    
    def conflicts_with(self, other: "FileLock") -> bool:
        """Check if this lock conflicts with another."""
        if self.path != other.path:
            return False
        
        # Write locks conflict with everything
        if self.lock_type == LockType.WRITE or other.lock_type == LockType.WRITE:
            return True
        
        # Multiple read locks are OK
        return False


@dataclass
class TaskFileClaims:
    """Files a task needs to access."""
    task_id: str
    read_files: Set[str] = field(default_factory=set)
    write_files: Set[str] = field(default_factory=set)
    
    @classmethod
    def from_task(cls, task: dict) -> "TaskFileClaims":
        """Build claims from task definition."""
        task_id = task.get("id", "unknown")
        
        read_files = set()
        write_files = set()
        
        # Pattern files are read
        for f in task.get("reference_files", []):
            read_files.add(f)
        
        # Files to modify are both read and write
        for f in task.get("files_to_modify", []):
            read_files.add(f)
            write_files.add(f)
        
        # Files to create are write
        for f in task.get("files_to_create", []):
            write_files.add(f)
        
        return cls(
            task_id=task_id,
            read_files=read_files,
            write_files=write_files,
        )
    
    def get_all_files(self) -> Set[str]:
        """Get all files this task touches."""
        return self.read_files | self.write_files


class FileLockManager:
    """
    Manages file locks for parallel task execution.
    
    Thread-safe for async DAG execution.
    """
    
    def __init__(self):
        self.locks: Dict[str, FileLock] = {}  # path -> lock
        self._lock = threading.RLock()
        self.lock_history: List[Tuple[str, str, str]] = []  # (action, path, task_id)
    
    def can_acquire(self, path: str, lock_type: LockType, task_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a lock can be acquired.
        
        Returns (can_acquire, blocking_task_id or None)
        """
        with self._lock:
            existing = self.locks.get(path)
            if not existing:
                return True, None
            
            # Same task can upgrade/re-acquire
            if existing.holder == task_id:
                return True, None
            
            # Check for conflict
            new_lock = FileLock(path, lock_type, task_id, "")
            if existing.conflicts_with(new_lock):
                return False, existing.holder
            
            return True, None
    
    def acquire(self, path: str, lock_type: LockType, task_id: str) -> Tuple[bool, str]:
        """
        Attempt to acquire a lock.
        
        Returns (success, message)
        """
        with self._lock:
            can_acquire, blocker = self.can_acquire(path, lock_type, task_id)
            
            if not can_acquire:
                return False, f"blocked by task {blocker}"
            
            self.locks[path] = FileLock(
                path=path,
                lock_type=lock_type,
                holder=task_id,
                acquired_at=datetime.now().isoformat()
            )
            
            self.lock_history.append(("acquire", path, task_id))
            return True, "acquired"
    
    def release(self, path: str, task_id: str) -> bool:
        """
        Release a lock.
        
        Only the holder can release.
        """
        with self._lock:
            existing = self.locks.get(path)
            if not existing:
                return True  # Nothing to release
            
            if existing.holder != task_id:
                return False  # Not the holder
            
            del self.locks[path]
            self.lock_history.append(("release", path, task_id))
            return True
    
    def release_all(self, task_id: str):
        """Release all locks held by a task."""
        with self._lock:
            to_release = [
                path for path, lock in self.locks.items()
                if lock.holder == task_id
            ]
            for path in to_release:
                del self.locks[path]
                self.lock_history.append(("release", path, task_id))
    
    def get_locks_for_task(self, task_id: str) -> List[FileLock]:
        """Get all locks held by a task."""
        with self._lock:
            return [
                lock for lock in self.locks.values()
                if lock.holder == task_id
            ]
    
    def get_blocking_tasks(self, claims: TaskFileClaims) -> Set[str]:
        """
        Get tasks that would block the given claims.
        
        Used by DAG scheduler to determine if a task can run.
        """
        blocking = set()
        
        with self._lock:
            # Check write claims against all existing locks
            for path in claims.write_files:
                existing = self.locks.get(path)
                if existing and existing.holder != claims.task_id:
                    blocking.add(existing.holder)
            
            # Check read claims against write locks
            for path in claims.read_files:
                existing = self.locks.get(path)
                if existing and existing.lock_type == LockType.WRITE and existing.holder != claims.task_id:
                    blocking.add(existing.holder)
        
        return blocking


class FileAwareDAGScheduler:
    """
    DAG scheduler that respects file locks.
    
    Reorders parallel groups to avoid file conflicts.
    """
    
    def __init__(self, lock_manager: FileLockManager = None):
        self.lock_manager = lock_manager or FileLockManager()
        self.task_claims: Dict[str, TaskFileClaims] = {}
    
    def register_task(self, task: dict):
        """Register a task's file claims."""
        claims = TaskFileClaims.from_task(task)
        self.task_claims[claims.task_id] = claims
    
    def analyze_conflicts(self, task_ids: List[str]) -> Dict[str, Set[str]]:
        """
        Analyze file conflicts between tasks.
        
        Returns dict of task_id -> set of conflicting task_ids
        """
        conflicts: Dict[str, Set[str]] = {tid: set() for tid in task_ids}
        
        for i, task_a in enumerate(task_ids):
            claims_a = self.task_claims.get(task_a)
            if not claims_a:
                continue
            
            for task_b in task_ids[i+1:]:
                claims_b = self.task_claims.get(task_b)
                if not claims_b:
                    continue
                
                # Check for write conflicts
                # A writes file that B reads or writes
                a_writes = claims_a.write_files
                b_all = claims_b.get_all_files()
                
                # B writes file that A reads or writes
                b_writes = claims_b.write_files
                a_all = claims_a.get_all_files()
                
                if a_writes & b_all or b_writes & a_all:
                    conflicts[task_a].add(task_b)
                    conflicts[task_b].add(task_a)
        
        return conflicts
    
    def split_parallel_group(self, task_ids: List[str]) -> List[List[str]]:
        """
        Split a parallel group into sub-groups that don't conflict.
        
        Uses a greedy coloring algorithm.
        """
        if len(task_ids) <= 1:
            return [task_ids]
        
        conflicts = self.analyze_conflicts(task_ids)
        
        # Greedy coloring
        groups: List[List[str]] = []
        assigned: Set[str] = set()
        
        for task_id in task_ids:
            if task_id in assigned:
                continue
            
            # Find a group where this task has no conflicts
            placed = False
            for group in groups:
                has_conflict = any(task_id in conflicts.get(other, set()) for other in group)
                if not has_conflict:
                    group.append(task_id)
                    assigned.add(task_id)
                    placed = True
                    break
            
            if not placed:
                # Start new group
                groups.append([task_id])
                assigned.add(task_id)
        
        return groups
    
    def reorder_execution_plan(
        self,
        parallel_groups: List[List[str]]
    ) -> List[List[str]]:
        """
        Reorder execution plan to respect file locks.
        
        Input: [[A, B, C], [D, E]]  (original parallel groups)
        Output: [[A, C], [B], [D, E]]  (if A/C and B conflict)
        """
        result = []
        
        for group in parallel_groups:
            sub_groups = self.split_parallel_group(group)
            result.extend(sub_groups)
        
        return result
    
    def can_start_task(self, task_id: str) -> Tuple[bool, List[str]]:
        """
        Check if a task can start now (no file conflicts).
        
        Returns (can_start, list of blocking tasks)
        """
        claims = self.task_claims.get(task_id)
        if not claims:
            return True, []
        
        blocking = self.lock_manager.get_blocking_tasks(claims)
        return len(blocking) == 0, list(blocking)
    
    def acquire_for_task(self, task_id: str) -> Tuple[bool, List[str]]:
        """
        Acquire all locks for a task before execution.
        
        Returns (success, list of failed paths)
        """
        claims = self.task_claims.get(task_id)
        if not claims:
            return True, []
        
        failed = []
        
        # Acquire write locks first (exclusive)
        for path in claims.write_files:
            success, _ = self.lock_manager.acquire(path, LockType.WRITE, task_id)
            if not success:
                failed.append(path)
        
        # Acquire read locks
        for path in claims.read_files - claims.write_files:
            success, _ = self.lock_manager.acquire(path, LockType.READ, task_id)
            if not success:
                failed.append(path)
        
        if failed:
            # Rollback
            self.lock_manager.release_all(task_id)
        
        return len(failed) == 0, failed
    
    def release_for_task(self, task_id: str):
        """Release all locks for a task after execution."""
        self.lock_manager.release_all(task_id)
    
    def get_conflict_report(self) -> str:
        """Generate a report of file conflicts."""
        lines = ["File Conflict Analysis:"]
        
        all_tasks = list(self.task_claims.keys())
        conflicts = self.analyze_conflicts(all_tasks)
        
        has_conflicts = False
        for task_id, conflicting in conflicts.items():
            if conflicting:
                has_conflicts = True
                claims = self.task_claims[task_id]
                lines.append(f"\n  {task_id}:")
                lines.append(f"    writes: {claims.write_files}")
                lines.append(f"    conflicts with: {conflicting}")
        
        if not has_conflicts:
            lines.append("  No file conflicts detected. All tasks can run in parallel.")
        
        return "\n".join(lines)


def create_file_aware_scheduler() -> FileAwareDAGScheduler:
    """Factory function for file-aware scheduler."""
    return FileAwareDAGScheduler()


if __name__ == "__main__":
    # Demo
    scheduler = create_file_aware_scheduler()
    
    # Register tasks
    tasks = [
        {"id": "1.1", "files_to_modify": ["src/models/user.rs"], "files_to_create": [], "reference_files": []},
        {"id": "1.2", "files_to_modify": [], "files_to_create": ["src/models/event.rs"], "reference_files": ["src/models/user.rs"]},
        {"id": "2.1", "files_to_modify": ["src/api/routes.rs"], "files_to_create": [], "reference_files": []},
        {"id": "2.2", "files_to_modify": ["src/api/routes.rs"], "files_to_create": [], "reference_files": []},  # Conflicts with 2.1!
    ]
    
    for task in tasks:
        scheduler.register_task(task)
    
    print(scheduler.get_conflict_report())
    
    # Original plan: [[1.1, 1.2], [2.1, 2.2]]
    original = [["1.1", "1.2"], ["2.1", "2.2"]]
    print(f"\nOriginal parallel groups: {original}")
    
    # Reorder to avoid conflicts
    reordered = scheduler.reorder_execution_plan(original)
    print(f"Reordered (conflict-free): {reordered}")
    
    # Test lock acquisition
    print("\nLock acquisition test:")
    success, failed = scheduler.acquire_for_task("2.1")
    print(f"  2.1 acquired locks: {success}")
    
    success, failed = scheduler.acquire_for_task("2.2")
    print(f"  2.2 can acquire while 2.1 holds routes.rs: {success}")
    
    scheduler.release_for_task("2.1")
    print("  2.1 released locks")
    
    success, failed = scheduler.acquire_for_task("2.2")
    print(f"  2.2 can acquire now: {success}")
