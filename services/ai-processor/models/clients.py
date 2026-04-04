"""
AI model client wrappers for each provider.
Implements circuit breaker pattern and fallback logic.
"""
import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar

import httpx
from openai import AsyncOpenAI, OpenAIError
import anthropic

from models import ModelProvider, ModelPrediction, GradeLevel, SportType

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CircuitBreakerState:
    """Circuit breaker state."""
    failures: int = 0
    last_failure_time: Optional[float] = None
    state: str = "closed"  # closed, open, half-open


class CircuitBreaker:
    """Circuit breaker decorator for model calls."""
    
    _states: Dict[str, CircuitBreakerState] = {}
    
    def __init__(self, name: str, threshold: int = 5, timeout: float = 60.0):
        self.name = name
        self.threshold = threshold
        self.timeout = timeout
        if name not in self._states:
            self._states[name] = CircuitBreakerState()
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        async def async_wrapper(*args, **kwargs) -> T:
            state = self._states[self.name]
            
            # Check if circuit is open
            if state.state == "open":
                if state.last_failure_time and (time.time() - state.last_failure_time) > self.timeout:
                    state.state = "half-open"
                    logger.info(f"Circuit breaker for {self.name} entering half-open state")
                else:
                    raise Exception(f"Circuit breaker for {self.name} is OPEN")
            
            try:
                result = await func(*args, **kwargs)
                # Success - reset circuit
                if state.state == "half-open":
                    state.state = "closed"
                    state.failures = 0
                    logger.info(f"Circuit breaker for {self.name} closed")
                return result
            except Exception as e:
                state.failures += 1
                state.last_failure_time = time.time()
                if state.failures >= self.threshold:
                    state.state = "open"
                    logger.error(f"Circuit breaker for {self.name} opened after {state.failures} failures")
                raise e
        
        return async_wrapper


