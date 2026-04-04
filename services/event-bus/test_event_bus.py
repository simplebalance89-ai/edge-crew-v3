"""
Tests for the Edge Crew Event Bus.

Run with: pytest test_event_bus.py -v
"""

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from models import (
    BaseEvent,
    EventMetadata,
    EventType,
    OddsUpdatedEvent,
    OddsData,
    EdgeDetectedEvent,
    EdgeData,
    GradeRequestedEvent,
)
from producer import EventBusProducer, EventBusProducerError
from consumer import EventBusConsumer, ConsumerConfig


# ============================================================================
# Model Tests
# ============================================================================

def test_event_type_enum():
    """Test EventType enum values."""
    assert EventType.ODDS_UPDATED == "odds.updated"
    assert EventType.ODDS_LINE_MOVED == "odds.line_moved"
    assert EventType.INJURY_REPORTED == "injury.reported"
    assert EventType.GAME_STARTED == "game.started"
    assert EventType.GAME_COMPLETED == "game.completed"
    assert EventType.GRADE_REQUESTED == "grade.requested"
    assert EventType.GRADE_COMPLETED == "grade.completed"
    assert EventType.EDGE_DETECTED == "edge.detected"
    assert EventType.PICK_GENERATED == "pick.generated"


def test_odds_updated_event():
    """Test OddsUpdatedEvent creation and serialization."""
    event = OddsUpdatedEvent(
        game_id="nba-123",
        sport="nba",
        home_team="Lakers",
        away_team="Warriors",
        odds=OddsData(
            bookmaker="draftkings",
            spread=-4.5,
            spread_odds=-110,
        )
    )
    
    assert event.event_type == "odds.updated"
    assert event.game_id == "nba-123"
    assert event.odds.bookmaker == "draftkings"
    assert event.odds.spread == -4.5
    
    # Test serialization
    stream_data = event.to_stream_data()
    assert stream_data["event_type"] == "odds.updated"
    assert "data" in stream_data
    
    # Test deserialization
    restored = OddsUpdatedEvent.from_stream_data(stream_data)
    assert restored.game_id == event.game_id
    assert restored.odds.bookmaker == event.odds.bookmaker


def test_edge_detected_event():
    """Test EdgeDetectedEvent creation."""
    event = EdgeDetectedEvent(
        game_id="nfl-456",
        edge_type="spread",
        bookmaker="fanduel",
        edge=EdgeData(
            edge_percentage=5.2,
            model_prediction=-6.5,
            market_line=-4.5,
            expected_value=0.52,
            confidence=0.85,
            factors=["rest_advantage"],
        ),
        recommended_action="bet",
    )
    
    assert event.event_type == "edge.detected"
    assert event.edge.edge_percentage == 5.2
    assert event.edge.confidence == 0.85
    assert "rest_advantage" in event.edge.factors


def test_grade_requested_event():
    """Test GradeRequestedEvent creation."""
    event = GradeRequestedEvent(
        game_id="nba-789",
        pick_id="pick-001",
        grading_type="auto",
        priority=8,
        requested_by="scheduler-service",
    )
    
    assert event.event_type == "grade.requested"
    assert event.priority == 8
    assert event.grading_type == "auto"


def test_event_metadata_defaults():
    """Test EventMetadata default values."""
    meta = EventMetadata()
    
    assert meta.source == "unknown"
    assert meta.version == "1.0"
    assert meta.retry_count == 0
    assert meta.correlation_id is None
    assert isinstance(meta.event_id, object)  # UUID
    assert isinstance(meta.timestamp, datetime)


# ============================================================================
# Producer Tests
# ============================================================================

@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.xadd = AsyncMock(return_value="1234567890-0")
    mock.close = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_producer_connect(mock_redis):
    """Test producer connection."""
    with patch('producer.redis.from_url', return_value=mock_redis):
        producer = EventBusProducer(redis_url="redis://localhost:6379")
        await producer.connect()
        
        assert producer._connected is True
        mock_redis.ping.assert_called_once()


@pytest.mark.asyncio
async def test_producer_publish(mock_redis):
    """Test publishing an event."""
    with patch('producer.redis.from_url', return_value=mock_redis):
        producer = EventBusProducer(redis_url="redis://localhost:6379")
        await producer.connect()
        
        message_id = await producer.publish(
            event_type="odds.updated",
            data={"game_id": "nba-123", "spread": -4.5},
        )
        
        assert message_id == "1234567890-0"
        mock_redis.xadd.assert_called_once()
        
        # Verify stream name
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "edgecrew:odds.updated"


@pytest.mark.asyncio
async def test_producer_publish_event(mock_redis):
    """Test publishing a typed event."""
    with patch('producer.redis.from_url', return_value=mock_redis):
        producer = EventBusProducer(redis_url="redis://localhost:6379")
        await producer.connect()
        
        event = OddsUpdatedEvent(
            game_id="nba-123",
            sport="nba",
            home_team="Lakers",
            away_team="Warriors",
            odds=OddsData(bookmaker="dk", spread=-4.5),
        )
        
        message_id = await producer.publish_event(event)
        
        assert message_id == "1234567890-0"
        mock_redis.xadd.assert_called_once()


