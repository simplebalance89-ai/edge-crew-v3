"""
Smart model routing with fallback chains.
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timedelta

from models import ModelProvider, SportType, ModelHealth
from models.clients import BaseModelClient, get_client_for_provider, get_all_clients, CircuitBreaker

logger = logging.getLogger(__name__)


@dataclass
class ModelScore:
    """Score for a model's suitability."""
    provider: ModelProvider
    score: float
    latency_ms: int
    accuracy: float
    cost_usd: float
    is_healthy: bool


class ModelRouter:
    """Routes requests to appropriate models."""
    
    # Default model priorities by sport
    SPORT_PRIORITIES = {
        SportType.NFL: [
            ModelProvider.CLAUDE,
            ModelProvider.GPT5,
            ModelProvider.GROK,
            ModelProvider.DEEPSEEK,
            ModelProvider.KIMI,
        ],
        SportType.NBA: [
            ModelProvider.GPT5,
            ModelProvider.CLAUDE,
            ModelProvider.GROK,
            ModelProvider.KIMI,
            ModelProvider.DEEPSEEK,
        ],
        SportType.NCAAB: [
            ModelProvider.DEEPSEEK,
            ModelProvider.KIMI,
            ModelProvider.CLAUDE,
            ModelProvider.GPT5,
            ModelProvider.GROK,
        ],
        SportType.NCAAF: [
            ModelProvider.CLAUDE,
            ModelProvider.GPT5,
            ModelProvider.GROK,
            ModelProvider.DEEPSEEK,
            ModelProvider.KIMI,
        ],
        SportType.MLB: [
            ModelProvider.GPT5,
            ModelProvider.GROK,
            ModelProvider.CLAUDE,
            ModelProvider.KIMI,
            ModelProvider.DEEPSEEK,
        ],
        SportType.NHL: [
            ModelProvider.DEEPSEEK,
            ModelProvider.GPT5,
            ModelProvider.CLAUDE,
            ModelProvider.GROK,
            ModelProvider.KIMI,
        ],
        SportType.SOCCER: [
            ModelProvider.KIMI,
            ModelProvider.DEEPSEEK,
            ModelProvider.GPT5,
            ModelProvider.CLAUDE,
            ModelProvider.GROK,
        ],
        SportType.UFC: [
            ModelProvider.CLAUDE,
            ModelProvider.GROK,
            ModelProvider.GPT5,
            ModelProvider.DEEPSEEK,
            ModelProvider.KIMI,
        ],
    }
    
    def __init__(self):
        self.clients = get_all_clients()
        self.model_stats: Dict[ModelProvider, Dict[str, Any]] = {
            provider: {
                "calls": 0,
                "errors": 0,
                "total_latency_ms": 0,
                "last_used": None,
            }
            for provider in ModelProvider
        }
        self.health_check_interval = 30  # seconds
        self._last_health_check: Optional[datetime] = None
    
    async def get_models_for_request(
        self,
        sport: SportType,
        required_count: int = 3,
        exclude: Optional[Set[ModelProvider]] = None,
    ) -> List[ModelProvider]:
        """
        Get the best models for a request based on sport and health.
        
        Args:
            sport: The sport being analyzed
            required_count: Number of models needed
            exclude: Models to exclude
            
        Returns:
            List of model providers ordered by priority
        """
        exclude = exclude or set()
        priorities = self.SPORT_PRIORITIES.get(sport, list(ModelProvider))
        
        # Score and filter models
        scored_models: List[ModelScore] = []
        
        for provider in priorities:
            if provider in exclude:
                continue
            
            client = self.clients.get(provider)
            if not client:
                continue
            
            stats = self.model_stats[provider]
            
            # Calculate error rate
            error_rate = stats["errors"] / max(stats["calls"], 1)
            avg_latency = stats["total_latency_ms"] / max(stats["calls"], 1)
            
            # Check circuit breaker state
            cb_state = client.circuit_breaker._states.get(provider.value)
            is_healthy = cb_state.state != "open" if cb_state else True
            
            # Calculate composite score
            # Higher is better for accuracy and health, lower is better for latency and errors
            health_penalty = 0.5 if not is_healthy else 1.0
            accuracy_score = (1 - error_rate) * 0.7 + health_penalty * 0.3
            
            scored_models.append(ModelScore(
                provider=provider,
                score=accuracy_score,
                latency_ms=avg_latency,
                accuracy=accuracy_score,
                cost_usd=0.0,  # Would track actual costs
                is_healthy=is_healthy,
            ))
        
        # Sort by score (descending) and health
        scored_models.sort(key=lambda x: (x.is_healthy, x.score), reverse=True)
        
        # Return top N healthy models, or fall back to any available
        healthy_models = [m for m in scored_models if m.is_healthy]
        
        if len(healthy_models) >= required_count:
            return [m.provider for m in healthy_models[:required_count]]
        
        # Not enough healthy models, include degraded ones
        all_available = [m.provider for m in scored_models]
        
        if len(all_available) >= required_count:
            logger.warning(f"Using degraded models for {sport}: insufficient healthy models")
            return all_available[:required_count]
        
        # Critical: not enough models available
        logger.error(f"CRITICAL: Only {len(all_available)} models available, need {required_count}")
        return all_available
    
    async def get_fallback_chain(
        self,
        sport: SportType,
        primary_model: ModelProvider,
    ) -> List[ModelProvider]:
        """Get a fallback chain for a primary model."""
        priorities = self.SPORT_PRIORITIES.get(sport, list(ModelProvider))
        
        # Move primary to front, keep rest of order
        chain = [primary_model]
        for p in priorities:
            if p != primary_model:
                chain.append(p)
        
        return chain
    
    async def execute_with_fallback(
        self,
        sport: SportType,
        primary_model: ModelProvider,
        call_func,
        max_attempts: int = 3,
    ) -> Tuple[Any, ModelProvider]:
        """
        Execute a call with automatic fallback.
        
        Args:
            sport: The sport being analyzed
            primary_model: Preferred model to use
            call_func: Async function that takes a client and returns result
            max_attempts: Maximum number of models to try
            
        Returns:
            Tuple of (result, successful_model)
        """
        chain = await self.get_fallback_chain(sport, primary_model)
        
        for i, provider in enumerate(chain[:max_attempts]):
            client = self.clients.get(provider)
            if not client:
                continue
            
            try:
                result = await call_func(client)
                self._update_stats(provider, success=True, latency_ms=0)
                return result, provider
            except Exception as e:
                self._update_stats(provider, success=False, latency_ms=0)
                logger.warning(f"Model {provider} failed (attempt {i+1}): {e}")
                continue
        
        raise Exception(f"All models in fallback chain failed for {sport}")
    
    def _update_stats(self, provider: ModelProvider, success: bool, latency_ms: int):
        """Update model statistics."""
        stats = self.model_stats[provider]
        stats["calls"] += 1
        if not success:
            stats["errors"] += 1
        stats["total_latency_ms"] += latency_ms
        stats["last_used"] = datetime.utcnow()
    
    async def health_check(self) -> List[ModelHealth]:
        """Run health checks on all models."""
        health_statuses = []
        
        for provider in ModelProvider:
            client = self.clients.get(provider)
            stats = self.model_stats[provider]
            cb_state = client.circuit_breaker._states.get(provider.value) if client else None
            
            error_rate = stats["errors"] / max(stats["calls"], 1)
            avg_latency = stats["total_latency_ms"] / max(stats["calls"], 1) if stats["calls"] > 0 else 0
            
            if cb_state and cb_state.state == "open":
                status = "down"
            elif error_rate > 0.2:
                status = "degraded"
            else:
                status = "healthy"
            
            health_statuses.append(ModelHealth(
                provider=provider,
                status=status,
                avg_latency_ms=int(avg_latency),
                error_rate=error_rate,
                last_success=stats["last_used"] if stats["calls"] > 0 else None,
                consecutive_failures=cb_state.failures if cb_state else 0,
                circuit_state=cb_state.state if cb_state else "closed",
            ))
        
        self._last_health_check = datetime.utcnow()
        return health_statuses


