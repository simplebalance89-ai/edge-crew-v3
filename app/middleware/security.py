"""
Edge Crew v3.0 - Security Middleware
CORS setup with strict origin validation and Render optimization
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import security_settings

logger = logging.getLogger("edge-crew-v3.security")


def setup_cors(app: FastAPI) -> None:
    """
    Configure CORS with strict origin validation.
    Supports localhost for dev and edge-crew-v3.onrender.com for prod.
    Also supports RENDER_PREVIEW_URL env injection.
    """
    origins = security_settings.cors_origins
    methods = security_settings.cors_methods
    headers = security_settings.cors_headers
    
    logger.info(f"CORS configured with {len(origins)} allowed origins")
    logger.debug(f"CORS origins: {origins}")
    logger.debug(f"CORS methods: {methods}")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,  # Required for JWT cookies
        allow_methods=methods,
        allow_headers=headers,
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=3600,
    )


def validate_origin(origin: str) -> bool:
    """Validate if an origin is in the allowed whitelist"""
    allowed = security_settings.cors_origins
    return origin in allowed


def get_cors_origins() -> list:
    """Get current CORS origin whitelist"""
    return security_settings.cors_origins.copy()