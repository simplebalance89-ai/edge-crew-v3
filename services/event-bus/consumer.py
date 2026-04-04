"""
Redis Streams Consumer with Consumer Groups.

Provides reliable event consumption with auto-scaling, retries, and DLQ support.
"""

import asyncio
import json
import logging
import signal
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Union

import redis.asyncio as redis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from models import BaseEvent, EventType, parse_event

logger = logging.getLogger(__name__)


@dataclass
class ConsumerConfig:
    """Configuration for event consumer."""
    
    redis_url: str = "redis://localhost:6379"
    stream_prefix: str = "edgecrew"
    consumer_group: str = "default-group"
    consumer_name: Optional[str] = None
    batch_size: int = 100
    block_timeout_ms: int = 5000
    claim_idle_timeout_ms: int = 60000  # Claim messages idle for 60s
    max_retries: int = 3
    retry_delays: List[float] = None
    enable_dlq: bool = True
    dlq_maxlen: int = 10000
    stream_maxlen: int = 100000
    heartbeat_interval_sec: int = 30
    auto_create_group: bool = True
    
    def __post_init__(self):
        if self.retry_delays is None:
            self.retry_delays = [1.0, 5.0, 15.0]  # Exponential-ish backoff
        if self.consumer_name is None:
            import socket
            import uuid
            self.consumer_name = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


class EventConsumerError(Exception):
    """Base exception for consumer errors."""
    pass


class EventProcessingError(EventConsumerError):
    """Raised when event processing fails."""
    pass


class EventHandler:
    """Wrapper for event handler functions with metadata."""
    
    def __init__(
        self,
        event_type: str,
        handler: Callable[[BaseEvent], Awaitable[None]],
        filter_fn: Optional[Callable[[BaseEvent], bool]] = None,
    ):
        self.event_type = event_type
        self.handler = handler
        self.filter_fn = filter_fn
        self.processed_count = 0
        self.failed_count = 0
    
    async def should_process(self, event: BaseEvent) -> bool:
        """Check if event should be processed by this handler."""
        if self.filter_fn:
            return self.filter_fn(event)
        return True
    
    async def execute(self, event: BaseEvent) -> None:
        """Execute the handler."""
        await self.handler(event)
        self.processed_count += 1


