"""
Custom Rate Limiting Plugin for Edge Crew v3.0 API Gateway

This plugin provides advanced rate limiting capabilities:
- Per-user rate limiting based on JWT claims
- Per-endpoint rate limiting with different tiers
- Sliding window rate limiting
- Redis-backed distributed rate limiting
- Burst allowance for premium users
"""

import json
import time
import hashlib
import redis
from typing import Dict, Optional, Tuple
from kong_pdk.pdk import kong

# Plugin metadata
VERSION = "1.0.0"
PRIORITY = 900

class Config:
    """Plugin configuration schema"""
    def __init__(self):
        # Default rate limits
        self.minute = 60
        self.hour = 1000
        self.day = 10000
        
        # Redis configuration
        self.redis_host = "redis"
        self.redis_port = 6379
        self.redis_password = None
        self.redis_database = 0
        self.redis_timeout = 2000
        self.redis_ssl = False
        
        # Rate limit by
        self.limit_by = "consumer"  # consumer, credential, ip, header, path
        self.header_name = None
        self.path = None
        
        # Burst configuration
        self.burst_multiplier = 1.5  # Allow 1.5x burst
        self.burst_window = 10  # seconds
        
        # Premium tiers
        self.premium_tiers = {
            "free": {"minute": 30, "hour": 500, "day": 5000},
            "basic": {"minute": 60, "hour": 1000, "day": 10000},
            "premium": {"minute": 120, "hour": 2000, "day": 20000},
            "enterprise": {"minute": 500, "hour": 10000, "day": 100000}
        }
        
        # Error handling
        self.fault_tolerant = True
        self.hide_client_headers = False
        self.retry_after = True
        self.error_code = 429
        self.error_message = "API rate limit exceeded"

