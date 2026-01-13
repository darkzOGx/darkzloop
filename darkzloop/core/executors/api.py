"""
API Executor - Direct SDK Integration

Executes prompts via direct API calls to LLM providers:
- Anthropic (Claude)
- OpenAI (GPT-4)

Requires API keys but provides more control over parameters
and streaming capabilities.

Usage:
    executor = APIExecutor(ExecutorConfig(
        type=ExecutorType.API,
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        api_key="sk-ant-...",
    ))
    response = executor.execute(prompt)
"""

import os
import time
import json
import re
from typing import Tuple, Optional

from darkzloop.core.executors import (
    BaseExecutor, ExecutorConfig, ExecutorResponse,
    ExecutorType, register_executor
)


@register_executor(ExecutorType.API)
class APIExecutor(BaseExecutor):
    """
    Executes prompts via direct API calls.
    
    Supports:
    - Anthropic Claude API
    - OpenAI API
    
    Requires API keys but provides:
    - Full parameter control
    - Streaming support (future)
    - Token counting
    """
    
    def __init__(self, config: ExecutorConfig):
        super().__init__(config)
        self._client = None
    
    def execute(self, prompt: str, system_prompt: str = "") -> ExecutorResponse:
        """Execute prompt via API."""
        start_time = time.time()
        
        full_prompt = self.prepare_prompt(prompt, system_prompt)
        
        try:
            if self.config.provider == "anthropic":
                return self._execute_anthropic(full_prompt, system_prompt, start_time)
            elif self.config.provider == "openai":
                return self._execute_openai(full_prompt, system_prompt, start_time)
            else:
                return ExecutorResponse(
                    success=False,
                    content="",
                    raw_output="",
                    error=f"Unknown provider: {self.config.provider}",
                )
        except Exception as e:
            return ExecutorResponse(
                success=False,
                content="",
                raw_output="",
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )
    
    def _execute_anthropic(
        self, 
        prompt: str, 
        system_prompt: str,
        start_time: float
    ) -> ExecutorResponse:
        """Execute via Anthropic API."""
        try:
            import anthropic
        except ImportError:
            return ExecutorResponse(
                success=False,
                content="",
                raw_output="",
                error="anthropic package not installed. Run: pip install anthropic",
            )
        
        api_key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return ExecutorResponse(
                success=False,
                content="",
                raw_output="",
                error="No Anthropic API key. Set ANTHROPIC_API_KEY or configure in darkzloop.",
            )
        
        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=self.config.base_url,
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        response = client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            system=system_prompt if system_prompt else None,
            messages=messages,
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                content += block.text
        
        # Calculate tokens
        tokens_used = (
            response.usage.input_tokens + 
            response.usage.output_tokens
        )
        
        # Extract action
        action = self._extract_action(content)
        
        return ExecutorResponse(
            success=True,
            content=content,
            raw_output=content,
            action=action,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )
    
    def _execute_openai(
        self,
        prompt: str,
        system_prompt: str,
        start_time: float
    ) -> ExecutorResponse:
        """Execute via OpenAI API."""
        try:
            import openai
        except ImportError:
            return ExecutorResponse(
                success=False,
                content="",
                raw_output="",
                error="openai package not installed. Run: pip install openai",
            )
        
        api_key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return ExecutorResponse(
                success=False,
                content="",
                raw_output="",
                error="No OpenAI API key. Set OPENAI_API_KEY or configure in darkzloop.",
            )
        
        client = openai.OpenAI(
            api_key=api_key,
            base_url=self.config.base_url,
        )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            messages=messages,
        )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        content = response.choices[0].message.content or ""
        
        # Calculate tokens
        tokens_used = None
        if response.usage:
            tokens_used = (
                response.usage.prompt_tokens +
                response.usage.completion_tokens
            )
        
        # Extract action
        action = self._extract_action(content)
        
        return ExecutorResponse(
            success=True,
            content=content,
            raw_output=content,
            action=action,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )
    
    def is_available(self) -> Tuple[bool, str]:
        """Check if API is configured."""
        if self.config.provider == "anthropic":
            key = self.config.api_key or os.environ.get("ANTHROPIC_API_KEY")
            if key:
                return True, "Anthropic API configured"
            return False, "No ANTHROPIC_API_KEY set"
        
        elif self.config.provider == "openai":
            key = self.config.api_key or os.environ.get("OPENAI_API_KEY")
            if key:
                return True, "OpenAI API configured"
            return False, "No OPENAI_API_KEY set"
        
        return False, f"Unknown provider: {self.config.provider}"
    
    def _extract_action(self, text: str) -> Optional[dict]:
        """Extract JSON action from response text."""
        # Try to find JSON block
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*({\s*[\s\S]*?})\s*```',
            r'(\{[^{}]*"action"[^{}]*\})',
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        
        # Try to parse entire text as JSON
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
        
        return None


# =============================================================================
# Convenience Functions
# =============================================================================

def create_anthropic_executor(
    model: str = "claude-sonnet-4-20250514",
    api_key: str = None,
) -> APIExecutor:
    """Create an Anthropic API executor."""
    config = ExecutorConfig(
        type=ExecutorType.API,
        provider="anthropic",
        model=model,
        api_key=api_key,
    )
    return APIExecutor(config)


def create_openai_executor(
    model: str = "gpt-4o",
    api_key: str = None,
) -> APIExecutor:
    """Create an OpenAI API executor."""
    config = ExecutorConfig(
        type=ExecutorType.API,
        provider="openai",
        model=model,
        api_key=api_key,
    )
    return APIExecutor(config)
