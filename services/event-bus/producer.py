"""
Async Producer for Redis Streams Event Bus.

Provides reliable event publishing with retries, batching, and monitoring.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import redis.asyncio as redis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from models import BaseEvent, EventMetadata, EventType

logger = logging.getLogger(__name__)


class EventBusProducerError(Exception):
    """Base exception for producer errors."""
    pass


class EventBusConnectionError(EventBusProducerError):
    """Raised when connection to Redis fails."""
    pass


class EventBusPublishError(EventBusProducerError):
    """Raised when publishing fails after retries."""
    pass


class EventBusProducer:
    """
    Async producer for publishing events to Redis Streams.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Event validation via Pydantic models
    - Batch publishing for high throughput
    - Dead letter queue for failed events
    - Metrics tracking
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_prefix: str = "edgecrew",
        max_retries: int = 3,
        retry_base_delay: float = 0.1,
        retry_max_delay: float = 5.0,
        connection_timeout: int = 5,
        socket_keepalive: bool = True,
        enable_metrics: bool = True,
    ):
        self.redis_url = redis_url
        self.stream_prefix = stream_prefix
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay = retry_max_delay
        self.connection_timeout = connection_timeout
        self.socket_keepalive = socket_keepalive
        self.enable_metrics = enable_metrics
        
        self._redis: Optional[redis.Redis] = None
        self._connected = False
        self._metrics: Dict[str, Any] = {
            "published": 0,
            "failed": 0,
            "retried": 0,
            "batches": 0,
        }
        self._lock = asyncio.Lock()
    
    async def connect(self) -> None:
        """Establish connection to Redis."""
        async with self._lock:
            if self._connected:
                return
            
            try:
                self._redis = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=self.connection_timeout,
                    socket_keepalive=self.socket_keepalive,
                )
                # Verify connection
                await self._redis.ping()
                self._connected = True
                logger.info(f"Connected to Redis at {self.redis_url}")
            except (ConnectionError, TimeoutError) as e:
                self._connected = False
                raise EventBusConnectionError(f"Failed to connect to Redis: {e}") from e
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        async with self._lock:
            if self._redis:
                await self._redis.close()
                self._redis = None
            self._connected = False
            logger.info("Disconnected from Redis")
    
    @asynccontextmanager
    async def session(self):
        """Context manager for producer sessions."""
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()
    
    def _get_stream_name(self, event_type: str) -> str:
        """Get the Redis stream name for an event type."""
        return f"{self.stream_prefix}:{event_type}"
    
    def _get_dlq_name(self, event_type: str) -> str:
        """Get the dead letter queue name for an event type."""
        return f"{self.stream_prefix}:dlq:{event_type}"
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = self.retry_base_delay * (2 ** attempt)
        return min(delay, self.retry_max_delay)
    
    async def _publish_with_retry(
        self,
        stream_name: str,
        event_data: Dict[str, str],
        event_type: str,
    ) -> Optional[str]:
        """Publish event with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if not self._connected or not self._redis:
                    await self.connect()
                
                # XADD to Redis Stream
                message_id = await self._redis.xadd(
                    stream_name,
                    event_data,
                    maxlen=100000,  # Keep last 100k events per stream
                    approximate=True,
                )
                
                if self.enable_metrics:
                    self._metrics["published"] += 1
                
                logger.debug(f"Published event to {stream_name}: {message_id}")
                return message_id
                
            except (ConnectionError, TimeoutError, RedisError) as e:
                last_error = e
                self._connected = False
                
                if attempt < self.max_retries:
                    delay = self._calculate_retry_delay(attempt)
                    if self.enable_metrics:
                        self._metrics["retried"] += 1
                    logger.warning(
                        f"Publish attempt {attempt + 1} failed, retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All publish attempts failed for {stream_name}: {e}")
        
        # All retries exhausted, send to DLQ
        await self._send_to_dlq(event_type, event_data, str(last_error))
        raise EventBusPublishError(f"Failed to publish after {self.max_retries} retries: {last_error}")
    
    async def _send_to_dlq(
        self,
        event_type: str,
        event_data: Dict[str, str],
        error_message: str,
    ) -> None:
        """Send failed event to dead letter queue."""
        try:
            dlq_name = self._get_dlq_name(event_type)
            dlq_entry = {
                "original_stream": self._get_stream_name(event_type),
                "error": error_message,
                "failed_at": datetime.utcnow().isoformat(),
                "event_data": json.dumps(event_data),
            }
            
            if self._redis:
                await self._redis.xadd(dlq_name, dlq_entry, maxlen=10000, approximate=True)
            
            if self.enable_metrics:
                self._metrics["failed"] += 1
            
            logger.warning(f"Sent failed event to DLQ: {dlq_name}")
        except Exception as e:
            logger.error(f"Failed to send to DLQ: {e}")
    
    async def publish(
        self,
        event_type: Union[str, EventType],
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Publish a single event to Redis Streams.
        
        Args:
            event_type: Type of event (e.g., 'odds.updated')
            data: Event payload data
            metadata: Optional metadata overrides
            
        Returns:
            Message ID from Redis
            
        Raises:
            EventBusConnectionError: If cannot connect to Redis
            EventBusPublishError: If publishing fails after retries
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        
        # Build event with metadata
        event_meta = EventMetadata(
            source=metadata.get("source", "event-bus") if metadata else "event-bus",
            correlation_id=metadata.get("correlation_id") if metadata else None,
        )
        
        event_data = {
            "event_type": event_type_str,
            "data": json.dumps({
                "metadata": event_meta.model_dump(mode="json"),
                "payload": data,
            }),
        }
        
        stream_name = self._get_stream_name(event_type_str)
        message_id = await self._publish_with_retry(stream_name, event_data, event_type_str)
        
        return message_id or ""
    
    async def publish_event(self, event: BaseEvent) -> str:
        """
        Publish a typed event object.
        
        Args:
            event: Pydantic BaseEvent instance
            
        Returns:
            Message ID from Redis
        """
        stream_name = self._get_stream_name(event.event_type)
        event_data = event.to_stream_data()
        
        message_id = await self._publish_with_retry(stream_name, event_data, event.event_type)
        return message_id or ""
    
    async def publish_batch(
        self,
        events: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Publish multiple events efficiently using pipeline.
        
        Args:
            events: List of {"event_type": str, "data": dict, "metadata": dict}
            
        Returns:
            List of message IDs
        """
        if not self._connected or not self._redis:
            await self.connect()
        
        message_ids = []
        pipeline = self._redis.pipeline(transaction=False)
        
        try:
            for event in events:
                event_type = event["event_type"]
                data = event.get("data", {})
                metadata = event.get("metadata", {})
                
                event_meta = EventMetadata(
                    source=metadata.get("source", "event-bus"),
                    correlation_id=metadata.get("correlation_id"),
                )
                
                stream_name = self._get_stream_name(event_type)
                event_data = {
                    "event_type": event_type,
                    "data": json.dumps({
                        "metadata": event_meta.model_dump(mode="json"),
                        "payload": data,
                    }),
                }
                
                pipeline.xadd(stream_name, event_data, maxlen=100000, approximate=True)
            
            results = await pipeline.execute()
            message_ids = [str(r) for r in results if r]
            
            if self.enable_metrics:
                self._metrics["published"] += len(message_ids)
                self._metrics["batches"] += 1
            
            logger.debug(f"Published batch of {len(message_ids)} events")
            
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Batch publish failed: {e}")
            # Fall back to individual publishes with retry
            for event in events:
                try:
                    msg_id = await self.publish(
                        event["event_type"],
                        event.get("data", {}),
                        event.get("metadata"),
                    )
                    message_ids.append(msg_id)
                except EventBusPublishError:
                    pass
        
        return message_ids
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get producer metrics."""
        metrics = self._metrics.copy()
        metrics["connected"] = self._connected
        return metrics
    
    async def health_check(self) -> Dict[str, Any]:
        """Check producer health."""
        try:
            if self._redis:
                await self._redis.ping()
                return {
                    "status": "healthy",
                    "connected": True,
                    "redis_url": self.redis_url,
                }
        except Exception as e:
            pass
        
        return {
            "status": "unhealthy",
            "connected": False,
            "redis_url": self.redis_url,
        }
