"""Edge Crew v3.0 Data Ingestion Service - FastAPI app with scheduled jobs."""
import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional

import aio_pika
import orjson
import redis.asyncio as redis
import structlog
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from models import BaseEvent, DataSource, HealthCheck, Priority, Sport
from scheduler import SmartScheduler
from ingesters import BaseIngester, OddsAPIIngester, ESPNIngester, RotowireIngester, KalshiIngester

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

EVENTS_INGESTED = Counter("data_ingestion_events_total", "Total events ingested", ["source", "sport", "event_type"])
FETCH_DURATION = Histogram("data_ingestion_fetch_duration_seconds", "Fetch duration", ["source", "sport"])
FETCH_ERRORS = Counter("data_ingestion_fetch_errors_total", "Total fetch errors", ["source", "sport", "error_type"])

scheduler: SmartScheduler
ingesters: dict[DataSource, BaseIngester] = {}
redis_client: Optional[redis.Redis] = None
rabbitmq_connection: Optional[aio_pika.Connection] = None
rabbitmq_channel: Optional[aio_pika.Channel] = None


class Settings:
    ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
    ROTOWIRE_API_KEY = os.getenv("ROTOWIRE_API_KEY", "")
    KALSHI_API_KEY = os.getenv("KALSHI_API_KEY", "")
    KALSHI_API_SECRET = os.getenv("KALSHI_API_SECRET", "")
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    EVENT_EXCHANGE = os.getenv("EVENT_EXCHANGE", "edge-crew-events")
    EVENT_QUEUE = os.getenv("EVENT_QUEUE", "data-ingestion-events")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_ODDS_API = os.getenv("ENABLE_ODDS_API", "true").lower() == "true"
    ENABLE_ESPN = os.getenv("ENABLE_ESPN", "true").lower() == "true"
    ENABLE_ROTOWIRE = os.getenv("ENABLE_ROTOWIRE", "true").lower() == "true"
    ENABLE_KALSHI = os.getenv("ENABLE_KALSHI", "true").lower() == "true"


settings = Settings()


async def init_ingesters():
    global ingesters
    if settings.ENABLE_ODDS_API and settings.ODDS_API_KEY:
        ingesters[DataSource.ODDS_API] = OddsAPIIngester(settings.ODDS_API_KEY)
    if settings.ENABLE_ESPN:
        ingesters[DataSource.ESPN] = ESPNIngester()
    if settings.ENABLE_ROTOWIRE and settings.ROTOWIRE_API_KEY:
        ingesters[DataSource.ROTOWIRE] = RotowireIngester(settings.ROTOWIRE_API_KEY)
    if settings.ENABLE_KALSHI and settings.KALSHI_API_KEY:
        ingesters[DataSource.KALSHI] = KalshiIngester(settings.KALSHI_API_KEY, settings.KALSHI_API_SECRET)
    for source, ingester in ingesters.items():
        await ingester.start()
        logger.info("ingester.initialized", source=source.value)


async def init_scheduler():
    global scheduler
    scheduler = SmartScheduler()
    for source, ingester in ingesters.items():
        scheduler.register_callback(source, create_fetch_callback(ingester))
    await scheduler.start()
    logger.info("scheduler.initialized")


def create_fetch_callback(ingester: BaseIngester):
    async def callback(sport: Sport, priority: Priority):
        with FETCH_DURATION.labels(source=ingester.source.value, sport=sport.value).time():
            try:
                events = await ingester.fetch(sport, priority)
                for event in events:
                    await publish_event(event)
                    EVENTS_INGESTED.labels(source=ingester.source.value, sport=sport.value, event_type=event.event_type.value).inc()
                logger.info("fetch.completed", source=ingester.source.value, sport=sport.value, event_count=len(events))
            except Exception as e:
                FETCH_ERRORS.labels(source=ingester.source.value, sport=sport.value, error_type=type(e).__name__).inc()
                logger.error("fetch.failed", source=ingester.source.value, sport=sport.value, error=str(e))
    return callback


async def init_redis():
    global redis_client
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        logger.info("redis.connected")
    except Exception as e:
        logger.error("redis.connection_failed", error=str(e))
        redis_client = None


async def init_rabbitmq():
    global rabbitmq_connection, rabbitmq_channel
    try:
        rabbitmq_connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        rabbitmq_channel = await rabbitmq_connection.channel()
        exchange = await rabbitmq_channel.declare_exchange(settings.EVENT_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await rabbitmq_channel.declare_queue(settings.EVENT_QUEUE, durable=True)
        for source in DataSource:
            await queue.bind(exchange, routing_key=f"{source.value}.*")
        logger.info("rabbitmq.connected")
    except Exception as e:
        logger.error("rabbitmq.connection_failed", error=str(e))


async def publish_event(event: BaseEvent):
    if not rabbitmq_channel:
        logger.warning("rabbitmq.not_connected", event_id=str(event.event_id))
        return
    try:
        message = aio_pika.Message(
            body=orjson.dumps(event.model_dump(mode="json")),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        routing_key = f"{event.source.value}.{event.sport.value}"
        await rabbitmq_channel.default_exchange.publish(message, routing_key=routing_key)
    except Exception as e:
        logger.error("event.publish_failed", event_id=str(event.event_id), error=str(e))


async def shutdown():
    logger.info("service.shutting_down")
    if scheduler:
        await scheduler.stop()
    for ingester in ingesters.values():
        await ingester.stop()
    if redis_client:
        await redis_client.close()
    if rabbitmq_connection:
        await rabbitmq_connection.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_ingesters()
    await init_redis()
    await init_rabbitmq()
    await init_scheduler()
    logger.info("service.started")
    yield
    await shutdown()


app = FastAPI(
    title="Edge Crew Data Ingestion Service",
    version="3.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check() -> HealthCheck:
    sources = {source: ingester.get_status() for source, ingester in ingesters.items()}
    queue_depth = 0
    try:
        if redis_client:
            queue_depth = await redis_client.llen("event_queue")
    except:
        pass
    return HealthCheck(
        status="healthy" if all(s.is_healthy for s in sources.values()) else "degraded",
        sources=sources,
        queue_depth=queue_depth,
        active_jobs=len(asyncio.all_tasks())
    )


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/scheduler/status")
async def scheduler_status():
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    breakdowns = {sport.value: scheduler.get_sport_priority_breakdown(sport) for sport in Sport}
    next_fetches = scheduler.get_next_fetch_times()
    return {"sport_breakdowns": breakdowns, "next_fetch_times": next_fetches}


@app.post("/scheduler/update-games")
async def update_games(games: list[GameInfo]):
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    scheduler.update_games(games)
    return {"updated": len(games)}


@app.post("/fetch/{source}/{sport}")
async def manual_fetch(source: DataSource, sport: Sport, priority: Priority = Priority.HIGH):
    if source not in ingesters:
        raise HTTPException(status_code=404, detail=f"Ingester {source} not found")
    ingester = ingesters[source]
    events = await ingester.fetch(sport, priority)
    for event in events:
        await publish_event(event)
    return {"source": source.value, "sport": sport.value, "events_fetched": len(events)}


@app.get("/sources/{source}/status")
async def source_status(source: DataSource):
    if source not in ingesters:
        raise HTTPException(status_code=404, detail=f"Ingester {source} not found")
    return ingesters[source].get_status()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