@pytest.mark.asyncio
async def test_producer_batch_publish(mock_redis):
    """Test batch publishing."""
    mock_redis.pipeline = MagicMock(return_value=AsyncMock())
    pipeline = mock_redis.pipeline.return_value
    pipeline.execute = AsyncMock(return_value=["1-0", "2-0", "3-0"])
    
    with patch('producer.redis.from_url', return_value=mock_redis):
        producer = EventBusProducer(redis_url="redis://localhost:6379")
        await producer.connect()
        
        events = [
            {"event_type": "odds.updated", "data": {"game_id": "1"}},
            {"event_type": "odds.updated", "data": {"game_id": "2"}},
            {"event_type": "game.started", "data": {"game_id": "3"}},
        ]
        
        message_ids = await producer.publish_batch(events)
        
        assert len(message_ids) == 3
        pipeline.execute.assert_called_once()


@pytest.mark.asyncio
async def test_producer_retry_logic(mock_redis):
    """Test producer retry with exponential backoff."""
    from redis.exceptions import ConnectionError
    
    # First two calls fail, third succeeds
    mock_redis.xadd = AsyncMock(side_effect=[
        ConnectionError("Connection failed"),
        ConnectionError("Connection failed"),
        "1234567890-0",
    ])
    
    with patch('producer.redis.from_url', return_value=mock_redis):
        producer = EventBusProducer(
            redis_url="redis://localhost:6379",
            retry_base_delay=0.01,  # Fast retries for testing
        )
        await producer.connect()
        
        # Should succeed after retries
        message_id = await producer.publish(
            event_type="odds.updated",
            data={"game_id": "nba-123"},
        )
        
        assert message_id == "1234567890-0"
        assert mock_redis.xadd.call_count == 3


@pytest.mark.asyncio
async def test_producer_dlq_on_failure(mock_redis):
    """Test that failed messages go to DLQ."""
    from redis.exceptions import ConnectionError
    
    # All calls fail
    mock_redis.xadd = AsyncMock(side_effect=ConnectionError("Connection failed"))
    mock_redis.ping = AsyncMock(return_value=True)
    
    with patch('producer.redis.from_url', return_value=mock_redis):
        producer = EventBusProducer(
            redis_url="redis://localhost:6379",
            max_retries=2,
            retry_base_delay=0.01,
        )
        await producer.connect()
        
        with pytest.raises(EventBusProducerError):
            await producer.publish(
                event_type="odds.updated",
                data={"game_id": "nba-123"},
            )
        
        # Should have attempted to send to DLQ
        # DLQ call is the 4th xadd call (3 retries + 1 DLQ)
        assert mock_redis.xadd.call_count == 4


# ============================================================================
# Consumer Tests
# ============================================================================

def test_consumer_config_defaults():
    """Test ConsumerConfig default values."""
    config = ConsumerConfig()
    
    assert config.redis_url == "redis://localhost:6379"
    assert config.stream_prefix == "edgecrew"
    assert config.consumer_group == "default-group"
    assert config.batch_size == 100
    assert config.block_timeout_ms == 5000
    assert config.max_retries == 3


def test_consumer_config_custom():
    """Test ConsumerConfig with custom values."""
    config = ConsumerConfig(
        redis_url="redis://custom:6379",
        consumer_group="my-service",
        batch_size=50,
    )
    
    assert config.redis_url == "redis://custom:6379"
    assert config.consumer_group == "my-service"
    assert config.batch_size == 50


@pytest.mark.asyncio
async def test_consumer_subscribe_decorator():
    """Test consumer subscribe decorator."""
    config = ConsumerConfig()
    consumer = EventBusConsumer(config)
    
    @consumer.subscribe("odds.updated")
    async def handler(event):
        pass
    
    assert "odds.updated" in consumer._handlers
    assert len(consumer._handlers["odds.updated"]) == 1


@pytest.mark.asyncio
async def test_consumer_on_method():
    """Test consumer on() method."""
    config = ConsumerConfig()
    consumer = EventBusConsumer(config)
    
    async def handler(event):
        pass
    
    consumer.on("game.started", handler)
    
    assert "game.started" in consumer._handlers
    assert len(consumer._handlers["game.started"]) == 1


@pytest.mark.asyncio
async def test_consumer_handler_filter():
    """Test consumer handler with filter."""
    config = ConsumerConfig()
    consumer = EventBusConsumer(config)
    
    @consumer.subscribe(
        "grade.requested",
        filter_fn=lambda e: e.priority >= 8
    )
    async def high_priority_handler(event):
        pass
    
    handler = consumer._handlers["grade.requested"][0]
    
    # Test filter allows high priority
    event_high = GradeRequestedEvent(
        game_id="game-1",
        priority=9,
        requested_by="system",
    )
    assert await handler.should_process(event_high) is True
    
    # Test filter blocks low priority
    event_low = GradeRequestedEvent(
        game_id="game-2",
        priority=3,
        requested_by="user",
    )
    assert await handler.should_process(event_low) is False


# ============================================================================
# Integration Tests (require Redis)
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_event_flow():
    """Test complete event publish/consume flow.
    
    Requires Redis to be running on localhost:6379.
    """
    from event_bus import EventBus
    
    received_events = []
    
    bus = EventBus(redis_url="redis://localhost:6379")
    
    @bus.subscribe("test.event", group="test-group")
    async def handler(event):
        received_events.append(event)
    
    # Start consumer
    consumer_task = asyncio.create_task(bus.start())
    
    # Give consumer time to start
    await asyncio.sleep(0.5)
    
    # Publish event
    await bus.publish("test.event", {
        "test_id": "123",
        "value": 42,
    })
    
    # Wait for processing
    await asyncio.sleep(1)
    
    # Stop
    bus.stop()
    
    try:
        await asyncio.wait_for(consumer_task, timeout=2)
    except asyncio.TimeoutError:
        consumer_task.cancel()
    
    # Verify
    assert len(received_events) == 1
    assert received_events[0].payload["test_id"] == "123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
