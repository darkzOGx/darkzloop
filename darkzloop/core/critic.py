"""
darkzloop Critic (Reflection Module)

Adds a "Critic" node that validates actions before expensive execution.
This catches drift early - costs a few tokens to check, but saves thousands
by preventing the agent from going down rabbit holes.

The Critic is a lightweight check that asks:
"Does this plan match the original goal and spec?"
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum


class CritiqueVerdict(Enum):
    """Possible critic verdicts."""
    PROCEED = "proceed"        # Action looks good
    RETRY = "retry"            # Action has issues, try again
    ESCALATE = "escalate"      # Need human review
    ABORT = "abort"            # Stop the loop


@dataclass
class CritiqueCheck:
    """A single check the critic performs."""
    name: str
    passed: bool
    reason: str
    severity: str = "warning"  # "info", "warning", "error"


@dataclass
class CritiqueReport:
    """Full report from the critic."""
    verdict: CritiqueVerdict
    checks: List[CritiqueCheck]
    summary: str
    suggested_fix: Optional[str] = None
    
    def to_compact(self) -> str:
        """Compact representation for context."""
        failed = [c for c in self.checks if not c.passed]
        if not failed:
            return f"[CRITIC] ✅ {self.verdict.value}: {self.summary}"
        else:
            issues = ", ".join(c.name for c in failed)
            return f"[CRITIC] ⚠️ {self.verdict.value}: {issues} | {self.summary}"


class Critic:
    """
    The Critic validates agent actions against the goal and spec.
    
    Uses lightweight checks that can be run with a cheaper/faster model
    or even rule-based logic.
    """
    
    def __init__(self, goal: str, spec_constraints: List[str] = None):
        self.goal = goal
        self.spec_constraints = spec_constraints or []
        self.checks_run = 0
    
    def critique_action(
        self,
        proposed_action: dict,
        current_task: dict,
        context: str = ""
    ) -> CritiqueReport:
        """
        Critique a proposed action before execution.
        
        Args:
            proposed_action: The action the agent wants to take
            current_task: The task definition
            context: Additional context
            
        Returns:
            CritiqueReport with verdict and checks
        """
        self.checks_run += 1
        checks = []
        
        # Check 1: Action type is valid
        valid_actions = ["read_file", "write_file", "modify_file", "run_command", "search_code", "commit"]
        action_type = proposed_action.get("action", "")
        checks.append(CritiqueCheck(
            name="valid_action_type",
            passed=action_type in valid_actions,
            reason=f"Action '{action_type}' is {'valid' if action_type in valid_actions else 'invalid'}",
            severity="error" if action_type not in valid_actions else "info"
        ))
        
        # Check 2: Target file is in task scope
        target = proposed_action.get("target", "")
        allowed_files = (
            current_task.get("files_to_modify", []) + 
            current_task.get("files_to_create", [])
        )
        file_in_scope = not target or any(
            target.endswith(f) or f.endswith(target) 
            for f in allowed_files
        ) or action_type in ["run_command", "search_code", "read_file"]
        checks.append(CritiqueCheck(
            name="file_in_scope",
            passed=file_in_scope,
            reason=f"Target '{target}' is {'in' if file_in_scope else 'NOT in'} task scope",
            severity="error" if not file_in_scope else "info"
        ))
        
        # Check 3: Has a reason
        has_reason = bool(proposed_action.get("reason", "").strip())
        checks.append(CritiqueCheck(
            name="has_reason",
            passed=has_reason,
            reason="Action has explanation" if has_reason else "Missing reasoning",
            severity="warning" if not has_reason else "info"
        ))
        
        # Check 4: Content check for writes
        if action_type in ["write_file", "modify_file"]:
            content = proposed_action.get("content", "")
            has_content = bool(content.strip())
            checks.append(CritiqueCheck(
                name="has_content",
                passed=has_content,
                reason="Write has content" if has_content else "Empty write attempted",
                severity="error" if not has_content else "info"
            ))
        
        # Determine verdict
        errors = [c for c in checks if not c.passed and c.severity == "error"]
        warnings = [c for c in checks if not c.passed and c.severity == "warning"]
        
        if errors:
            verdict = CritiqueVerdict.RETRY
            summary = f"{len(errors)} error(s) found"
            suggested_fix = f"Fix: {errors[0].reason}"
        elif len(warnings) > 2:
            verdict = CritiqueVerdict.RETRY
            summary = f"Too many warnings ({len(warnings)})"
            suggested_fix = "Address warnings before proceeding"
        else:
            verdict = CritiqueVerdict.PROCEED
            summary = "Action approved"
            suggested_fix = None
        
        return CritiqueReport(
            verdict=verdict,
            checks=checks,
            summary=summary,
            suggested_fix=suggested_fix
        )
    
    def critique_plan(
        self,
        proposed_plan: str,
        task_description: str
    ) -> CritiqueReport:
        """
        Critique a plan before execution.
        Used in PLAN state to validate the approach.
        """
        checks = []
        
        # Check: Plan mentions the task
        mentions_task = task_description.lower()[:30] in proposed_plan.lower()
        checks.append(CritiqueCheck(
            name="addresses_task",
            passed=mentions_task,
            reason="Plan addresses the task" if mentions_task else "Plan may not address the task",
            severity="warning"
        ))
        
        # Check: Plan is not too long (token economy)
        reasonable_length = len(proposed_plan) < 2000
        checks.append(CritiqueCheck(
            name="reasonable_length",
            passed=reasonable_length,
            reason=f"Plan is {len(proposed_plan)} chars",
            severity="warning" if not reasonable_length else "info"
        ))
        
        # Check: Plan mentions specific files
        mentions_files = "/" in proposed_plan or ".py" in proposed_plan or ".rs" in proposed_plan
        checks.append(CritiqueCheck(
            name="mentions_files",
            passed=mentions_files,
            reason="Plan references files" if mentions_files else "Plan is vague about files",
            severity="warning" if not mentions_files else "info"
        ))
        
        failed = [c for c in checks if not c.passed]
        if len(failed) >= 2:
            verdict = CritiqueVerdict.RETRY
            summary = "Plan needs improvement"
        else:
            verdict = CritiqueVerdict.PROCEED
            summary = "Plan approved"
        
        return CritiqueReport(
            verdict=verdict,
            checks=checks,
            summary=summary
        )
    
    def goal_alignment_check(
        self,
        current_state: str,
        recent_actions: List[str]
    ) -> CritiqueReport:
        """
        High-level check: Is the loop still aligned with the original goal?
        Run this periodically to catch drift.
        """
        checks = []
        
        # This would ideally use an LLM call, but we'll do heuristics
        # In production, you'd call a cheaper model here
        
        # Heuristic: Check action diversity (stuck in a loop?)
        unique_actions = len(set(recent_actions))
        good_diversity = unique_actions >= min(3, len(recent_actions) * 0.5)
        checks.append(CritiqueCheck(
            name="action_diversity",
            passed=good_diversity,
            reason=f"{unique_actions} unique actions" if good_diversity else "Repetitive actions detected",
            severity="warning" if not good_diversity else "info"
        ))
        
        # Heuristic: Check for error keywords
        error_keywords = ["error", "failed", "cannot", "unable"]
        recent_text = " ".join(recent_actions).lower()
        error_count = sum(1 for kw in error_keywords if kw in recent_text)
        few_errors = error_count <= 2
        checks.append(CritiqueCheck(
            name="error_level",
            passed=few_errors,
            reason=f"{error_count} error indicators" if not few_errors else "Normal error level",
            severity="warning" if not few_errors else "info"
        ))
        
        if not good_diversity or error_count > 3:
            verdict = CritiqueVerdict.ESCALATE
            summary = "Loop may be drifting - human review recommended"
        else:
            verdict = CritiqueVerdict.PROCEED
            summary = "Loop on track"
        
        return CritiqueReport(
            verdict=verdict,
            checks=checks,
            summary=summary
        )


# =============================================================================
# Lightweight Critic for Cost Optimization
# =============================================================================

class RuleBasedCritic(Critic):
    """
    A purely rule-based critic that doesn't use any LLM calls.
    Use this for maximum speed/cost efficiency.
    """
    
    def __init__(self, goal: str, rules: List[dict] = None):
        super().__init__(goal)
        self.rules = rules or self._default_rules()
    
    def _default_rules(self) -> List[dict]:
        """Default validation rules."""
        return [
            {
                "name": "no_deletion_without_backup",
                "pattern": "rm -rf",
                "severity": "error",
                "message": "Dangerous deletion detected"
            },
            {
                "name": "no_force_push",
                "pattern": "git push --force",
                "severity": "error",
                "message": "Force push not allowed"
            },
            {
                "name": "no_direct_main",
                "pattern": "checkout main",
                "severity": "warning",
                "message": "Avoid direct work on main branch"
            },
        ]
    
    def apply_rules(self, content: str) -> List[CritiqueCheck]:
        """Apply all rules to content."""
        checks = []
        for rule in self.rules:
            violated = rule["pattern"].lower() in content.lower()
            checks.append(CritiqueCheck(
                name=rule["name"],
                passed=not violated,
                reason=rule["message"] if violated else f"{rule['name']} OK",
                severity=rule["severity"]
            ))
        return checks


# =============================================================================
# Integration Helper
# =============================================================================

def create_critic(goal: str, use_llm: bool = False) -> Critic:
    """Factory to create appropriate critic."""
    if use_llm:
        return Critic(goal)  # Would integrate with LLM
    else:
        return RuleBasedCritic(goal)


def quick_critique(
    action: dict,
    task: dict,
    goal: str
) -> Tuple[bool, str]:
    """
    Quick critique helper - returns (should_proceed, reason).
    Use this for inline validation.
    """
    critic = RuleBasedCritic(goal)
    report = critic.critique_action(action, task)
    
    should_proceed = report.verdict in [CritiqueVerdict.PROCEED]
    return should_proceed, report.summary


if __name__ == "__main__":
    # Demo critic
    critic = Critic(goal="Build event analytics API")
    
    # Test action critique
    action = {
        "action": "write_file",
        "target": "src/models/event.rs",
        "content": "pub struct Event { ... }",
        "reason": "Creating Event model per task 1.2"
    }
    
    task = {
        "id": "1.2",
        "description": "Create Event model",
        "files_to_modify": [],
        "files_to_create": ["src/models/event.rs"],
    }
    
    report = critic.critique_action(action, task)
    print("Critique Report:")
    print(f"  Verdict: {report.verdict.value}")
    print(f"  Summary: {report.summary}")
    for check in report.checks:
        status = "✅" if check.passed else "❌"
        print(f"  {status} {check.name}: {check.reason}")
    
    print("\nCompact format:")
    print(report.to_compact())
