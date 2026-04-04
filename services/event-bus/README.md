# Edge Crew v3.0 Event Bus

A Redis Streams-based event bus for reliable, scalable inter-service communication in the Edge Crew ecosystem.

## Features

- **Redis Streams**: Persistent message queuing with automatic replay capability
- **Consumer Groups**: Horizontal scaling with automatic load balancing
- **Dead Letter Queue**: Failed events are captured for later analysis
- **Event Schema Validation**: Pydantic models ensure type safety
- **Automatic Retry**: Exponential backoff for transient failures
- **Metrics & Monitoring**: Built-in health checks and metrics endpoints

## Quick Start

### Running with Docker

```bash
# Start Redis and Event Bus
docker run -d -p 6379:6379 redis:7-alpine
uvicorn main:app --reload
```

### Using the Event Bus

```python
from event_bus import EventBus

# Initialize
bus = EventBus(redis_url="redis://localhost:6379")

# Subscribe to events
@bus.subscribe("odds.updated", group="grading-engine")
async def handle_odds(event):
    print(f"Odds updated: {event.game_id}")
    await regrade_game(event.game_id)

# Start consuming
await bus.start()

# Publish events
await bus.publish("odds.updated", {
    "game_id": "nba-123",
    "bookmaker": "draftkings",
    "spread": -4.5,
    "timestamp": "2026-04-04T00:00:00Z"
})
```

## Event Types

| Event Type | Description |
|------------|-------------|
| `odds.updated` | New odds available for a game |
| `odds.line_moved` | Significant line movement detected |
| `injury.reported` | New injury report published |
| `game.started` | Game has begun |
| `game.completed` | Game has ended |
| `grade.requested` | Request to grade a pick |
| `grade.completed` | Grading has been completed |
| `edge.detected` | Edge detected on a game |
| `pick.generated` | New pick has been generated |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /metrics` | Producer metrics |
| `POST /publish` | Publish a single event |
| `POST /publish/batch` | Publish multiple events |
| `GET /streams` | List all streams |
| `GET /event-types` | List supported event types |

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `STREAM_PREFIX` | `edgecrew` | Prefix for stream names |
| `PORT` | `8000` | HTTP server port |
| `HOST` | `0.0.0.0` | HTTP server host |

## Project Structure

```
event-bus/
├── __init__.py      # EventBus unified interface
├── models.py        # Pydantic event models
├── producer.py      # Event publisher
├── consumer.py      # Event consumer with groups
├── main.py          # FastAPI HTTP service
├── Dockerfile       # Container definition
├── requirements.txt # Dependencies
└── README.md        # This file
```

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Odds Service   │────▶│              │     │ Grading Engine  │
└─────────────────┘     │              │     └─────────────────┘
                        │              │     ┌─────────────────┐
┌─────────────────┐     │   Redis      │     │  Pick Service   │
│ Injury Service  │────▶│   Streams    │────▶└─────────────────┘
└─────────────────┘     │              │     ┌─────────────────┐
                        │              │     │  Edge Detector  │
┌─────────────────┐     │              │     └─────────────────┘
│  Game Service   │────▶│              │
└─────────────────┘     └──────────────┘
```
