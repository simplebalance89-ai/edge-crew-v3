"""
Edge Crew v3.0 - Security Headers Middleware
Comprehensive security headers with HSTS, CSP, and X-Request-ID tracing
"""

import uuid
import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import security_settings

logger = logging.getLogger("edge-crew-v3.headers")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers and request tracing to all responses.
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Generate or propagate X-Request-ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response
        response.headers["X-Request-ID"] = request_id
        
        # Security Headers
        # HSTS - Force HTTPS for 1 year
        response.headers["Strict-Transport-Security"] = (
            f"max-age={security_settings.hsts_max_age}; includeSubDomains; preload"
        )
        
        # X-Frame-Options - Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # X-Content-Type-Options - Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Referrer-Policy - Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions-Policy - Disable unnecessary browser features
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "accelerometer=(), gyroscope=(), magnetometer=(), "
            "payment=(), usb=(), bluetooth=()"
        )
        
        # X-XSS-Protection - Legacy XSS protection (defense in depth)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Content-Security-Policy
        csp_directive = "Content-Security-Policy-Report-Only" if security_settings.csp_report_only else "Content-Security-Policy"
        
        # CSP adjusted for React frontend
        csp_value = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://api.the-odds-api.com https://site.api.espn.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers[csp_directive] = csp_value
        
        # Cache-Control for API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response


def get_request_id(request: Request) -> str:
    """Get the current request ID from request state"""
    return getattr(request.state, "request_id", "unknown")


def get_client_ip(request: Request) -> str:
    """Get real client IP from behind Render proxy"""
    # Render sets X-Forwarded-For with the real client IP
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: client, proxy1, proxy2
        # The first IP is the real client
        return forwarded_for.split(",")[0].strip()
    
    # Fallback to X-Real-IP or direct connection
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"