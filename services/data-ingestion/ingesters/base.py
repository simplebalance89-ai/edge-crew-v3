"""
Base ingester class with circuit breaker pattern and rate limiting.
"""
import asyncio
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
import structlog
from circuitbreaker import circuit, CircuitBreaker
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from models import (
    BaseEvent,
    DataSource,
    Priority,
    Sport,
    IngestionStatus,
)

logger = structlog.get_logger()


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, rate: int, period: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            rate: Maximum number of requests per period
            period: Time period in seconds
        """
        self.rate = rate
        self.period = period
        self._tokens = rate
        self._last_update = datetime.utcnow()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = datetime.utcnow()
            elapsed = (now - self._last_update).total_seconds()
            
            # Replenish tokens
            self._tokens = min(
                self.rate,
                self._tokens + (elapsed * self.rate / self.period)
            )
            self._last_update = now
            
            if self._tokens < 1:
                # Calculate wait time
                wait_time = (1 - self._tokens) * self.period / self.rate
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1


class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    
    FAILURE_THRESHOLD = 5
    RECOVERY_TIMEOUT = 60
    EXPECTED_EXCEPTION = Exception


class BaseIngester(ABC):
    """Base class for all data ingesters."""
    
    source: DataSource
    base_url: str
    rate_limit: int = 60  # requests per minute
    rate_limit_period: int = 60
    timeout: int = 30
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None
        self._rate_limiter = RateLimiter(self.rate_limit, self.rate_limit_period)
        self._status = IngestionStatus(source=self.source)
        self._dedup_cache: dict[str, datetime] = {}
        self._dedup_window = 300  # 5 minutes
        self._circuit_breaker: Optional[CircuitBreaker] = None
        self._lock = asyncio.Lock()
        
        # Set up circuit breaker
        self._setup_circuit_breaker()
    
    def _setup_circuit_breaker(self):
        """Configure circuit breaker for this ingester."""
        @circuit(
            failure_threshold=CircuitBreakerConfig.FAILURE_THRESHOLD,
            recovery_timeout=CircuitBreakerConfig.RECOVERY_TIMEOUT,
            expected_exception=CircuitBreakerConfig.EXPECTED_EXCEPTION
        )
        async def _protected_request(*args, **kwargs):
            return await self._client.request(*args, **kwargs)
        
        self._protected_request = _protected_request
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
    
    async def start(self):
        """Initialize the HTTP client."""
        if self._client is None:
            limits = httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=30.0
            )
            timeout = httpx.Timeout(
                connect=5.0,
                read=self.timeout,
                write=5.0,
                pool=5.0
            )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                limits=limits,
                timeout=timeout,
                http2=True,
                headers=self._get_default_headers()
            )
            logger.info(f"{self.source.value}.client_started")
    
    async def stop(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info(f"{self.source.value}.client_stopped")
    
    def _get_default_headers(self) -> dict[str, str]:
        """Get default HTTP headers."""
        return {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "EdgeCrew-DataIngestion/3.0.0",
        }
    
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def _request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make an HTTP request with rate limiting and circuit breaker.
        """
        if not self._client:
            raise RuntimeError("Ingester not started")
        
        # Apply rate limiting
        await self._rate_limiter.acquire()
        
        start_time = datetime.utcnow()
        
        try:
            # Use circuit breaker protected request
            response = await self._protected_request(
                method,
                path,
                **kwargs
            )
            response.raise_for_status()
            
            # Update success metrics
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self._update_status(success=True, latency_ms=latency)
            
            return response
            
        except Exception as e:
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self._update_status(success=False, latency_ms=latency)
            logger.error(
                f"{self.source.value}.request_failed",
                path=path,
                error=str(e),
                latency_ms=latency
            )
            raise
    
    async def _update_status(self, success: bool, latency_ms: float):
        """Update ingestion status metrics."""
        async with self._lock:
            now = datetime.utcnow()
            
            # Update rolling average latency
            total = self._status.success_count + self._status.failure_count
            if total > 0:
                self._status.average_latency_ms = (
                    (self._status.average_latency_ms * total + latency_ms) / (total + 1)
                )
            else:
                self._status.average_latency_ms = latency_ms
            
            if success:
                self._status.last_success = now
                self._status.success_count += 1
            else:
                self._status.last_failure = now
                self._status.failure_count += 1
            
            # Update circuit state
            if self._protected_request:
                cb = CircuitBreaker.get(self._protected_request)
                self._status.circuit_state = cb.current_state
                self._status.is_healthy = cb.current_state == "closed"
    
    def _is_duplicate(self, event: BaseEvent) -> bool:
        """Check if event is a duplicate based on dedup_key."""
        now = datetime.utcnow()
        
        # Clean old entries
        self._clean_dedup_cache(now)
        
        # Check if we've seen this event recently
        if event.dedup_key in self._dedup_cache:
            return True
        
        # Add to cache
        self._dedup_cache[event.dedup_key] = now
        return False
    
    def _clean_dedup_cache(self, now: datetime):
        """Remove expired entries from dedup cache."""
        cutoff = now - timedelta(seconds=self._dedup_window)
        stale_keys = [
            k for k, v in self._dedup_cache.items()
            if v < cutoff
        ]
        for k in stale_keys:
            del self._dedup_cache[k]
    
    def _generate_dedup_key(self, *parts: str) -> str:
        """Generate a deduplication key from parts."""
        content = "|".join(parts)
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    @abstractmethod
    async def fetch(
        self,
        sport: Sport,
        priority: Priority = Priority.MEDIUM
    ) -> list[BaseEvent]:
        """
        Fetch data for a sport.
        
        Args:
            sport: The sport to fetch data for
            priority: The priority level of this fetch
            
        Returns:
            List of events
        """
        pass
    
    async def fetch_all(
        self,
        sports: Optional[list[Sport]] = None,
        priority: Priority = Priority.MEDIUM
    ) -> list[BaseEvent]:
        """
        Fetch data for multiple sports concurrently.
        
        Args:
            sports: List of sports to fetch (defaults to all)
            priority: Priority level
            
        Returns:
            Combined list of events
        """
        if sports is None:
            sports = list(Sport)
        
        tasks = [self.fetch(sport, priority) for sport in sports]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        events = []
        for sport, result in zip(sports, results):
            if isinstance(result, Exception):
                logger.error(
                    f"{self.source.value}.fetch_failed",
                    sport=sport.value,
                    error=str(result)
                )
            else:
                events.extend(result)
        
        return events
    
    def get_status(self) -> IngestionStatus:
        """Get current ingestion status."""
        return self._status
    
    @abstractmethod
    def map_sport(self, sport: Sport) -> str:
        """Map internal sport to provider-specific sport code."""
        pass
