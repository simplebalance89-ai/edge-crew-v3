"""
Edge Crew v3.0 Event Bus

A Redis Streams-based event bus for reliable, scalable inter-service communication.

Usage:
    from event_bus import EventBus
    
    bus = EventBus(redis_url="redis://localhost:6379")
    
    # Publish events
    await bus.publish("odds.updated", {"game_id": "nba-123", "spread": -4.5})
    
    # Subscribe to events
    @bus.subscribe("odds.updated", group="grading-engine")
    async def handle_odds(event):
        print(f"Odds updated: {event}")
"""

from typing import Optional, Callable, Any, Dict, Union
import asyncio
import logging

__version__ = "3.0.0"

# Import models first
from models import (
    BaseEvent,
    EdgeDetectedEvent,
    EventMetadata,
    EventType,
    GameCompletedEvent,
    GameStartedEvent,
    GradeCompletedEvent,
    GradeRequestedEvent,
    InjuryReportedEvent,
    OddsLineMovedEvent,
    OddsUpdatedEvent,
    PickGeneratedEvent,
)
from consumer import EventBusConsumer, ConsumerConfig
from producer import EventBusProducer

logger = logging.getLogger(__name__)


class EventBus:
    """
    Unified EventBus interface for publishing and subscribing to events.
    
    This class combines the Producer and Consumer functionality into a single,
    easy-to-use interface.
    
    Example:
        bus = EventBus(redis_url="redis://localhost:6379")
        
        # Start consuming in background
        await bus.start()
        
        # Publish events
        await bus.publish("odds.updated", {...})
        
        # Subscribe with decorator
        @bus.subscribe("odds.updated", group="my-service")
        async def handler(event):
            pass
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_prefix: str = "edgecrew",
        consumer_group: Optional[str] = None,
        consumer_name: Optional[str] = None,
    ):
        self.redis_url = redis_url
        self.stream_prefix = stream_prefix
        
        # Initialize producer
        self.producer = EventBusProducer(
            redis_url=redis_url,
            stream_prefix=stream_prefix,
        )
        
        # Initialize consumer config (but don't start yet)
        self._consumer_config = ConsumerConfig(
            redis_url=redis_url,
            stream_prefix=stream_prefix,
            consumer_group=consumer_group or "default-group",
            consumer_name=consumer_name,
        )
        self.consumer = EventBusConsumer(self._consumer_config)
        self._consumer_task: Optional[asyncio.Task] = None
    
    async def publish(
        self,
        event_type: Union[str, EventType],
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Publish an event to the bus.
        
        Args:
            event_type: Type of event (e.g., 'odds.updated')
            data: Event payload data
            metadata: Optional metadata (source, correlation_id, etc.)
            
        Returns:
            Message ID from Redis
        """
        return await self.producer.publish(event_type, data, metadata)
    
    async def publish_event(self, event: BaseEvent) -> str:
        """
        Publish a typed event object.
        
        Args:
            event: Pydantic BaseEvent instance
            
        Returns:
            Message ID from Redis
        """
        return await self.producer.publish_event(event)
    
    def subscribe(
        self,
        event_type: Union[str, EventType],
        group: Optional[str] = None,
        filter_fn: Optional[Callable[[BaseEvent], bool]] = None,
    ) -> Callable:
        """
        Decorator to subscribe to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            group: Consumer group name (overrides default)
            filter_fn: Optional filter function
            
        Usage:
            @bus.subscribe("odds.updated", group="grading-engine")
            async def handle_odds(event):
                await process_odds(event)
        """
        # Update consumer group if specified
        if group:
            self._consumer_config.consumer_group = group
            self.consumer.config.consumer_group = group
        
        return self.consumer.subscribe(event_type, filter_fn)
    
    async def start(self) -> None:
        """Start the consumer in the background."""
        if self._consumer_task and not self._consumer_task.done():
            return
        
        self._consumer_task = asyncio.create_task(self.consumer.start())
        logger.info("EventBus consumer started")
    
    async def stop(self) -> None:
        """Stop the consumer."""
        self.consumer.stop()
        if self._consumer_task:
            try:
                await asyncio.wait_for(self._consumer_task, timeout=30)
            except asyncio.TimeoutError:
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass
        
        await self.producer.disconnect()
        logger.info("EventBus stopped")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of both producer and consumer."""
        producer_health = await self.producer.health_check()
        consumer_health = await self.consumer.health_check()
        
        return {
            "status": "healthy" if producer_health["status"] == "healthy" else "unhealthy",
            "producer": producer_health,
            "consumer": consumer_health,
        }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get combined metrics from producer and consumer."""
        return {
            "producer": await self.producer.get_metrics(),
            "consumer": await self.consumer.get_metrics(),
        }


__all__ = [
    "EventBus",
    "EventBusProducer",
    "EventBusConsumer",
    "ConsumerConfig",
    "BaseEvent",
    "EventMetadata",
    "EventType",
    "OddsUpdatedEvent",
    "OddsLineMovedEvent",
    "InjuryReportedEvent",
    "GameStartedEvent",
    "GameCompletedEvent",
    "GradeRequestedEvent",
    "GradeCompletedEvent",
    "EdgeDetectedEvent",
    "PickGeneratedEvent",
]
