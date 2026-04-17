"""
Edge Crew v3.0 - Rate Limiting Middleware
Redis-based rate limiting with per-user and per-IP support
"""

import logging
import time
from typing import Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
import redis

from app.core.config import security_settings
from app.middleware.headers import get_client_ip

logger = logging.getLogger("edge-crew-v3.rate_limit")

# Redis client for rate limiting
_redis_client: Optional[redis.Redis] = None


def _get_redis_client() -> Optional[redis.Redis]:
    """Get or create Redis client for rate limiting"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    
    try:
        _redis_client = redis.Redis.from_url(
            security_settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        _redis_client.ping()
        logger.info("Redis rate limit client connected")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis rate limit client unavailable: {e}")
        return None


class RateLimiter:
    """Redis-based sliding window rate limiter"""
    
    def __init__(self, requests: int = 100, window: int = 60):
        self.requests = requests
        self.window = window
        self.redis_client = _get_redis_client()
    
    def _get_key(self, identifier: str, endpoint: str = "global") -> str:
        """Generate rate limit key"""
        return f"rate_limit:{endpoint}:{identifier}"
    
    def is_allowed(self, identifier: str, endpoint: str = "global") -> tuple[bool, dict]:
        """
        Check if a request is allowed under the rate limit.
        Returns (allowed, rate_limit_info).
        """
        if self.redis_client is None:
            # If Redis is unavailable, allow the request
            logger.warning("Redis unavailable - rate limiting disabled")
            return True, {
                "limit": self.requests,
                "remaining": self.requests,
                "reset": int(time.time()) + self.window,
            }
        
        key = self._get_key(identifier, endpoint)
        now = time.time()
        window_start = now - self.window
        
        try:
            # Remove old requests outside the window
            self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Count requests in current window
            current_count = self.redis_client.zcard(key)
            
            if current_count >= self.requests:
                # Get the oldest request in the window to calculate reset time
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                reset_time = int(oldest[0][1]) + self.window if oldest else int(now) + self.window
                
                return False, {
                    "limit": self.requests,
                    "remaining": 0,
                    "reset": reset_time,
                }
            
            # Add current request
            self.redis_client.zadd(key, {str(now): now})
            # Set expiry on the key
            self.redis_client.expire(key, self.window)
            
            return True, {
                "limit": self.requests,
                "remaining": max(0, self.requests - current_count - 1),
                "reset": int(now) + self.window,
            }
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True, {
                "limit": self.requests,
                "remaining": self.requests,
                "reset": int(now) + self.window,
            }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that applies rate limiting to all requests.
    Differentiates between authenticated users and anonymous IPs.
    """
    
    def __init__(self, app, requests: int = 100, window: int = 60):
        super().__init__(app)
        self.rate_limiter = RateLimiter(requests=requests, window=window)
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/healthz"]:
            return await call_next(request)
        
        # Determine identifier: authenticated user or IP address
        identifier = self._get_identifier(request)
        endpoint = request.url.path
        
        allowed, rate_info = self.rate_limiter.is_allowed(identifier, endpoint)
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])
        
        if not allowed:
            retry_after = max(1, rate_info["reset"] - int(time.time()))
            response.headers["Retry-After"] = str(retry_after)
            logger.warning(f"Rate limit exceeded for {identifier} on {endpoint}")
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        
        return response
    
    def _get_identifier(self, request: Request) -> str:
        """Get rate limit identifier from request"""
        # Check for authenticated user
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP address (with X-Forwarded-For support)
        client_ip = get_client_ip(request)
        return f"ip:{client_ip}"


def get_rate_limiter(requests: Optional[int] = None, window: Optional[int] = None) -> RateLimiter:
    """Factory for creating rate limiters with custom settings"""
    return RateLimiter(
        requests=requests or security_settings.rate_limit_requests,
        window=window or security_settings.rate_limit_window,
    )


async def check_rate_limit(request: Request, requests: int = 100, window: int = 60):
    """
    Dependency for endpoint-specific rate limiting.
    Usage: dependencies=[Depends(check_rate_limit)]
    """
    limiter = RateLimiter(requests=requests, window=window)
    
    # Determine identifier
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        identifier = f"user:{user_id}"
    else:
        identifier = f"ip:{get_client_ip(request)}"
    
    endpoint = request.url.path
    allowed, rate_info = limiter.is_allowed(identifier, endpoint)
    
    if not allowed:
        retry_after = max(1, rate_info["reset"] - int(time.time()))
        logger.warning(f"Rate limit exceeded for {identifier} on {endpoint}")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(rate_info["limit"]),
                "X-RateLimit-Remaining": str(rate_info["remaining"]),
                "X-RateLimit-Reset": str(rate_info["reset"]),
            },
        )
    
    return rate_info