"""
Edge Crew v3.0 - Authentication Middleware
JWT validation with Redis token blacklisting
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import redis

from app.core.config import security_settings

logger = logging.getLogger("edge-crew-v3.auth")

# JWT Bearer scheme
security_bearer = HTTPBearer(auto_error=False)

# Redis client for token blacklisting
_redis_client: Optional[redis.Redis] = None


def _get_redis_client() -> Optional[redis.Redis]:
    """Get or create Redis client for token blacklisting"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    
    try:
        _redis_client = redis.Redis.from_url(
            security_settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        _redis_client.ping()
        logger.info("Redis auth client connected")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis auth client unavailable: {e}")
        return None


def _is_token_blacklisted(token: str) -> bool:
    """Check if a JWT token has been blacklisted (logged out)"""
    redis_client = _get_redis_client()
    if redis_client is None:
        # If Redis is unavailable, we can't verify blacklisting
        # In a high-security environment, you might want to fail closed
        logger.warning("Redis unavailable - cannot verify token blacklist")
        return False
    
    try:
        # Use token hash as key to avoid storing full tokens
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return redis_client.exists(f"token_blacklist:{token_hash}") > 0
    except Exception as e:
        logger.error(f"Token blacklist check failed: {e}")
        return False


def blacklist_token(token: str, expires_minutes: int = 60) -> bool:
    """Blacklist a JWT token (e.g., on logout)"""
    redis_client = _get_redis_client()
    if redis_client is None:
        logger.error("Cannot blacklist token - Redis unavailable")
        return False
    
    try:
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        redis_client.setex(f"token_blacklist:{token_hash}", expires_minutes * 60, "1")
        logger.info("Token blacklisted successfully")
        return True
    except Exception as e:
        logger.error(f"Token blacklisting failed: {e}")
        return False


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(
            token,
            security_settings.jwt_secret_key.get_secret_value(),
            algorithms=[security_settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        logger.debug(f"JWT decode failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected JWT error: {e}")
        return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> Dict[str, Any]:
    """
    FastAPI dependency to validate JWT and return current user.
    Attaches user_id and user_role to request.state.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = credentials.credentials
    
    # Check if token is blacklisted
    if _is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    
    # Decode token
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Extract user info
    user_id = payload.get("sub")
    user_role = payload.get("role", "user")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    # Check token expiration explicitly
    exp = payload.get("exp")
    if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token has expired")
    
    # Attach to request state for downstream use
    request.state.user_id = user_id
    request.state.user_role = user_role
    request.state.token = token
    
    user = {
        "user_id": user_id,
        "role": user_role,
        "email": payload.get("email"),
        "username": payload.get("username"),
    }
    
    logger.debug(f"Authenticated user: {user_id}, role: {user_role}")
    return user


def require_role(required_role: str):
    """
    Factory for role-based access control dependency.
    Usage: dependencies=[Depends(require_role("admin"))]
    """
    async def role_checker(
        request: Request,
        user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        user_role = user.get("role", "user")
        if user_role != required_role:
            logger.warning(f"Access denied: user {user['user_id']} has role {user_role}, required {required_role}")
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {required_role}"
            )
        return user
    return role_checker


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=security_settings.jwt_access_token_expire_minutes
        )
    
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "access"})
    
    encoded_jwt = jwt.encode(
        to_encode,
        security_settings.jwt_secret_key.get_secret_value(),
        algorithm=security_settings.jwt_algorithm,
    )
    return encoded_jwt