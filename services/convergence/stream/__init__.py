"""
Streaming Module

Server-Sent Events (SSE) for real-time convergence updates.
"""

from .sse import SSEManager, StreamEvent, create_sse_stream

__all__ = ["SSEManager", "StreamEvent", "create_sse_stream"]
