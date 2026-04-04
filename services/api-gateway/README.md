# Edge Crew v3.0 API Gateway

A Kong-based API Gateway providing centralized authentication, rate limiting, request/response transformation, and routing for the Edge Crew microservices architecture.

## Architecture

```
                    +-------------------------------+
                    |     Edge Crew API Gateway     |
                    |            (Kong)             |
                    +-------------------------------+
                                    |
          +-----------+-----------+---------+----------+
          |           |           |         |          |
          v           v           v         v          v
   +----------+ +----------+ +----------+ +--------+ +--------+
   | Grading  | |    AI    | |Converge- | |  Data  | | Health |
   |  Engine  | |Processor | |  gence   | |Ingest  | | Checks |
   +----------+ +----------+ +----------+ +--------+ +--------+
```

## Features

- **Authentication**: JWT validation, API Key auth, OAuth2 introspection
- **Rate Limiting**: Redis-backed distributed rate limiting with per-user tiers
- **Request/Response Transformation**: Header manipulation, path rewriting
- **CORS**: Cross-origin resource sharing support
- **Monitoring**: Prometheus metrics and Grafana dashboards

## Quick Start

### Prerequisites

- Docker Desktop 4.0+
- Docker Compose v2.0+

### Start the Gateway

```bash
cd services/api-gateway
cp .env .env.local
docker-compose up -d
```

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| Kong Proxy | http://localhost:8000 | Main API endpoint |
| Kong Admin | http://localhost:8001 | Admin API |
| Grafana | http://localhost:3000 | Metrics dashboards |
| Prometheus | http://localhost:9090 | Metrics collection |

## API Routes

### Protected Routes

| Route | Service | Rate Limit |
|-------|---------|------------|
| POST /api/grade | grading-engine | 60/min |
| POST /api/ai/grade | ai-processor | 30/min |
| GET/POST /api/convergence | convergence | 100/min |
| GET/POST /api/picks | convergence | 100/min |
| GET /api/stream | convergence | 20/min |
| GET/POST /api/games | data-ingestion | 120/min |

### Health Check Routes (No Auth)

| Route | Service |
|-------|---------|
| GET /health | gateway |
| GET /health/grading-engine | grading-engine |
| GET /health/ai-processor | ai-processor |
| GET /health/convergence | convergence |
| GET /health/data-ingestion | data-ingestion |

## Authentication

### JWT Authentication

```bash
curl -H "Authorization: Bearer <jwt_token>" \
     http://localhost:8000/api/grade
```

### API Key Authentication

```bash
curl -H "X-API-Key: your-api-key" \
     http://localhost:8000/api/grade
```

## Project Structure

```
api-gateway/
├── kong.yml              # Kong declarative configuration
├── docker-compose.yml    # Local development setup
├── Dockerfile            # Kong with custom plugins
├── .env                  # Environment variables
├── plugins/
│   ├── auth.py           # JWT and API Key authentication
│   ├── rate_limiting.py  # Custom rate limiting
│   └── transform.py      # Request/response transformation
└── monitoring/
    ├── prometheus.yml    # Prometheus configuration
    └── grafana/          # Grafana dashboards
```

## Custom Plugins

### edge-auth

Handles JWT validation, API Key authentication, and RBAC.

Configuration:
- jwt_secret: Secret for H256 JWT verification
- jwt_public_key: Public key for RS256 verification
- api_key_header: Header name for API keys
- enforce_rbac: Enable role-based access control

### edge-rate-limiting

Advanced rate limiting with Redis backend and tiered limits.

Configuration:
- minute: Requests per minute
- hour: Requests per hour
- redis_host: Redis server hostname
- burst_multiplier: Allow burst traffic

### edge-transform

Request and response transformation.

Configuration:
- request_headers_add: Add request headers
- response_headers_add: Add response headers
- path_prefix_remove: Remove path prefix

## Development

### Testing Routes

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test with JWT (requires valid token)
curl -H "Authorization: Bearer test-token" \
     http://localhost:8000/api/grade

# Test rate limiting (should fail after limit exceeded)
for i in {1..65}; do
  curl -H "Authorization: Bearer test-token" \
       http://localhost:8000/api/grade
done
```

### View Logs

```bash
# Kong logs
docker-compose logs -f kong

# All services
docker-compose logs -f
```

### Reload Configuration

```bash
# Reload Kong without restart
docker-compose exec kong kong reload

# Full restart
docker-compose restart kong
```

## Production Deployment

1. Generate strong JWT secrets
2. Enable database mode (PostgreSQL)
3. Configure TLS/SSL certificates
4. Set up proper Redis clustering
5. Enable Kong Enterprise features
6. Configure log aggregation

See deployment documentation for details.

## License

Proprietary - Edge Crew Sports Analytics
