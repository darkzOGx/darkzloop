"""
Mock Executor - For Testing

Provides predictable responses for testing the darkzloop framework
without making actual API calls.

Usage:
    executor = MockExecutor(ExecutorConfig(type=ExecutorType.MOCK))
    executor.set_response('{"action": "read_file", "path": "test.py"}')
    response = executor.execute(prompt)
"""

import time
from typing import Tuple, List, Optional
import json

from darkzloop.core.executors import (
    BaseExecutor, ExecutorConfig, ExecutorResponse,
    ExecutorType, register_executor
)


@register_executor(ExecutorType.MOCK)
class MockExecutor(BaseExecutor):
    """
    Mock executor for testing.
    
    Features:
    - Predictable responses
    - Response queue for multi-turn testing
    - Prompt capture for assertions
    - Simulated latency
    """
    
    def __init__(self, config: ExecutorConfig):
        super().__init__(config)
        self._responses: List[str] = []
        self._default_response: str = '{"action": "no_op", "reason": "mock"}'
        self._captured_prompts: List[str] = []
        self._latency_ms: int = 0
    
    def execute(self, prompt: str, system_prompt: str = "") -> ExecutorResponse:
        """Execute and return mock response."""
        start_time = time.time()
        
        # Capture the prompt
        self._captured_prompts.append(prompt)
        
        # Simulate latency
        if self._latency_ms > 0:
            time.sleep(self._latency_ms / 1000)
        
        # Get response
        if self._responses:
            content = self._responses.pop(0)
        else:
            content = self._default_response
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Parse action
        action = None
        try:
            action = json.loads(content)
        except json.JSONDecodeError:
            pass
        
        return ExecutorResponse(
            success=True,
            content=content,
            raw_output=content,
            action=action,
            duration_ms=duration_ms,
        )
    
    def is_available(self) -> Tuple[bool, str]:
        """Mock is always available."""
        return True, "Mock executor (testing mode)"
    
    # =============================================================================
    # Test Helpers
    # =============================================================================
    
    def set_response(self, response: str):
        """Set the next response to return."""
        self._responses = [response]
    
    def queue_responses(self, responses: List[str]):
        """Queue multiple responses for multi-turn testing."""
        self._responses = list(responses)
    
    def set_default_response(self, response: str):
        """Set the default response when queue is empty."""
        self._default_response = response
    
    def set_latency(self, ms: int):
        """Set simulated latency in milliseconds."""
        self._latency_ms = ms
    
    def get_captured_prompts(self) -> List[str]:
        """Get all captured prompts."""
        return list(self._captured_prompts)
    
    def get_last_prompt(self) -> Optional[str]:
        """Get the last captured prompt."""
        if self._captured_prompts:
            return self._captured_prompts[-1]
        return None
    
    def clear(self):
        """Clear all state."""
        self._responses = []
        self._captured_prompts = []
    
    # =============================================================================
    # Preset Responses for Common Actions
    # =============================================================================
    
    @staticmethod
    def read_file_response(path: str) -> str:
        """Generate a read_file action response."""
        return json.dumps({
            "thinking": f"I need to read {path} to understand its contents",
            "action": "read_file",
            "parameters": {"path": path}
        })
    
    @staticmethod
    def write_file_response(path: str, content: str) -> str:
        """Generate a write_file action response."""
        return json.dumps({
            "thinking": f"I will write the required content to {path}",
            "action": "write_file",
            "parameters": {"path": path, "content": content}
        })
    
    @staticmethod
    def run_command_response(command: str) -> str:
        """Generate a run_command action response."""
        return json.dumps({
            "thinking": f"I need to run: {command}",
            "action": "run_command",
            "parameters": {"command": command}
        })
    
    @staticmethod
    def done_response(reason: str = "Task completed") -> str:
        """Generate a done action response."""
        return json.dumps({
            "thinking": reason,
            "action": "done",
            "parameters": {}
        })
    
    @staticmethod
    def failure_response() -> str:
        """Generate a response that will fail to parse."""
        return "This is not valid JSON and will fail to parse"


# =============================================================================
# Convenience Functions
# =============================================================================

def create_mock_executor(
    default_response: str = None,
    latency_ms: int = 0,
) -> MockExecutor:
    """Create a mock executor for testing."""
    config = ExecutorConfig(type=ExecutorType.MOCK)
    executor = MockExecutor(config)
    
    if default_response:
        executor.set_default_response(default_response)
    
    if latency_ms > 0:
        executor.set_latency(latency_ms)
    
    return executor
