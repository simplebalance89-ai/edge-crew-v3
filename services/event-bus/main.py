"""
FastAPI Application for Edge Crew v3.0 Event Bus Service.

Provides HTTP endpoints for:
- Publishing events
- Health checks
- Metrics
- Consumer management
- Dead letter queue management
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models import (
    BaseEvent,
    EVENT_REGISTRY,
    EventType,
    parse_event,
)
from producer import EventBusProducer, EventBusProducerError
from consumer import EventBusConsumer, ConsumerConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_PREFIX = os.getenv("STREAM_PREFIX", "edgecrew")
SERVICE_PORT = int(os.getenv("PORT", "8000"))
SERVICE_HOST = os.getenv("HOST", "0.0.0.0")

# Global instances
producer: Optional[EventBusProducer] = None
consumer: Optional[EventBusConsumer] = None
redis_client: Optional[redis.Redis] = None


# ============================================================================
# Pydantic Models for API
# ============================================================================

class PublishRequest(BaseModel):
    """Request to publish an event."""
    event_type: str = Field(..., description="Type of event to publish")
    data: Dict[str, Any] = Field(..., description="Event payload")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")


class PublishResponse(BaseModel):
    """Response from publishing an event."""
    message_id: str
    event_type: str
    status: str = "published"
    timestamp: str


class StreamInfo(BaseModel):
    """Information about a Redis stream."""
    name: str
    length: int
    groups: int
    last_generated_id: str


class ConsumerGroupInfo(BaseModel):
    """Information about a consumer group."""
    name: str
    consumers: int
    pending: int
    last_delivered_id: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    redis: str
    timestamp: str
    version: str = "3.0.0"


# ============================================================================
# Lifespan Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global producer, redis_client
    
    # Startup
    logger.info("Starting Event Bus Service...")
    
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    producer = EventBusProducer(redis_url=REDIS_URL, stream_prefix=STREAM_PREFIX)
    await producer.connect()
    
    logger.info("Event Bus Service started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Event Bus Service...")
    
    if producer:
        await producer.disconnect()
    if redis_client:
        await redis_client.close()
    
    logger.info("Event Bus Service stopped")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Edge Crew v3.0 Event Bus",
    description="Redis Streams-based event bus for inter-service communication",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health & Monitoring Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        await redis_client.ping()
        redis_status = "connected"
    except Exception as e:
        redis_status = f"disconnected: {e}"
    
    return HealthResponse(
        status="healthy" if redis_status == "connected" else "unhealthy",
        redis=redis_status,
        timestamp=datetime.utcnow().isoformat(),
    )


@app.get("/metrics")
async def get_metrics():
    """Get producer metrics."""
    return {
        "producer": await producer.get_metrics(),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# Publishing Endpoints
# ============================================================================

@app.post("/publish", response_model=PublishResponse)
async def publish_event(request: PublishRequest):
    """Publish an event to the bus."""
    try:
        message_id = await producer.publish(
            event_type=request.event_type,
            data=request.data,
            metadata=request.metadata,
        )
        
        return PublishResponse(
            message_id=message_id,
            event_type=request.event_type,
            status="published",
            timestamp=datetime.utcnow().isoformat(),
        )
    
    except EventBusProducerError as e:
        logger.error(f"Failed to publish event: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error publishing event: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/publish/batch")
async def publish_batch(events: List[PublishRequest]):
    """Publish multiple events in a batch."""
    batch = [
        {
            "event_type": e.event_type,
            "data": e.data,
            "metadata": e.metadata,
        }
        for e in events
    ]
    
    try:
        message_ids = await producer.publish_batch(batch)
        
        return {
            "published": len(message_ids),
            "message_ids": message_ids,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Failed to publish batch: {e}")
        raise HTTPException(status_code=503, detail=str(e))


# ============================================================================
# Stream Management Endpoints
# ============================================================================

@app.get("/streams")
async def list_streams():
    """List all event streams."""
    try:
        keys = await redis_client.keys(f"{STREAM_PREFIX}:*")
        
        streams = []
        for key in keys:
            if await redis_client.type(key) == "stream":
                info = await redis_client.xinfo_stream(key, full=False)
                streams.append({
                    "name": key,
                    "length": info.get("length", 0),
                    "groups": info.get("groups", 0),
                    "last_generated_id": info.get("last-generated-id", ""),
                })
        
        return streams
    
    except Exception as e:
        logger.error(f"Failed to list streams: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/event-types")
async def list_event_types():
    """List all supported event types."""
    return [
        {"event_type": et.value, "description": et.name}
        for et in EventType
    ]


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=SERVICE_HOST, port=SERVICE_PORT)
