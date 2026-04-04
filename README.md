# Edge Crew v3.0

> Real-time sports analytics and betting intelligence platform

## Overview

Edge Crew v3.0 is a modern, microservices-based platform for sports analytics and betting intelligence.

## Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Make (optional)

### Setup

```bash
# Clone repository
git clone <repository-url>
cd edge-crew-v3

# Copy environment template
cp .env.example .env

# Start all services
docker-compose up -d
```

### Access Services

| Service | URL |
|---------|-----|
| Web UI | http://localhost:3000 |
| API Gateway | http://localhost:8000 |

## Architecture

```
Web UI (3000) --> API Gateway (8000) --> Services
                              |--> Data Ingestion
                              |--> Grading Engine
                              |--> AI Processor
                              |--> Convergence
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| web | 3000 | Next.js frontend |
| api-gateway | 8000 | API entry point |
| data-ingestion | 8080 | Sports data ingestion |
| grading-engine | 8080 | Prediction grading |
| ai-processor | 8080 | ML inference |
| convergence | 8080 | Data aggregation |
| postgres | 5432 | TimescaleDB |
| redis | 6379 | Cache & queue |

## Make Commands

```bash
make up          # Start all services
make down        # Stop all services
make build       # Build images
make logs        # View logs
make test        # Run tests
make migrate     # Run migrations
make seed        # Seed database
make db-shell    # PostgreSQL shell
make redis-cli   # Redis CLI
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description |
|----------|-------------|
| AZURE_SWEDEN_KEY | Azure AI key |
| JWT_SECRET | JWT signing secret |
| LOG_LEVEL | Logging level |

## Development

Hot-reload is enabled for all services via `docker-compose.override.yml`.

## API Documentation

API docs available at http://localhost:8000/docs

## License

MIT
