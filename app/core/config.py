"""
Edge Crew v3.0 - Security Configuration
Pydantic Settings for centralized security configuration
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator, SecretStr


class SecuritySettings(BaseSettings):
    """Security configuration with environment-based validation"""
    
    # JWT Configuration
    jwt_secret_key: SecretStr = SecretStr(os.getenv("JWT_SECRET_KEY", ""))
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_expire_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    jwt_refresh_token_expire_days: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    # Redis Configuration (for token blacklisting and rate limiting)
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379")
    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: Optional[str] = os.getenv("REDIS_PASSWORD")
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    
    # CORS Configuration
    allowed_origins: str = os.getenv("ALLOWED_ORIGINS", "")
    render_preview_url: Optional[str] = os.getenv("RENDER_EXTERNAL_URL")
    
    # Environment
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    environment: str = os.getenv("ENVIRONMENT", "production")
    
    # Rate Limiting
    rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    rate_limit_window: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    admin_rate_limit_requests: int = int(os.getenv("ADMIN_RATE_LIMIT_REQUESTS", "50"))
    
    # Security Headers
    hsts_max_age: int = int(os.getenv("HSTS_MAX_AGE", "31536000"))  # 1 year
    csp_report_only: bool = os.getenv("CSP_REPORT_ONLY", "false").lower() == "true"
    
    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: SecretStr) -> SecretStr:
        """Ensure JWT secret meets minimum security requirements"""
        secret = v.get_secret_value()
        if len(secret) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
        return v
    
    @property
    def cors_origins(self) -> List[str]:
        """Build CORS origin whitelist from environment"""
        origins = []
        
        # Development origins
        if self.debug or self.environment == "development":
            origins.extend([
                "http://localhost:3000",
                "http://localhost:5173",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:5173",
            ])
        
        # Production origins
        origins.extend([
            "https://edge-crew-v3.onrender.com",
            "https://www.edge-crew-v3.onrender.com",
        ])
        
        # Custom allowed origins from env
        if self.allowed_origins:
            custom_origins = [origin.strip() for origin in self.allowed_origins.split(",")]
            origins.extend(custom_origins)
        
        # Render preview URL
        if self.render_preview_url:
            origins.append(self.render_preview_url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_origins = []
        for origin in origins:
            if origin and origin not in seen:
                seen.add(origin)
                unique_origins.append(origin)
        
        return unique_origins
    
    @property
    def cors_methods(self) -> List[str]:
        """Allowed CORS methods"""
        return ["GET", "POST", "PUT", "DELETE"]
    
    @property
    def cors_headers(self) -> List[str]:
        """Allowed CORS headers"""
        return [
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-API-Key",
            "X-Forwarded-For",
        ]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production" and not self.debug


# Global security settings instance
security_settings = SecuritySettings()