class SmartRouter(ModelRouter):
    """Enhanced router with predictive load balancing."""
    
    def __init__(self):
        super().__init__()
        self.cost_budget_usd = float(os.getenv("AI_COST_BUDGET_USD", "100.0"))
        self.current_spend_usd = 0.0
        self.latency_target_ms = int(os.getenv("AI_LATENCY_TARGET_MS", "5000"))
    
    async def get_models_for_request(
        self,
        sport: SportType,
        required_count: int = 3,
        exclude: Optional[Set[ModelProvider]] = None,
        optimization: str = "balanced",  # "speed", "accuracy", "cost", "balanced"
    ) -> List[ModelProvider]:
        """
        Get models optimized for specific goals.
        
        Args:
            sport: The sport being analyzed
            required_count: Number of models needed
            exclude: Models to exclude
            optimization: Optimization target
        """
        base_models = await super().get_models_for_request(sport, required_count * 2, exclude)
        
        if optimization == "speed":
            # Sort by latency
            return base_models[:required_count]
        
        elif optimization == "cost":
            # Prefer cheaper models (DeepSeek, Kimi)
            cost_order = [
                ModelProvider.DEEPSEEK,
                ModelProvider.KIMI,
                ModelProvider.GROK,
                ModelProvider.GPT5,
                ModelProvider.CLAUDE,
            ]
            sorted_models = sorted(
                base_models,
                key=lambda m: cost_order.index(m) if m in cost_order else 999
            )
            return sorted_models[:required_count]
        
        elif optimization == "accuracy":
            # Use sport priorities directly (already sorted by accuracy)
            return base_models[:required_count]
        
        else:  # balanced
            return base_models[:required_count]
    
    def should_use_cheap_models(self, urgency: str = "normal") -> bool:
        """Determine if we should use cheaper models based on budget."""
        if urgency == "critical":
            return False
        
        spend_ratio = self.current_spend_usd / self.cost_budget_usd
        
        if spend_ratio > 0.9:
            return True
        if spend_ratio > 0.7 and urgency == "normal":
            return True
        
        return False
    
    def update_spend(self, cost_usd: float):
        """Update current spend tracking."""
        self.current_spend_usd += cost_usd
        logger.info(f"AI spend updated: ${self.current_spend_usd:.4f} / ${self.cost_budget_usd:.2f}")


# Global router instance
_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    """Get the global router instance."""
    global _router
    if _router is None:
        _router = SmartRouter()
    return _router


def reset_router():
    """Reset the global router."""
    global _router
    _router = None


import os
