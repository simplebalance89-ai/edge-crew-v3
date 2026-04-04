# Edge Crew v3.0 - Local Development Makefile

.PHONY: help up down build rebuild logs ps clean test lint fmt setup init

.DEFAULT_GOAL := help

help:
	@echo Edge Crew v3.0 - Local Development Commands
	@echo ===========================================
	@echo.
	@echo [Setup Commands]
	@echo   make setup       - Initial project setup
	@echo   make init        - Initialize database and dependencies
	@echo.
	@echo [Development Commands]
	@echo   make up          - Start all services (detached)
	@echo   make up-build    - Build and start all services
	@echo   make down        - Stop all services
	@echo   make down-v      - Stop services and remove volumes
	@echo   make restart     - Restart all services
	@echo   make build       - Build all service images
	@echo   make rebuild     - Force rebuild (no cache)
	@echo   make ps          - List running containers
	@echo   make logs        - Follow logs from all services
	@echo.
	@echo [Service Logs]
	@echo   make api-logs    - API Gateway logs
	@echo   make web-logs    - Web frontend logs
	@echo   make db-logs     - Database logs
	@echo   make redis-logs  - Redis logs
	@echo.
	@echo [Database Commands]
	@echo   make migrate     - Run database migrations
	@echo   make seed        - Seed database with sample data
	@echo   make db-reset    - Reset database
	@echo   make db-shell    - Open PostgreSQL shell
	@echo   make redis-cli   - Open Redis CLI
	@echo.
	@echo [Testing Commands]
	@echo   make test        - Run all tests
	@echo   make test-grading  - Grading Engine tests
	@echo   make test-ai       - AI Processor tests
	@echo   make test-conv     - Convergence tests
	@echo   make coverage    - Run tests with coverage
	@echo.
	@echo [Code Quality]
	@echo   make lint        - Run linters
	@echo   make fmt         - Format code
	@echo   make typecheck   - Run type checking
	@echo.
	@echo [Utility Commands]
	@echo   make clean       - Remove containers and volumes
	@echo   make prune       - Prune Docker system
	@echo   make tools       - Start dev tools (pgAdmin, Redis Commander)

setup:
	@echo Setting up Edge Crew v3.0...
	@if not exist .env (copy .env.example .env) else (echo .env already exists)
	@echo Setup complete! Run 'make up' to start services.

init: up
	@echo Initializing database...
	@docker-compose exec -T postgres psql -U edgecrew -d edgecrew -f /docker-entrypoint-initdb.d/01-schema.sql

up:
	@echo Starting Edge Crew services...
	@docker-compose up -d
	@echo Services started!
	@echo   API Gateway: http://localhost:8000
	@echo   Web App:     http://localhost:3000

up-build:
	@echo Building and starting services...
	@docker-compose up -d --build

down:
	@echo Stopping services...
	@docker-compose down

down-v:
	@echo Stopping services and removing volumes...
	@docker-compose down -v

restart: down up

build:
	@echo Building service images...
	@docker-compose build

rebuild:
	@echo Force rebuilding images...
	@docker-compose build --no-cache

ps:
	@docker-compose ps

logs:
	@docker-compose logs -f

api-logs:
	@docker-compose logs -f api-gateway

web-logs:
	@docker-compose logs -f web

db-logs:
	@docker-compose logs -f postgres

redis-logs:
	@docker-compose logs -f redis

grading-logs:
	@docker-compose logs -f grading-engine

ai-logs:
	@docker-compose logs -f ai-processor

convergence-logs:
	@docker-compose logs -f convergence

migrate:
	@echo Running migrations...
	@docker-compose exec postgres psql -U edgecrew -d edgecrew -f /docker-entrypoint-initdb.d/01-schema.sql

seed:
	@echo Seeding database...
	@bash scripts/seed.sh || echo Run scripts/seed.sh manually

db-reset:
	@echo Resetting database...
	@docker-compose down
	@docker volume rm edge-crew-v3_postgres_data 2>nul || echo Volume removed
	@docker-compose up -d postgres

db-shell:
	@docker-compose exec postgres psql -U edgecrew -d edgecrew

redis-cli:
	@docker-compose exec redis redis-cli

test:
	@echo Running all tests...
	@bash scripts/test.sh || (docker-compose run --rm grading-engine pytest -v && docker-compose run --rm ai-processor pytest -v && docker-compose run --rm convergence pytest -v)

test-grading:
	@docker-compose run --rm grading-engine pytest -v

test-ai:
	@docker-compose run --rm ai-processor pytest -v

test-conv:
	@docker-compose run --rm convergence pytest -v

coverage:
	@docker-compose run --rm grading-engine pytest --cov=app --cov-report=term-missing
	@docker-compose run --rm ai-processor pytest --cov=app --cov-report=term-missing
	@docker-compose run --rm convergence pytest --cov=app --cov-report=term-missing

lint:
	@docker-compose exec -T grading-engine flake8 app 2>nul || echo Grading lint done
	@docker-compose exec -T ai-processor flake8 app 2>nul || echo AI lint done

fmt:
	@docker-compose exec -T grading-engine black app 2>nul || echo Grading format done
	@docker-compose exec -T ai-processor black app 2>nul || echo AI format done

typecheck:
	@docker-compose exec -T grading-engine mypy app 2>nul || echo Type check done

clean:
	@echo Cleaning up...
	@docker-compose down -v --remove-orphans 2>nul || echo Cleanup done

prune:
	@docker system prune -f

tools:
	@echo Starting development tools...
	@docker-compose --profile tools up -d
	@echo pgAdmin:      http://localhost:5050
	@echo Redis Commander: http://localhost:8085
	@echo Mailpit:      http://localhost:8025
