"""
Edge Crew v3.0 - Health Check System
Comprehensive health monitoring for Render deployment and service dependencies
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import httpx

from app.core.config import security_settings
from app.database import get_db_manager
from app.cache import _redis_cache

logger = logging.getLogger("edge-crew-v3.health")


class HealthStatus:
    """Health status constants"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


async def check_database() -> Dict[str, Any]:
    """Check PostgreSQL database connectivity. Optional — app works without it."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        return {
            "status": HealthStatus.HEALTHY,
            "mode": "file_persistence",
            "note": "DATABASE_URL not set; using JSON file persistence",
        }
    
    try:
        db_manager = get_db_manager()
        is_healthy = db_manager.test_connection()
        return {
            "status": HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
            "connection_pool": {
                "active": db_manager.connection_metrics.get("active_connections", 0),
                "total": db_manager.connection_metrics.get("total_connections", 0),
                "errors": db_manager.connection_metrics.get("errors", 0),
            }
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": str(e),
        }


async def check_redis() -> Dict[str, Any]:
    """Check Redis connectivity"""
    try:
        if _redis_cache.redis_client is None:
            _redis_cache.connect()
        
        if _redis_cache.redis_client is None:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": "Redis client not initialized",
            }
        
        # Test with ping
        pong = _redis_cache.redis_client.ping()
        info = _redis_cache.redis_client.info()
        
        return {
            "status": HealthStatus.HEALTHY if pong else HealthStatus.UNHEALTHY,
            "memory": info.get("used_memory_human", "N/A"),
            "connected_clients": info.get("connected_clients", 0),
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": str(e),
        }


async def check_external_apis() -> Dict[str, Any]:
    """Check critical external API availability"""
    checks = {}
    
    # Check Odds API
    odds_api_key = os.environ.get("ODDS_API_KEY_PAID", "") or os.environ.get("ODDS_API_KEY", "")
    if odds_api_key:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.the-odds-api.com/v4/sports",
                    params={"apiKey": odds_api_key},
                )
                checks["odds_api"] = {
                    "status": HealthStatus.HEALTHY if resp.status_code == 200 else HealthStatus.DEGRADED,
                    "status_code": resp.status_code,
                }
        except Exception as e:
            checks["odds_api"] = {
                "status": HealthStatus.UNHEALTHY,
                "error": str(e),
            }
    else:
        checks["odds_api"] = {
            "status": HealthStatus.DEGRADED,
            "error": "ODDS_API_KEY not configured",
        }
    
    # Check ESPN API (lightweight endpoint)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
                params={"limit": 1},
            )
            checks["espn_api"] = {
                "status": HealthStatus.HEALTHY if resp.status_code == 200 else HealthStatus.DEGRADED,
                "status_code": resp.status_code,
            }
    except Exception as e:
        checks["espn_api"] = {
            "status": HealthStatus.UNHEALTHY,
            "error": str(e),
        }
    
    # Check Azure AI (if configured)
    azure_key = (
        os.environ.get("AZURE_OPENAI_KEY", "")
        or os.environ.get("AZURE_AI_KEY", "")
        or os.environ.get("AZURE_SWEDEN_KEY", "")
    )
    if azure_key:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                endpoint = (
                    os.environ.get("AZURE_OPENAI_ENDPOINT", "")
                    or os.environ.get("AZURE_AI_ENDPOINT", "")
                    or "https://pwgcerp-9302-resource.openai.azure.com/"
                )
                resp = await client.get(
                    endpoint,
                    headers={"api-key": azure_key},
                    timeout=5.0,
                )
                # Azure returns 404 on root but that's fine - means it's reachable
                checks["azure_ai"] = {
                    "status": HealthStatus.HEALTHY if resp.status_code in [200, 404] else HealthStatus.DEGRADED,
                    "status_code": resp.status_code,
                }
        except Exception as e:
            checks["azure_ai"] = {
                "status": HealthStatus.UNHEALTHY,
                "error": str(e),
            }
    else:
        checks["azure_ai"] = {
            "status": HealthStatus.DEGRADED,
            "error": "Azure AI key not configured (AZURE_OPENAI_KEY, AZURE_AI_KEY, or AZURE_SWEDEN_KEY)",
        }
    
    return checks


async def check_disk_space() -> Dict[str, Any]:
    """Check persistent disk availability"""
    try:
        persist_dir = "/data" if os.path.exists("/data") else "/tmp/ec8"
        
        # Use shutil for cross-platform disk usage
        import shutil
        total, used, free = shutil.disk_usage(persist_dir)
        
        free_gb = free / (1024 ** 3)
        usage_percent = (used / total) * 100
        
        status = HealthStatus.HEALTHY
        if usage_percent > 90:
            status = HealthStatus.UNHEALTHY
        elif usage_percent > 80:
            status = HealthStatus.DEGRADED
        
        return {
            "status": status,
            "path": persist_dir,
            "free_gb": round(free_gb, 2),
            "usage_percent": round(usage_percent, 1),
        }
    except Exception as e:
        logger.error(f"Disk space health check failed: {e}")
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": str(e),
        }


async def check_memory() -> Dict[str, Any]:
    """Check memory usage (important for Render 512MB tier)"""
    try:
        import psutil
        memory = psutil.virtual_memory()
        
        status = HealthStatus.HEALTHY
        if memory.percent > 95:
            status = HealthStatus.UNHEALTHY
        elif memory.percent > 85:
            status = HealthStatus.DEGRADED
        
        return {
            "status": status,
            "used_percent": memory.percent,
            "available_mb": round(memory.available / (1024 * 1024), 1),
            "total_mb": round(memory.total / (1024 * 1024), 1),
        }
    except ImportError:
        return {
            "status": HealthStatus.DEGRADED,
            "error": "psutil not installed",
        }
    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": str(e),
        }


async def run_health_checks() -> Dict[str, Any]:
    """Run all health checks and compute overall status"""
    start_time = datetime.now(timezone.utc)
    
    # Run checks concurrently
    results = await asyncio.gather(
        check_database(),
        check_redis(),
        check_external_apis(),
        check_disk_space(),
        check_memory(),
        return_exceptions=True,
    )
    
    db_result = results[0] if not isinstance(results[0], Exception) else {"status": HealthStatus.UNHEALTHY, "error": str(results[0])}
    redis_result = results[1] if not isinstance(results[1], Exception) else {"status": HealthStatus.UNHEALTHY, "error": str(results[1])}
    api_results = results[2] if not isinstance(results[2], Exception) else {"odds_api": {"status": HealthStatus.UNHEALTHY, "error": str(results[2])}}
    disk_result = results[3] if not isinstance(results[3], Exception) else {"status": HealthStatus.UNHEALTHY, "error": str(results[3])}
    memory_result = results[4] if not isinstance(results[4], Exception) else {"status": HealthStatus.UNHEALTHY, "error": str(results[4])}
    
    # Determine overall status
    # Database and disk are critical; Redis is optional (degraded if missing)
    all_statuses = [
        db_result["status"],
        disk_result["status"],
        memory_result["status"],
    ]
    
    # Redis is optional — app works fine without it
    if redis_result["status"] == HealthStatus.UNHEALTHY:
        all_statuses.append(HealthStatus.DEGRADED)
    else:
        all_statuses.append(redis_result["status"])
    
    # External APIs don't make the service unhealthy, just degraded
    for api_name, api_result in api_results.items():
        if api_result["status"] == HealthStatus.UNHEALTHY:
            all_statuses.append(HealthStatus.DEGRADED)
        else:
            all_statuses.append(api_result["status"])
    
    if HealthStatus.UNHEALTHY in all_statuses:
        overall_status = HealthStatus.UNHEALTHY
    elif HealthStatus.DEGRADED in all_statuses:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY
    
    end_time = datetime.now(timezone.utc)
    duration_ms = round((end_time - start_time).total_seconds() * 1000, 2)
    
    return {
        "status": overall_status,
        "version": "3.0.0",
        "time": end_time.isoformat(),
        "check_duration_ms": duration_ms,
        "environment": security_settings.environment,
        "checks": {
            "database": db_result,
            "redis": redis_result,
            "external_apis": api_results,
            "disk": disk_result,
            "memory": memory_result,
        },
    }


def get_liveness_check() -> Dict[str, Any]:
    """Simple liveness check for Kubernetes/Render load balancers"""
    return {
        "status": HealthStatus.HEALTHY,
        "time": datetime.now(timezone.utc).isoformat(),
    }


def get_readiness_check() -> Dict[str, Any]:
    """Readiness check - is the service ready to accept traffic?"""
    # Quick synchronous checks
    checks = {
        "status": HealthStatus.HEALTHY,
        "time": datetime.now(timezone.utc).isoformat(),
    }
    
    # Database is optional in Edge Crew — file persistence works without it
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if database_url:
        try:
            from app.database import _db_manager
            if _db_manager.engine is not None:
                checks["database_configured"] = True
            else:
                checks["database_configured"] = False
                checks["status"] = HealthStatus.UNHEALTHY
        except Exception:
            checks["database_configured"] = False
            checks["status"] = HealthStatus.UNHEALTHY
    else:
        checks["database_configured"] = False
        checks["mode"] = "file_persistence"
    
    return checks