class EventBusConsumer:
    """
    Redis Streams Consumer with Consumer Groups support.
    
    Features:
    - Consumer groups for horizontal scaling
    - Automatic message claiming from failed consumers
    - Dead letter queue for permanently failed messages
    - Event type filtering and routing
    - Graceful shutdown handling
    - Heartbeat mechanism for liveness
    """
    
    def __init__(self, config: Optional[ConsumerConfig] = None):
        self.config = config or ConsumerConfig()
        self._redis: Optional[redis.Redis] = None
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._tasks: Set[asyncio.Task] = set()
        self._claimed_messages: Dict[str, Any] = {}
        self._metrics: Dict[str, Any] = {
            "received": 0,
            "processed": 0,
            "failed": 0,
            "dlq": 0,
            "claimed": 0,
        }
    
    async def connect(self) -> None:
        """Establish Redis connection."""
        self._redis = redis.from_url(
            self.config.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )
        await self._redis.ping()
        logger.info(f"Consumer connected to Redis: {self.config.consumer_name}")
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
        logger.info("Consumer disconnected from Redis")
    
    async def _create_consumer_group(self, stream_name: str) -> None:
        """Create consumer group if it doesn't exist."""
        try:
            await self._redis.xgroup_create(
                stream_name,
                self.config.consumer_group,
                id="0",  # Start from beginning if new
                mkstream=True,
            )
            logger.info(f"Created consumer group {self.config.consumer_group} for {stream_name}")
        except redis.ResponseError as e:
            if "already exists" in str(e):
                pass  # Group already exists, that's fine
            else:
                raise
    
    def subscribe(
        self,
        event_type: Union[str, EventType],
        filter_fn: Optional[Callable[[BaseEvent], bool]] = None,
    ) -> Callable:
        """
        Decorator to subscribe to an event type.
        
        Usage:
            @consumer.subscribe("odds.updated")
            async def handle_odds(event):
                print(event)
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        
        def decorator(handler: Callable[[BaseEvent], Awaitable[None]]) -> Callable:
            if event_type_str not in self._handlers:
                self._handlers[event_type_str] = []
            
            self._handlers[event_type_str].append(
                EventHandler(event_type_str, handler, filter_fn)
            )
            logger.info(f"Registered handler for {event_type_str}")
            return handler
        
        return decorator
    
    def on(
        self,
        event_type: Union[str, EventType],
        handler: Optional[Callable[[BaseEvent], Awaitable[None]]] = None,
        filter_fn: Optional[Callable[[BaseEvent], bool]] = None,
    ) -> Optional[Callable]:
        """
        Register a handler for an event type (imperative style).
        
        Can be used as decorator or function call.
        """
        if handler is None:
            # Used as decorator
            return self.subscribe(event_type, filter_fn)
        
        # Used as function call
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        
        if event_type_str not in self._handlers:
            self._handlers[event_type_str] = []
        
        self._handlers[event_type_str].append(
            EventHandler(event_type_str, handler, filter_fn)
        )
        logger.info(f"Registered handler for {event_type_str}")
        return None
    
    def _get_stream_name(self, event_type: str) -> str:
        """Get Redis stream name for event type."""
        return f"{self.config.stream_prefix}:{event_type}"
    
    def _get_dlq_name(self, event_type: str) -> str:
        """Get dead letter queue name."""
        return f"{self.config.stream_prefix}:dlq:{event_type}"
    
    async def _claim_pending_messages(self, stream_name: str) -> List[Dict[str, Any]]:
        """Claim messages from consumers that appear to be dead."""
        try:
            # Get pending messages info
            pending_info = await self._redis.xpending_range(
                stream_name,
                self.config.consumer_group,
                min="-",
                max="+",
                count=self.config.batch_size,
            )
            
            if not pending_info:
                return []
            
            # Find messages that have been idle too long
            message_ids_to_claim = []
            for item in pending_info:
                if item.get("time_since_delivered", 0) > self.config.claim_idle_timeout_ms:
                    message_ids_to_claim.append(item["message_id"])
            
            if not message_ids_to_claim:
                return []
            
            # Claim the messages
            claimed = await self._redis.xclaim(
                stream_name,
                self.config.consumer_group,
                self.config.consumer_name,
                min_idle_time=self.config.claim_idle_timeout_ms,
                message_ids=message_ids_to_claim,
            )
            
            if claimed:
                self._metrics["claimed"] += len(claimed)
                logger.info(f"Claimed {len(claimed)} messages from {stream_name}")
            
            return claimed
            
        except Exception as e:
            logger.error(f"Error claiming pending messages: {e}")
            return []
    
    async def _send_to_dlq(
        self,
        stream_name: str,
        message_id: str,
        event_data: Dict[str, Any],
        error: str,
        retry_count: int,
    ) -> None:
        """Send failed message to dead letter queue."""
        if not self.config.enable_dlq:
            return
        
        try:
            # Extract event type from stream name
            event_type = stream_name.replace(f"{self.config.stream_prefix}:", "")
            dlq_name = self._get_dlq_name(event_type)
            
            dlq_entry = {
                "original_stream": stream_name,
                "original_id": message_id,
                "error": error,
                "retry_count": str(retry_count),
                "failed_at": datetime.utcnow().isoformat(),
                "consumer": self.config.consumer_name,
                "event_data": json.dumps(event_data),
            }
            
            await self._redis.xadd(dlq_name, dlq_entry, maxlen=self.config.dlq_maxlen, approximate=True)
            self._metrics["dlq"] += 1
            
            logger.warning(f"Sent message {message_id} to DLQ: {dlq_name}")
        except Exception as e:
            logger.error(f"Failed to send to DLQ: {e}")
    
    async def _process_message(
        self,
        stream_name: str,
        message_id: str,
        message_data: Dict[str, str],
    ) -> bool:
        """Process a single message. Returns True if successful."""
        event_type = message_data.get("event_type", "")
        
        # Parse the event
        try:
            event = parse_event(event_type, message_data)
        except Exception as e:
            logger.error(f"Failed to parse event from {message_id}: {e}")
            return False
        
        # Get handlers for this event type
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            logger.warning(f"No handlers for event type: {event_type}")
            return True  # Ack anyway, nothing to do
        
        # Execute handlers
        any_failed = False
        for handler in handlers:
            try:
                if await handler.should_process(event):
                    await handler.execute(event)
            except Exception as e:
                logger.exception(f"Handler failed for {event_type}: {e}")
                any_failed = True
        
        if not any_failed:
            self._metrics["processed"] += 1
        
        return not any_failed
    
    async def _process_with_retry(
        self,
        stream_name: str,
        message_id: str,
        message_data: Dict[str, str],
    ) -> bool:
        """Process message with retry logic."""
        retry_count = 0
        last_error = None
        
        for retry_delay in self.config.retry_delays:
            try:
                success = await self._process_message(stream_name, message_id, message_data)
                if success:
                    return True
                retry_count += 1
                await asyncio.sleep(retry_delay)
            except Exception as e:
                last_error = str(e)
                retry_count += 1
                logger.warning(f"Retry {retry_count} for {message_id}: {e}")
                await asyncio.sleep(retry_delay)
        
        # All retries exhausted, send to DLQ
        await self._send_to_dlq(
            stream_name,
            message_id,
            message_data,
            last_error or "Max retries exceeded",
            retry_count,
        )
        
        self._metrics["failed"] += 1
        return False
    
    async def _consume_stream(self, stream_name: str) -> None:
        """Consume messages from a single stream."""
        if self.config.auto_create_group:
            await self._create_consumer_group(stream_name)
        
        while self._running and not self._shutdown_event.is_set():
            try:
                # First, try to claim pending messages from dead consumers
                claimed = await self._claim_pending_messages(stream_name)
                for msg_id, msg_data in claimed:
                    self._metrics["received"] += 1
                    await self._process_with_retry(stream_name, msg_id, msg_data)
                    await self._redis.xack(stream_name, self.config.consumer_group, msg_id)
                
                # Read new messages
                streams = {stream_name: ">"}  ">" means undelivered messages
                
                messages = await self._redis.xreadgroup(
                    groupname=self.config.consumer_group,
                    consumername=self.config.consumer_name,
                    streams=streams,
                    count=self.config.batch_size,
                    block=self.config.block_timeout_ms,
                )
                
                if not messages:
                    continue
                
                # Process messages
                for stream_key, entries in messages:
                    for msg_id, msg_data in entries:
                        self._metrics["received"] += 1
                        
                        success = await self._process_with_retry(stream_name, msg_id, msg_data)
                        
                        # Acknowledge message
                        if success:
                            await self._redis.xack(stream_name, self.config.consumer_group, msg_id)
                        
            except asyncio.CancelledError:
                break
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"Redis connection error: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.exception(f"Error consuming from {stream_name}: {e}")
                await asyncio.sleep(1)
    
    async def _heartbeat(self) -> None:
        """Send periodic heartbeat to indicate consumer is alive."""
        while self._running and not self._shutdown_event.is_set():
            try:
                await self._redis.setex(
                    f"consumer:{self.config.consumer_name}:heartbeat",
                    self.config.heartbeat_interval_sec * 2,
                    datetime.utcnow().isoformat(),
                )
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
            
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.config.heartbeat_interval_sec,
                )
            except asyncio.TimeoutError:
                pass
    
    async def start(self) -> None:
        """Start consuming events."""
        if not self._handlers:
            raise EventConsumerError("No handlers registered")
        
        await self.connect()
        self._running = True
        
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.stop)
        
        # Start heartbeat
        heartbeat_task = asyncio.create_task(self._heartbeat())
        self._tasks.add(heartbeat_task)
        
        # Start consumers for each stream
        streams_to_consume = set()
        for event_type in self._handlers.keys():
            streams_to_consume.add(self._get_stream_name(event_type))
        
        logger.info(f"Starting consumers for streams: {streams_to_consume}")
        
        for stream_name in streams_to_consume:
            task = asyncio.create_task(self._consume_stream(stream_name))
            self._tasks.add(task)
        
        # Wait for shutdown
        await self._shutdown_event.wait()
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        await self.disconnect()
    
    def stop(self) -> None:
        """Signal the consumer to stop."""
        logger.info("Stopping consumer...")
        self._running = False
        self._shutdown_event.set()
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get consumer metrics."""
        metrics = self._metrics.copy()
        metrics["running"] = self._running
        metrics["consumer_name"] = self.config.consumer_name
        metrics["handlers"] = {k: len(v) for k, v in self._handlers.items()}
        return metrics
    
    async def health_check(self) -> Dict[str, Any]:
        """Check consumer health."""
        try:
            if self._redis:
                await self._redis.ping()
                return {
                    "status": "healthy",
                    "running": self._running,
                    "consumer_name": self.config.consumer_name,
                }
        except Exception:
            pass
        
        return {
            "status": "unhealthy",
            "running": self._running,
            "consumer_name": self.config.consumer_name,
        }
