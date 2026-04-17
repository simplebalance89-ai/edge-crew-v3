"""
Tests for security middleware components
"""

import os
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

# Set env vars before importing security modules
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters-long"
os.environ["DEBUG"] = "true"
os.environ["ALLOWED_ORIGINS"] = "https://test.example.com"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from app.middleware.security import setup_cors, validate_origin
from app.middleware.headers import SecurityHeadersMiddleware
import time
from app.middleware.rate_limit import RateLimiter
from app.core.validation import TeamQueryRequest, GradeRequest, contains_sql_injection, sanitize_xss


class TestCORSMiddleware:
    """Test CORS configuration"""

    def test_setup_cors_adds_middleware(self):
        app = FastAPI()
        setup_cors(app)
        
        # Check that CORS middleware was added
        cors_middlewares = [m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"]
        assert len(cors_middlewares) == 1
    
    def test_validate_origin_allows_localhost(self):
        assert validate_origin("http://localhost:3000") is True
    
    def test_validate_origin_allows_production(self):
        assert validate_origin("https://edge-crew-v3.onrender.com") is True
    
    def test_validate_origin_allows_custom(self):
        assert validate_origin("https://test.example.com") is True
    
    def test_validate_origin_blocks_evil(self):
        assert validate_origin("https://evil.com") is False


class TestSecurityHeadersMiddleware:
    """Test security headers"""

    def test_security_headers_present(self):
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/test")
        def test_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Strict-Transport-Security" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-Request-ID" in response.headers
        assert "Referrer-Policy" in response.headers
        assert "Permissions-Policy" in response.headers


class TestRateLimiter:
    """Test rate limiting"""

    def test_rate_limiter_allows_initial_requests(self):
        limiter = RateLimiter(requests=5, window=60)
        allowed, info = limiter.is_allowed("test-client")
        
        assert allowed is True
        assert info["limit"] == 5
        assert info["remaining"] >= 0
    
    @pytest.mark.skipif(
        RateLimiter(requests=3, window=60).redis_client is None,
        reason="Redis unavailable - skipping Redis-backed rate limit test"
    )
    def test_rate_limiter_tracks_multiple_requests(self):
        limiter = RateLimiter(requests=3, window=60)
        
        # Make requests up to the limit (using unique timestamps)
        for _ in range(3):
            allowed, info = limiter.is_allowed("test-client-track")
            assert allowed is True
            time.sleep(0.01)
        
        # Next request should be blocked
        allowed, info = limiter.is_allowed("test-client-track")
        assert allowed is False
        assert info["remaining"] == 0
    
    def test_rate_limiter_mock_redis_tracks_requests(self):
        """Test rate limiting logic with a mock Redis client"""
        limiter = RateLimiter(requests=3, window=60)
        
        class MockRedis:
            def __init__(self):
                self.data = {}
            
            def zremrangebyscore(self, key, min_score, max_score):
                if key in self.data:
                    self.data[key] = [(m, s) for m, s in self.data[key] if s > max_score]
            
            def zcard(self, key):
                return len(self.data.get(key, []))
            
            def zrange(self, key, start, end, withscores=False):
                items = self.data.get(key, [])
                return [(m, s) for m, s in items[start:end+1]]
            
            def zadd(self, key, mapping):
                if key not in self.data:
                    self.data[key] = []
                for member, score in mapping.items():
                    self.data[key].append((member, score))
            
            def expire(self, key, seconds):
                pass
        
        limiter.redis_client = MockRedis()
        
        # Make requests up to the limit
        for _ in range(3):
            allowed, info = limiter.is_allowed("mock-client")
            assert allowed is True
        
        # Next request should be blocked
        allowed, info = limiter.is_allowed("mock-client")
        assert allowed is False
        assert info["remaining"] == 0
    
    def test_rate_limiter_redis_unavailable_fallback(self):
        """Test that rate limiter gracefully falls back when Redis is unavailable"""
        limiter = RateLimiter(requests=3, window=60)
        
        # Force redis_client to None to simulate unavailable Redis
        limiter.redis_client = None
        
        allowed, info = limiter.is_allowed("test-client")
        assert allowed is True
        assert info["limit"] == 3
        assert info["remaining"] == 3


class TestInputValidation:
    """Test input validation and sanitization"""

    def test_sql_injection_detected(self):
        assert contains_sql_injection("SELECT * FROM users") is True
        assert contains_sql_injection("DROP TABLE users") is True
        assert contains_sql_injection("UNION SELECT password") is True
    
    def test_sql_injection_clean_input(self):
        assert contains_sql_injection("Los Angeles Lakers") is False
        assert contains_sql_injection("NBA") is False
    
    def test_xss_sanitization(self):
        sanitized = sanitize_xss("<script>alert('xss')</script>")
        assert "<script>" not in sanitized
        
        sanitized = sanitize_xss("<img src=x onerror=alert(1)>")
        assert "onerror" not in sanitized
    
    def test_team_query_request_valid(self):
        req = TeamQueryRequest(team_name="Lakers", sport="NBA")
        assert req.team_name == "Lakers"
        assert req.sport == "NBA"
    
    def test_team_query_request_invalid_sport(self):
        with pytest.raises(ValueError):
            TeamQueryRequest(team_name="Lakers", sport="INVALID")
    
    def test_grade_request_valid(self):
        req = GradeRequest(
            game_id="game123",
            sport="NBA",
            home_team="Lakers",
            away_team="Warriors",
            spread=5.5,
            ml_home=-200,
            ml_away=170
        )
        assert req.game_id == "game123"
        assert req.spread == 5.5
    
    def test_sql_injection_blocked_in_model(self):
        with pytest.raises(ValueError):
            TeamQueryRequest(team_name="SELECT * FROM users", sport="NBA")


class TestJWTAuth:
    """Test JWT authentication"""

    def test_create_and_decode_token(self):
        from app.middleware.auth import create_access_token, decode_token
        
        token = create_access_token({"sub": "user123", "role": "user"})
        assert token is not None
        
        payload = decode_token(token)
        assert payload["sub"] == "user123"
        assert payload["role"] == "user"
    
    def test_invalid_token_decode(self):
        from app.middleware.auth import decode_token
        
        payload = decode_token("invalid.token.here")
        assert payload is None
    
    def test_token_blacklisting(self):
        from app.middleware.auth import create_access_token, blacklist_token, _is_token_blacklisted
        
        token = create_access_token({"sub": "user123", "role": "user"})
        
        # Initially not blacklisted
        assert _is_token_blacklisted(token) is False
        
        # Blacklist the token
        result = blacklist_token(token, expires_minutes=1)
        
        # If Redis is available, token should be blacklisted
        # If Redis is unavailable, this will still return False
        if result:
            assert _is_token_blacklisted(token) is True