class BaseModelClient(ABC):
    """Base class for AI model clients."""
    
    def __init__(self, provider: ModelProvider, api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key or os.getenv(f"{provider.upper()}_API_KEY")
        self.client: Optional[Any] = None
        self.circuit_breaker = CircuitBreaker(
            name=provider.value,
            threshold=5,
            timeout=60.0
        )
        self._init_client()
    
    @abstractmethod
    def _init_client(self) -> None:
        """Initialize the API client."""
        pass
    
    @abstractmethod
    async def _call_api(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Make the actual API call."""
        pass
    
    async def grade(self, prompt: str, sport: SportType, system_prompt: Optional[str] = None) -> ModelPrediction:
        """Grade a pick using the model."""
        start_time = time.time()
        
        @self.circuit_breaker
        async def _call_with_circuit():
            return await self._call_api(prompt, system_prompt)
        
        try:
            response = await _call_with_circuit()
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Parse response
            parsed = self._parse_response(response.get("content", ""))
            
            return ModelPrediction(
                model=self.provider,
                score=parsed.get("score", 50.0),
                grade=self._score_to_grade(parsed.get("score", 50.0)),
                confidence=parsed.get("confidence", 0.5),
                reasoning=parsed.get("reasoning", ""),
                latency_ms=latency_ms,
                tokens_used=response.get("tokens_used"),
                cost_usd=response.get("cost_usd"),
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Error calling {self.provider}: {e}")
            return ModelPrediction(
                model=self.provider,
                score=0.0,
                grade=GradeLevel.PASS,
                confidence=0.0,
                error=str(e),
                latency_ms=latency_ms,
            )
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse model response into structured data."""
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content
            
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback: try to extract score from text
            logger.warning(f"Failed to parse JSON response from {self.provider}")
            return self._extract_from_text(content)
    
    def _extract_from_text(self, content: str) -> Dict[str, Any]:
        """Extract score and grade from text response."""
        import re
        
        score_match = re.search(r'score["\']?\s*[:=]\s*(\d+\.?\d*)', content, re.IGNORECASE)
        confidence_match = re.search(r'confidence["\']?\s*[:=]\s*(\d+\.?\d*)', content, re.IGNORECASE)
        
        return {
            "score": float(score_match.group(1)) if score_match else 50.0,
            "confidence": float(confidence_match.group(1)) if confidence_match else 0.5,
            "reasoning": content[:500],
        }
    
    def _score_to_grade(self, score: float) -> GradeLevel:
        """Convert numeric score to grade."""
        if score >= 95:
            return GradeLevel.A_PLUS
        elif score >= 90:
            return GradeLevel.A
        elif score >= 85:
            return GradeLevel.A_MINUS
        elif score >= 80:
            return GradeLevel.B_PLUS
        elif score >= 75:
            return GradeLevel.B
        elif score >= 70:
            return GradeLevel.B_MINUS
        elif score >= 65:
            return GradeLevel.C_PLUS
        elif score >= 60:
            return GradeLevel.C
        elif score >= 55:
            return GradeLevel.C_MINUS
        elif score >= 50:
            return GradeLevel.D_PLUS
        elif score >= 45:
            return GradeLevel.D
        else:
            return GradeLevel.F
    
    @property
    def is_healthy(self) -> bool:
        """Check if the model client is healthy."""
        cb_state = self.circuit_breaker._states.get(self.provider.value)
        if cb_state:
            return cb_state.state != "open"
        return True


class GrokClient(BaseModelClient):
    """xAI Grok client."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(ModelProvider.GROK, api_key)
    
    def _init_client(self) -> None:
        """Initialize xAI client."""
        if self.api_key:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.x.ai/v1"
            )
    
    async def _call_api(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Call Grok API."""
        if not self.client:
            raise ValueError("Grok client not initialized - missing API key")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.chat.completions.create(
            model="grok-2",
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
        
        # Approximate cost (check xAI pricing)
        cost_usd = (tokens_used / 1000) * 0.002
        
        return {
            "content": content,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        }


class DeepSeekClient(BaseModelClient):
    """DeepSeek client."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(ModelProvider.DEEPSEEK, api_key)
    
    def _init_client(self) -> None:
        """Initialize DeepSeek client."""
        if self.api_key:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1"
            )
    
    async def _call_api(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Call DeepSeek API."""
        if not self.client:
            raise ValueError("DeepSeek client not initialized - missing API key")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
        cost_usd = (tokens_used / 1000) * 0.0005
        
        return {
            "content": content,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        }


class KimiClient(BaseModelClient):
    """Moonshot Kimi client."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(ModelProvider.KIMI, api_key)
    
    def _init_client(self) -> None:
        """Initialize Kimi client."""
        if self.api_key:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.moonshot.cn/v1"
            )
    
    async def _call_api(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Call Kimi API."""
        if not self.client:
            raise ValueError("Kimi client not initialized - missing API key")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.chat.completions.create(
            model="kimi-k1.5",
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
        cost_usd = (tokens_used / 1000) * 0.001
        
        return {
            "content": content,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        }


class ClaudeClient(BaseModelClient):
    """Anthropic Claude client."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(ModelProvider.CLAUDE, api_key)
    
    def _init_client(self) -> None:
        """Initialize Anthropic client."""
        if self.api_key:
            self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
    
    async def _call_api(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Call Claude API."""
        if not self.client:
            raise ValueError("Claude client not initialized - missing API key")
        
        sys_prompt = system_prompt or "You are a sports betting analysis expert."
        
        response = await self.client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=2000,
            temperature=0.3,
            system=sys_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        
        content = response.content[0].text if response.content else ""
        tokens_used = response.usage.input_tokens + response.usage.output_tokens if response.usage else 0
        
        # Claude 3.7 Sonnet pricing
        cost_usd = (response.usage.input_tokens / 1_000_000 * 3.0 + 
                   response.usage.output_tokens / 1_000_000 * 15.0) if response.usage else 0
        
        return {
            "content": content,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        }


class GPT5Client(BaseModelClient):
    """OpenAI GPT-5 client."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(ModelProvider.GPT5, api_key)
    
    def _init_client(self) -> None:
        """Initialize OpenAI client."""
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
    
    async def _call_api(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Call GPT-5 API."""
        if not self.client:
            raise ValueError("GPT-5 client not initialized - missing API key")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.chat.completions.create(
            model="gpt-5",
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else 0
        cost_usd = (tokens_used / 1000) * 0.005
        
        return {
            "content": content,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        }


# Client factory
_CLIENTS: Dict[ModelProvider, BaseModelClient] = {}


def get_client_for_provider(provider: ModelProvider) -> BaseModelClient:
    """Get or create a client for the specified provider."""
    if provider not in _CLIENTS:
        client_map = {
            ModelProvider.GROK: GrokClient,
            ModelProvider.DEEPSEEK: DeepSeekClient,
            ModelProvider.KIMI: KimiClient,
            ModelProvider.CLAUDE: ClaudeClient,
            ModelProvider.GPT5: GPT5Client,
        }
        
        client_class = client_map.get(provider)
        if not client_class:
            raise ValueError(f"Unknown provider: {provider}")
        
        _CLIENTS[provider] = client_class()
    
    return _CLIENTS[provider]


def get_all_clients() -> Dict[ModelProvider, BaseModelClient]:
    """Get all initialized clients."""
    for provider in ModelProvider:
        if provider not in _CLIENTS:
            try:
                get_client_for_provider(provider)
            except Exception as e:
                logger.warning(f"Failed to initialize {provider}: {e}")
    
    return _CLIENTS


def reset_client(provider: ModelProvider) -> None:
    """Reset a client (useful for testing or reconnection)."""
    if provider in _CLIENTS:
        del _CLIENTS[provider]
