"""
Darkzloop Test Suite

Run with: pytest tests/ -v
"""

import pytest
from pathlib import Path


# ============================================================================
# FSM Tests
# ============================================================================

class TestFSM:
    """Test the Finite State Machine."""
    
    def test_initial_state(self):
        """FSM starts in INIT state."""
        from darkzloop.core.fsm import FSMContext, LoopState
        
        ctx = FSMContext()
        assert ctx.current_state == LoopState.INIT
    
    def test_valid_transition(self):
        """Valid transitions are allowed."""
        from darkzloop.core.fsm import FSMContext, LoopState
        
        ctx = FSMContext()
        ctx.transition(LoopState.PLAN, "Starting plan")
        assert ctx.current_state == LoopState.PLAN
    
    def test_invalid_transition(self):
        """Invalid transitions are rejected."""
        from darkzloop.core.fsm import FSMContext, LoopState, InvalidTransitionError
        
        ctx = FSMContext()
        with pytest.raises(InvalidTransitionError):
            # Can't go directly from INIT to COMPLETE
            ctx.transition(LoopState.COMPLETE)
    
    def test_terminal_state(self):
        """Terminal states are correctly identified."""
        from darkzloop.core.fsm import FSMContext, LoopState
        
        ctx = FSMContext()
        ctx.transition(LoopState.PLAN)
        ctx.transition(LoopState.EXECUTE)
        ctx.transition(LoopState.OBSERVE)
        ctx.transition(LoopState.CRITIQUE)
        ctx.transition(LoopState.CHECKPOINT)
        ctx.transition(LoopState.COMPLETE)
        
        assert ctx.is_terminal()
    
    def test_failure_tracking(self):
        """Consecutive failures are tracked."""
        from darkzloop.core.fsm import FSMContext, LoopState
        
        ctx = FSMContext()
        ctx.transition(LoopState.PLAN)
        ctx.transition(LoopState.EXECUTE)
        ctx.transition(LoopState.TASK_FAILURE, "Test failed")
        
        assert ctx.consecutive_failures == 1


# ============================================================================
# Manifest Tests
# ============================================================================

class TestManifest:
    """Test the Context Manifest."""
    
    def test_read_before_write(self):
        """Cannot write to files not read."""
        from darkzloop.core.manifest import ContextManifest
        
        manifest = ContextManifest()
        manifest.allowed_writes.add("test.py")
        
        allowed, reason = manifest.can_write("test.py")
        assert not allowed
        assert "must read" in reason
    
    def test_write_after_read(self):
        """Can write to files after reading."""
        from darkzloop.core.manifest import ContextManifest
        
        manifest = ContextManifest()
        manifest.allowed_writes.add("test.py")
        manifest.record_read("test.py", success=True)
        
        allowed, reason = manifest.can_write("test.py")
        assert allowed
    
    def test_create_without_read(self):
        """Can create new files without reading."""
        from darkzloop.core.manifest import ContextManifest
        
        manifest = ContextManifest()
        manifest.allowed_creates.add("new_file.py")
        
        allowed, reason = manifest.can_write("new_file.py")
        assert allowed
        assert reason == "allowed_create"
    
    def test_context_pruning(self):
        """Files pruned from context require re-read."""
        from darkzloop.core.manifest import ContextManifest
        
        manifest = ContextManifest()
        manifest.allowed_writes.add("test.py")
        manifest.record_read("test.py", success=True)
        
        # Can write after read
        allowed, _ = manifest.can_write("test.py")
        assert allowed
        
        # Prune from context
        manifest.prune_from_context("test.py")
        
        # Cannot write after prune
        allowed, reason = manifest.can_write("test.py")
        assert not allowed
        assert "pruned from context" in reason


# ============================================================================
# Semantic Expansion Tests
# ============================================================================

class TestSemanticExpansion:
    """Test semantic term expansion."""
    
    def test_builtin_synonyms(self):
        """Built-in synonyms are expanded."""
        from darkzloop.core.semantic import SemanticExpander
        
        expander = SemanticExpander(Path("."))
        result = expander.expand("billing")
        
        assert "billing" in result
        assert "invoice" in result
        assert "payment" in result
    
    def test_original_term_highest_confidence(self):
        """Original term has highest confidence."""
        from darkzloop.core.semantic import SemanticExpander
        
        expander = SemanticExpander(Path("."))
        result = expander.expand("login")
        
        assert result["login"] == 1.0
        assert all(conf < 1.0 for term, conf in result.items() if term != "login")
    
    def test_bidirectional_synonyms(self):
        """Synonyms work in both directions."""
        from darkzloop.core.semantic import SemanticExpander
        
        expander = SemanticExpander(Path("."))
        
        # "auth" should find "login"
        auth_result = expander.expand("auth")
        assert "login" in auth_result
        
        # "login" should find "auth"
        login_result = expander.expand("login")
        assert "auth" in login_result


# ============================================================================
# Executor Tests
# ============================================================================

class TestExecutors:
    """Test executor infrastructure."""
    
    def test_mock_executor(self):
        """Mock executor returns queued responses."""
        from darkzloop.core.executors import ExecutorConfig, ExecutorType
        from darkzloop.core.executors.mock import MockExecutor
        
        config = ExecutorConfig(type=ExecutorType.MOCK)
        executor = MockExecutor(config)
        
        # Set a response
        executor.set_response('{"action": "done"}')
        
        response = executor.execute("test prompt")
        assert response.success
        assert response.action["action"] == "done"
    
    def test_executor_factory(self):
        """Executor factory creates correct type."""
        from darkzloop.core.executors import create_executor, ExecutorConfig, ExecutorType
        from darkzloop.core.executors.mock import MockExecutor
        
        config = ExecutorConfig(type=ExecutorType.MOCK)
        executor = create_executor(config)
        
        assert isinstance(executor, MockExecutor)
    
    def test_preset_loading(self):
        """Presets load correctly."""
        from darkzloop.core.executors.presets import get_preset, list_presets
        
        presets = list_presets()
        assert "claude" in presets
        assert "ollama" in presets
        
        claude = get_preset("claude")
        assert claude.command == "claude"
        assert "--dangerously-skip-permissions" in claude.args


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests (require more setup)."""
    
    @pytest.mark.skip(reason="Requires project directory setup")
    def test_full_fsm_cycle(self):
        """Full FSM cycle from INIT to COMPLETE."""
        pass
    
    @pytest.mark.skip(reason="Requires native tool installed")
    def test_shell_executor_real(self):
        """Real shell executor test."""
        pass
