"""
Edge Crew v3.0 - Distributed Caching System
Redis-based caching with Render optimization and proper invalidation
"""

import json
import logging
import hashlib
import asyncio
from typing import Optional, Any, Dict, Callable
from datetime import datetime, timedelta
import redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError
import os

logger = logging.getLogger("edge-crew-v3.cache")

class CacheConfig:
    """Redis cache configuration with Render optimization"""
    
    def __init__(self):
        # Redis connection settings
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        self.redis_host = os.getenv("REDIS_HOST", "redis")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)
        self.redis_db = int(os.getenv("REDIS_DB", "0"))
        
        # Connection pool settings for Render
        self.connection_pool_kwargs = {
            'max_connections': int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
            'socket_connect_timeout': int(os.getenv("REDIS_CONNECT_TIMEOUT", "5")),
            'socket_timeout': int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
            'socket_keepalive': True,
            'socket_keepalive_options': {},
            'retry_on_timeout': True,
            'health_check_interval': 30
        }
        
        # Cache settings
        self.default_ttl = int(os.getenv("CACHE_DEFAULT_TTL", "3600"))  # 1 hour
        self.compression_threshold = int(os.getenv("CACHE_COMPRESSION_THRESHOLD", "1024"))  # 1KB
        self.enable_compression = os.getenv("CACHE_ENABLE_COMPRESSION", "true").lower() == "true"
        
    def validate_config(self) -> bool:
        """Validate cache configuration"""
        try:
            assert self.redis_port > 0, "Redis port must be positive"
            assert self.redis_db >= 0, "Redis DB must be non-negative"
            assert self.default_ttl > 0, "Default TTL must be positive"
            assert self.connection_pool_kwargs['max_connections'] > 0, "Max connections must be positive"
            return True
        except Exception as e:
            logger.error(f"Cache configuration validation failed: {e}")
            return False

