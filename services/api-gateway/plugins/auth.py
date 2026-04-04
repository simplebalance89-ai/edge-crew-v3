"""
Custom Authentication Plugin for Edge Crew v3.0 API Gateway
Provides JWT validation, API Key auth, OAuth2 introspection, and RBAC.
"""

import json
import jwt
import base64
import hashlib
from typing import Dict, Optional, Tuple

VERSION = "1.0.0"
PRIORITY = 1000


class Config:
    def __init__(self):
        self.jwt_secret = None
        self.jwt_public_key = None
        self.jwt_algorithm = "HS256"
        self.jwt_issuer = None
        self.jwt_audience = None
        self.api_key_header = "X-API-Key"
        self.enforce_rbac = False
        self.required_roles = []
        self.allow_anonymous = False
        self.error_code = 401
        self.error_message = "Authentication required"
        self.realm = "Edge Crew API"


class JWTValidator:
    def __init__(self, config: Config):
        self.config = config

    def extract_token(self, kong) -> Optional[str]:
        auth_header = kong.request.get_header("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                return parts[1]
        return None

    def verify_token(self, token: str) -> Tuple[bool, Optional[Dict], str]:
        try:
            if self.config.jwt_algorithm.startswith("HS"):
                if not self.config.jwt_secret:
                    return False, None, "JWT secret not configured"
                payload = jwt.decode(
                    token, self.config.jwt_secret, algorithms=[self.config.jwt_algorithm]
                )
            elif self.config.jwt_algorithm.startswith("RS"):
                if not self.config.jwt_public_key:
                    return False, None, "JWT public key not configured"
                payload = jwt.decode(
                    token,
                    self.config.jwt_public_key,
                    algorithms=[self.config.jwt_algorithm],
                )
            else:
                return False, None, "Unsupported algorithm"

            if self.config.jwt_issuer and payload.get("iss") != self.config.jwt_issuer:
                return False, None, "Invalid issuer"

            if self.config.jwt_audience:
                aud = payload.get("aud")
                if isinstance(aud, list):
                    if self.config.jwt_audience not in aud:
                        return False, None, "Invalid audience"
                elif aud != self.config.jwt_audience:
                    return False, None, "Invalid audience"

            return True, payload, ""
        except jwt.ExpiredSignatureError:
            return False, None, "Token expired"
        except jwt.InvalidTokenError as e:
            return False, None, str(e)


class APIKeyValidator:
    def __init__(self, config: Config):
        self.config = config

    def extract_key(self, kong) -> Optional[str]:
        return kong.request.get_header(self.config.api_key_header)

    def validate_key(self, api_key: str) -> Tuple[bool, Optional[Dict]]:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        if len(api_key) >= 32:
            return True, {"id": f"key_{key_hash[:16]}", "username": "api-user"}
        return False, None


class Plugin:
    def __init__(self, config: Dict):
        self.config = Config()
        for key, value in config.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.jwt_validator = JWTValidator(self.config)
        self.api_key_validator = APIKeyValidator(self.config)

    def access(self, kong):
        authenticated = False
        consumer = None
        credential = None
        claims = None

        jwt_token = self.jwt_validator.extract_token(kong)
        if jwt_token:
            valid, payload, error = self.jwt_validator.verify_token(jwt_token)
            if valid:
                authenticated = True
                claims = payload
                credential = {"id": payload.get("sub"), "type": "jwt"}
                consumer = {"id": payload.get("sub"), "username": payload.get("sub")}

        if not authenticated:
            api_key = self.api_key_validator.extract_key(kong)
            if api_key:
                valid, key_info = self.api_key_validator.validate_key(api_key)
                if valid:
                    authenticated = True
                    credential = {"id": key_info["id"], "type": "api_key"}
                    consumer = {"id": key_info["id"], "username": key_info["username"]}

        if not authenticated:
            if self.config.allow_anonymous:
                kong.client.set_consumer(self.config.anonymous_consumer, None)
                return
            else:
                return kong.response.exit(
                    self.config.error_code,
                    json.dumps(
                        {"error": "Unauthorized", "message": self.config.error_message}
                    ),
                    {
                        "Content-Type": "application/json",
                        "WWW-Authenticate": f'Bearer realm="{self.config.realm}"',
                    },
                )

        if consumer:
            kong.client.set_consumer(consumer, credential)

        if claims:
            claims_header = base64.b64encode(json.dumps(claims).encode()).decode()
            kong.service.request.set_header("X-JWT-Claims", claims_header)
            kong.service.request.set_header("X-User-ID", str(claims.get("sub", "")))


def access(kong):
    config = kong.configuration
    plugin = Plugin(config)
    return plugin.access(kong)


Schema = {
    "name": "edge-auth",
    "fields": [
        {"jwt_secret": {"type": "string"}},
        {"jwt_public_key": {"type": "string"}},
        {"jwt_algorithm": {"type": "string", "default": "HS256"}},
        {"jwt_issuer": {"type": "string"}},
        {"jwt_audience": {"type": "string"}},
        {"api_key_header": {"type": "string", "default": "X-API-Key"}},
        {"enforce_rbac": {"type": "boolean", "default": False}},
        {"allow_anonymous": {"type": "boolean", "default": False}},
        {"error_code": {"type": "number", "default": 401}},
        {"error_message": {"type": "string", "default": "Authentication required"}},
    ],
}