class RateLimiter:
    """Core rate limiting logic with Redis backend"""
    
    def __init__(self, config: Config):
        self.config = config
        self.redis_client = None
        self._connect_redis()
    
    def _connect_redis(self):
        """Establish Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                password=self.config.redis_password,
                db=self.config.redis_database,
                socket_connect_timeout=self.config.redis_timeout / 1000,
                ssl=self.config.redis_ssl,
                decode_responses=True
            )
            self.redis_client.ping()
        except Exception as e:
            kong.log.err(f"Redis connection failed: {e}")
            self.redis_client = None
    
    def _get_identifier(self, kong) -> str:
        """Extract rate limit identifier from request"""
        if self.config.limit_by == "consumer":
            consumer = kong.client.get_consumer()
            if consumer:
                return f"consumer:{consumer.get('id', 'anonymous')}"
            credential = kong.client.get_credential()
            if credential:
                return f"credential:{credential.get('id', 'anonymous')}"
            return f"ip:{kong.client.get_ip()}"
        
        elif self.config.limit_by == "credential":
            credential = kong.client.get_credential()
            if credential:
                return f"credential:{credential.get('id', 'anonymous')}"
            return f"ip:{kong.client.get_ip()}"
        
        elif self.config.limit_by == "ip":
            return f"ip:{kong.client.get_ip()}"
        
        elif self.config.limit_by == "header" and self.config.header_name:
            header_value = kong.request.get_header(self.config.header_name)
            if header_value:
                return f"header:{self.config.header_name}:{header_value}"
            return f"ip:{kong.client.get_ip()}"
        
        elif self.config.limit_by == "path":
            path = kong.request.get_path()
            return f"path:{path}"
        
        return f"ip:{kong.client.get_ip()}"
    
    def _get_tier_limits(self, kong) -> Dict[str, int]:
        """Get rate limits based on user tier from JWT claims"""
        try:
            # Try to get tier from JWT claims
            jwt_claims = kong.request.get_headers().get("X-JWT-Claims")
            if jwt_claims:
                claims = json.loads(jwt_claims)
                tier = claims.get("tier", "basic")
                if tier in self.config.premium_tiers:
                    return self.config.premium_tiers[tier]
        except Exception:
            pass
        
        # Default limits
        return {
            "minute": self.config.minute,
            "hour": self.config.hour,
            "day": self.config.day
        }
    
    def _get_current_window_counts(self, identifier: str) -> Tuple[int, int, int]:
        """Get current request counts for all time windows"""
        if not self.redis_client:
            return 0, 0, 0
        
        now = int(time.time())
        minute_key = f"ratelimit:{identifier}:minute:{now // 60}"
        hour_key = f"ratelimit:{identifier}:hour:{now // 3600}"
        day_key = f"ratelimit:{identifier}:day:{now // 86400}"
        
        pipe = self.redis_client.pipeline()
        pipe.get(minute_key)
        pipe.get(hour_key)
        pipe.get(day_key)
        results = pipe.execute()
        
        return (
            int(results[0]) if results[0] else 0,
            int(results[1]) if results[1] else 0,
            int(results[2]) if results[2] else 0
        )
    
    def _increment_counters(self, identifier: str) -> bool:
        """Increment rate limit counters in Redis"""
        if not self.redis_client:
            return True
        
        now = int(time.time())
        minute_key = f"ratelimit:{identifier}:minute:{now // 60}"
        hour_key = f"ratelimit:{identifier}:hour:{now // 3600}"
        day_key = f"ratelimit:{identifier}:day:{now // 86400}"
        
        pipe = self.redis_client.pipeline()
        
        # Increment counters
        pipe.incr(minute_key)
        pipe.incr(hour_key)
        pipe.incr(day_key)
        
        # Set expiration
        pipe.expire(minute_key, 120)  # 2 minutes
        pipe.expire(hour_key, 7200)   # 2 hours
        pipe.expire(day_key, 172800)  # 2 days
        
        try:
            pipe.execute()
            return True
        except Exception as e:
            kong.log.err(f"Redis increment failed: {e}")
            return self.config.fault_tolerant
    
    def check_rate_limit(self, kong) -> Tuple[bool, Dict]:
        """
        Check if request is within rate limits
        Returns: (allowed, headers_dict)
        """
        identifier = self._get_identifier(kong)
        limits = self._get_tier_limits(kong)
        
        # Get current counts
        minute_count, hour_count, day_count = self._get_current_window_counts(identifier)
        
        # Calculate remaining
        minute_remaining = max(0, limits["minute"] - minute_count - 1)
        hour_remaining = max(0, limits["hour"] - hour_count - 1)
        day_remaining = max(0, limits["day"] - day_count - 1)
        
        # Determine if allowed (check all windows)
        allowed = (
            minute_count < limits["minute"] * self.config.burst_multiplier and
            hour_count < limits["hour"] and
            day_count < limits["day"]
        )
        
        # Calculate reset times
        now = int(time.time())
        minute_reset = ((now // 60) + 1) * 60
        hour_reset = ((now // 3600) + 1) * 3600
        day_reset = ((now // 86400) + 1) * 86400
        
        headers = {
            "X-RateLimit-Limit-Minute": str(limits["minute"]),
            "X-RateLimit-Remaining-Minute": str(minute_remaining),
            "X-RateLimit-Limit-Hour": str(limits["hour"]),
            "X-RateLimit-Remaining-Hour": str(hour_remaining),
            "X-RateLimit-Limit-Day": str(limits["day"]),
            "X-RateLimit-Remaining-Day": str(day_remaining),
            "X-RateLimit-Reset": str(minute_reset)
        }
        
        if allowed:
            # Increment counters
            if not self._increment_counters(identifier):
                allowed = False
        
        return allowed, headers
    
    def get_retry_after(self) -> int:
        """Calculate retry-after header value"""
        now = int(time.time())
        return ((now // 60) + 1) * 60 - now


class Plugin:
    """Kong Plugin Implementation"""
    
    def __init__(self, config: Dict):
        self.config = Config()
        # Update config from provided values
        for key, value in config.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self.limiter = RateLimiter(self.config)
    
    def access(self, kong):
        """Main access phase handler"""
        try:
            allowed, headers = self.limiter.check_rate_limit(kong)
            
            # Add rate limit headers unless hidden
            if not self.config.hide_client_headers:
                for header, value in headers.items():
                    kong.response.set_header(header, value)
            
            if not allowed:
                # Rate limit exceeded
                retry_after = self.limiter.get_retry_after()
                
                if self.config.retry_after:
                    kong.response.set_header("Retry-After", str(retry_after))
                
                return kong.response.exit(
                    self.config.error_code,
                    json.dumps({
                        "error": self.config.error_message,
                        "retry_after": retry_after,
                        "documentation_url": "https://docs.edgecrew.io/rate-limits"
                    }),
                    {"Content-Type": "application/json"}
                )
            
        except Exception as e:
            kong.log.err(f"Rate limiting error: {e}")
            if not self.config.fault_tolerant:
                return kong.response.exit(
                    500,
                    json.dumps({"error": "Internal rate limiting error"}),
                    {"Content-Type": "application/json"}
                )


# Kong PDK entry point
def access(kong):
    """Entry point for Kong access phase"""
    config = kong.configuration
    plugin = Plugin(config)
    return plugin.access(kong)


# Schema for Kong plugin configuration
Schema = {
    "name": "edge-rate-limiting",
    "fields": [
        {"minute": {"type": "number", "default": 60}},
        {"hour": {"type": "number", "default": 1000}},
        {"day": {"type": "number", "default": 10000}},
        {"redis_host": {"type": "string", "default": "redis"}},
        {"redis_port": {"type": "number", "default": 6379}},
        {"redis_password": {"type": "string"}},
        {"redis_database": {"type": "number", "default": 0}},
        {"redis_timeout": {"type": "number", "default": 2000}},
        {"redis_ssl": {"type": "boolean", "default": False}},
        {"limit_by": {"type": "string", "default": "consumer", "one_of": ["consumer", "credential", "ip", "header", "path"]}},
        {"header_name": {"type": "string"}},
        {"path": {"type": "string"}},
        {"burst_multiplier": {"type": "number", "default": 1.5}},
        {"burst_window": {"type": "number", "default": 10}},
        {"fault_tolerant": {"type": "boolean", "default": True}},
        {"hide_client_headers": {"type": "boolean", "default": False}},
        {"retry_after": {"type": "boolean", "default": True}},
        {"error_code": {"type": "number", "default": 429}},
        {"error_message": {"type": "string", "default": "API rate limit exceeded"}}
    ]
}