class RedisCache:
    """Redis-based distributed cache with Render optimization"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.connection_pool = None
        self._connected = False
        self._connect_lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None
        
    def _create_connection_pool(self) -> redis.ConnectionPool:
        """Create Redis connection pool with Render optimization"""
        
        # Parse Redis URL if provided
        if self.config.redis_url and self.config.redis_url.startswith("redis://"):
            return redis.ConnectionPool.from_url(
                self.config.redis_url,
                **self.config.connection_pool_kwargs
            )
        
        # Manual connection configuration
        return redis.ConnectionPool(
            host=self.config.redis_host,
            port=self.config.redis_port,
            password=self.config.redis_password,
            db=self.config.redis_db,
            **self.config.connection_pool_kwargs
        )
    
    async def connect_async(self):
        """Connect to Redis asynchronously (for async contexts)"""
        if self._connected:
            return
            
        try:
            self.connection_pool = self._create_connection_pool()
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            await asyncio.get_event_loop().run_in_executor(None, self.redis_client.ping)
            
            self._connected = True
            logger.info("Redis cache connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise
    
    def connect(self):
        """Connect to Redis synchronously"""
        if self._connected:
            return
            
        try:
            self.connection_pool = self._create_connection_pool()
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            self.redis_client.ping()
            
            self._connected = True
            logger.info("Redis cache connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise
    
    def _generate_cache_key(self, key: str, prefix: str = "") -> str:
        """Generate cache key with optional prefix and hashing"""
        if prefix:
            key = f"{prefix}:{key}"
        
        # Hash long keys to prevent Redis key length issues
        if len(key) > 250:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            key = f"{key[:100]}:{key_hash}"
            
        return key
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize value for Redis storage"""
        try:
            if isinstance(value, (dict, list)):
                return json.dumps(value, default=str)
            elif isinstance(value, (datetime, timedelta)):
                return json.dumps({"__type__": type(value).__name__, "value": str(value)})
            else:
                return str(value)
        except Exception as e:
            logger.error(f"Failed to serialize cache value: {e}")
            raise
    
    def _deserialize_value(self, value: str) -> Any:
        """Deserialize value from Redis storage"""
        try:
            # Try JSON deserialization first
            parsed = json.loads(value)
            
            # Handle special types
            if isinstance(parsed, dict) and "__type__" in parsed:
                if parsed["__type__"] == "datetime":
                    return datetime.fromisoformat(parsed["value"])
                elif parsed["__type__"] == "timedelta":
                    # Parse timedelta string representation
                    parts = parsed["value"].split()
                    if len(parts) == 2:
                        return timedelta(**{parts[1]: float(parts[0])})
                
            return parsed
            
        except (json.JSONDecodeError, ValueError):
            # Return as string if JSON parsing fails
            return value
    
    async def get_async(self, key: str, prefix: str = "") -> Optional[Any]:
        """Get value from cache asynchronously"""
        if not self._connected:
            await self.connect_async()
            
        try:
            cache_key = self._generate_cache_key(key, prefix)
            value = await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.get, cache_key
            )
            
            if value is None:
                return None
                
            return self._deserialize_value(value.decode())
            
        except RedisError as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in cache get for key {key}: {e}")
            return None
    
    def get(self, key: str, prefix: str = "") -> Optional[Any]:
        """Get value from cache synchronously"""
        if not self._connected:
            self.connect()
            
        try:
            cache_key = self._generate_cache_key(key, prefix)
            value = self.redis_client.get(cache_key)
            
            if value is None:
                return None
                
            return self._deserialize_value(value.decode())
            
        except RedisError as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in cache get for key {key}: {e}")
            return None
    
    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None, prefix: str = "") -> bool:
        """Set value in cache asynchronously"""
        if not self._connected:
            await self.connect_async()
            
        try:
            cache_key = self._generate_cache_key(key, prefix)
            serialized_value = self._serialize_value(value)
            
            # Use default TTL if not specified
            if ttl is None:
                ttl = self.config.default_ttl
            
            success = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.redis_client.setex(cache_key, ttl, serialized_value)
            )
            
            logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
            return bool(success)
            
        except RedisError as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in cache set for key {key}: {e}")
            return False
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, prefix: str = "") -> bool:
        """Set value in cache synchronously"""
        if not self._connected:
            self.connect()
            
        try:
            cache_key = self._generate_cache_key(key, prefix)
            serialized_value = self._serialize_value(value)
            
            # Use default TTL if not specified
            if ttl is None:
                ttl = self.config.default_ttl
            
            success = self.redis_client.setex(cache_key, ttl, serialized_value)
            
            logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
            return bool(success)
            
        except RedisError as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in cache set for key {key}: {e}")
            return False
    
    async def delete_async(self, key: str, prefix: str = "") -> bool:
        """Delete value from cache asynchronously"""
        if not self._connected:
            await self.connect_async()
            
        try:
            cache_key = self._generate_cache_key(key, prefix)
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.redis_client.delete, cache_key
            )
            
            logger.debug(f"Cache DELETE: {cache_key}")
            return bool(result)
            
        except RedisError as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in cache delete for key {key}: {e}")
            return False
    
    def delete(self, key: str, prefix: str = "") -> bool:
        """Delete value from cache synchronously"""
        if not self._connected:
            self.connect()
            
        try:
            cache_key = self._generate_cache_key(key, prefix)
            result = self.redis_client.delete(cache_key)
            
            logger.debug(f"Cache DELETE: {cache_key}")
            return bool(result)
            
        except RedisError as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in cache delete for key {key}: {e}")
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics"""
        if not self._connected or not self.redis_client:
            return {"status": "disconnected"}
            
        try:
            # Get Redis info
            info = self.redis_client.info()
            
            return {
                "status": "connected",
                "used_memory": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_ratio": info.get("keyspace_hits", 0) / max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1)
            }
        except Exception as e:
            logger.error(f"Failed to get cache metrics: {e}")
            return {"status": "error", "error": str(e)}

def cache_key_generator(prefix: str, *args, **kwargs) -> str:
    """Generate consistent cache keys from function arguments"""
    key_parts = [prefix]
    
    # Add positional arguments
    for arg in args:
        key_parts.append(str(arg))
    
    # Add keyword arguments (sorted for consistency)
    for key, value in sorted(kwargs.items()):
        key_parts.append(f"{key}:{value}")
    
    return ":".join(key_parts)

def with_cache(cache_getter: Callable, key_func: Callable, ttl: Optional[int] = None, prefix: str = ""):
    """Decorator for function result caching with lazy cache initialization"""
    
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            cache_key = key_func(prefix, *args, **kwargs)
            
            try:
                cache = cache_getter()
                # Try to get from cache
                cached_result = await cache.get_async(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached_result
                
                # Execute function and cache result
                result = await func(*args, **kwargs)
                await cache.set_async(cache_key, result, ttl)
                
                logger.debug(f"Cache miss - stored: {cache_key}")
                return result
            except Exception as e:
                logger.warning(f"Cache operation failed, executing without cache: {e}")
                return await func(*args, **kwargs)
            
        def sync_wrapper(*args, **kwargs):
            cache_key = key_func(prefix, *args, **kwargs)
            
            try:
                cache = cache_getter()
                # Try to get from cache
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached_result
                
                # Execute function and cache result
                result = func(*args, **kwargs)
                cache.set(cache_key, result, ttl)
                
                logger.debug(f"Cache miss - stored: {cache_key}")
                return result
            except Exception as e:
                logger.warning(f"Cache operation failed, executing without cache: {e}")
                return func(*args, **kwargs)
            
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator

# Global cache configuration and instance
_cache_config = CacheConfig()
_redis_cache = RedisCache(_cache_config)

def initialize_cache():
    """Initialize global Redis cache"""
    _redis_cache.connect()
    return _redis_cache

def get_cache() -> RedisCache:
    """Get global Redis cache instance"""
    if not _redis_cache._connected:
        raise RuntimeError("Cache not initialized. Call initialize_cache() first.")
    return _redis_cache

# Cache TTL constants for different data types
CACHE_TTL = {
    'TEAM_PROFILE': 600,      # 10 minutes
    'GAME_DATA': 300,         # 5 minutes  
    'ODDS_DATA': 60,          # 1 minute (frequently updated)
    'GRADE_DATA': 1800,       # 30 minutes
    'ESPN_DATA': 600,         # 10 minutes
    'STATIC_DATA': 3600,      # 1 hour
    'SEASON_DATA': 86400,     # 24 hours
}