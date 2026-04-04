"""
Server-Sent Events (SSE) for Real-Time Streaming

Provides real-time updates for convergence results, pick generation,
and portfolio changes via Server-Sent Events.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Callable, Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import uuid

from models import Convergence, Pick, Portfolio, StreamEvent

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """Event for SSE streaming."""
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = None
    id: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.id is None:
            self.id = str(uuid.uuid4())
    
    def to_sse_format(self) -> str:
        """Convert to SSE format."""
        lines = [
            f"id: {self.id}",
            f"event: {self.event_type}",
            f"data: {json.dumps(self.data, default=self._json_serializer)}",
            ""  # Empty line to end event
        ]
        return "\n".join(lines)
    
    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for non-serializable objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class SSEManager:
    """
    Manager for Server-Sent Events streams.
    
    Handles multiple client connections, event broadcasting,
    and stream lifecycle management.
    """
    
    def __init__(self):
        self._clients: Dict[str, asyncio.Queue] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._running = True
        logger.info("SSEManager initialized")
    
    async def subscribe(self, client_id: Optional[str] = None) -> str:
        """
        Subscribe a new client to the event stream.
        
        Args:
            client_id: Optional client identifier (auto-generated if not provided)
            
        Returns:
            Client ID for the subscription
        """
        if client_id is None:
            client_id = str(uuid.uuid4())
        
        queue = asyncio.Queue(maxsize=100)
        self._clients[client_id] = queue
        
        logger.info(f"Client {client_id} subscribed to SSE stream")
        
        # Send initial connection event
        await self.send_to_client(
            client_id,
            StreamEvent(
                event_type="connected",
                data={"client_id": client_id, "status": "connected"}
            )
        )
        
        return client_id
    
    async def unsubscribe(self, client_id: str):
        """Unsubscribe a client from the event stream."""
        if client_id in self._clients:
            del self._clients[client_id]
            logger.info(f"Client {client_id} unsubscribed from SSE stream")
    
    async def send_to_client(self, client_id: str, event: StreamEvent):
        """Send an event to a specific client."""
        if client_id not in self._clients:
            return
        
        try:
            queue = self._clients[client_id]
            await asyncio.wait_for(queue.put(event), timeout=1.0)
        except asyncio.TimeoutError:
            logger.warning(f"Queue full for client {client_id}, dropping event")
        except Exception as e:
            logger.error(f"Error sending to client {client_id}: {e}")
    
    async def broadcast(self, event: StreamEvent):
        """Broadcast an event to all connected clients."""
        tasks = []
        for client_id in list(self._clients.keys()):
            tasks.append(self.send_to_client(client_id, event))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def event_stream(self, client_id: str) -> AsyncGenerator[str, None]:
        """
        Generate SSE stream for a client.
        
        Yields SSE-formatted strings for HTTP streaming response.
        """
        if client_id not in self._clients:
            raise ValueError(f"Client {client_id} not subscribed")
        
        queue = self._clients[client_id]
        
        try:
            while self._running:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event.to_sse_format()
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield ":heartbeat\n\n"
        except asyncio.CancelledError:
            logger.info(f"Event stream cancelled for client {client_id}")
            raise
        except Exception as e:
            logger.error(f"Error in event stream for {client_id}: {e}")
            raise
        finally:
            await self.unsubscribe(client_id)
    
    # Convenience methods for specific event types
    
    async def emit_convergence(self, convergence: Convergence):
        """Emit a convergence result event."""
        event = StreamEvent(
            event_type="convergence",
            data={
                "id": str(convergence.id),
                "game_id": convergence.game_id,
                "sport": convergence.sport.value,
                "selection": convergence.selection,
                "score": convergence.score,
                "status": convergence.status.value,
                "confidence": convergence.confidence,
                "edge": convergence.edge_percent,
                "delta": convergence.delta,
                "variance": convergence.variance,
                "timestamp": convergence.timestamp.isoformat()
            }
        )
        await self.broadcast(event)
    
    async def emit_pick(self, pick: Pick):
        """Emit a pick generated event."""
        event = StreamEvent(
            event_type="pick",
            data={
                "id": str(pick.id),
                "game_id": pick.game_id,
                "sport": pick.sport.value,
                "selection": pick.selection,
                "odds": pick.odds,
                "line": pick.line,
                "convergence_score": pick.convergence_score,
                "confidence": pick.confidence,
                "edge": pick.edge_percent,
                "kelly_fraction": pick.kelly_fraction,
                "recommended_units": pick.recommended_units,
                "expected_value": pick.expected_value,
                "timestamp": pick.timestamp.isoformat()
            }
        )
        await self.broadcast(event)
    
    async def emit_portfolio(self, portfolio: Portfolio):
        """Emit a portfolio update event."""
        event = StreamEvent(
            event_type="portfolio",
            data={
                "id": str(portfolio.id),
                "num_positions": portfolio.num_positions,
                "total_allocation": portfolio.total_allocation,
                "expected_return": portfolio.expected_return,
                "expected_variance": portfolio.expected_variance,
                "sharpe_ratio": portfolio.sharpe_ratio,
                "var_95": portfolio.var_95,
                "is_balanced": portfolio.is_balanced,
                "picks": [{"id": str(p.id), "selection": p.selection} for p in portfolio.picks],
                "timestamp": portfolio.date.isoformat()
            }
        )
        await self.broadcast(event)
    
    async def emit_status(self, status: str, message: str = ""):
        """Emit a status update event."""
        event = StreamEvent(
            event_type="status",
            data={
                "status": status,
                "message": message,
                "active_clients": len(self._clients)
            }
        )
        await self.broadcast(event)
    
    async def emit_error(self, error: str, details: Optional[Dict] = None):
        """Emit an error event."""
        event = StreamEvent(
            event_type="error",
            data={
                "error": error,
                "details": details or {}
            }
        )
        await self.broadcast(event)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current streaming statistics."""
        return {
            "active_clients": len(self._clients),
            "client_ids": list(self._clients.keys())
        }
    
    async def shutdown(self):
        """Shutdown the SSE manager and clean up."""
        self._running = False
        
        # Notify all clients
        await self.emit_status("shutdown", "Server is shutting down")
        
        # Clear clients
        self._clients.clear()
        logger.info("SSEManager shutdown complete")


# Global SSE manager instance
_sse_manager: Optional[SSEManager] = None


def get_sse_manager() -> SSEManager:
    """Get or create the global SSE manager."""
    global _sse_manager
    if _sse_manager is None:
        _sse_manager = SSEManager()
    return _sse_manager


async def create_sse_stream(
    event_generator: Callable[[], AsyncGenerator[Dict, None]],
    event_type: str = "update"
) -> AsyncGenerator[str, None]:
    """
    Create an SSE stream from an async generator.
    
    Args:
        event_generator: Async generator yielding event data dicts
        event_type: Type of events being streamed
        
    Yields:
        SSE-formatted strings
    """
    try:
        async for data in event_generator():
            event = StreamEvent(event_type=event_type, data=data)
            yield event.to_sse_format()
    except Exception as e:
        logger.error(f"Error in SSE stream: {e}")
        error_event = StreamEvent(
            event_type="error",
            data={"message": str(e)}
        )
        yield error_event.to_sse_format()
