#!/bin/bash
# Edge Crew v3.0 - Initial Setup Script
# Usage: ./scripts/setup.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Edge Crew v3.0 - Setup Script            ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if running in the correct directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found.${NC}"
    echo -e "${YELLOW}Please run this script from the project root directory.${NC}"
    exit 1
fi

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo -e "${YELLOW}Please install Docker: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed.${NC}"
    echo -e "${YELLOW}Please install Docker Compose: https://docs.docker.com/compose/install/${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"

# Check .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}NOTE: Please edit .env and add your API keys${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Create necessary directories
echo -e "${BLUE}Creating project directories...${NC}"
mkdir -p infrastructure/db/migrations
mkdir -p infrastructure/db/seeds
mkdir -p infrastructure/db/functions
mkdir -p logs
echo -e "${GREEN}✓ Directories created${NC}"

# Pull base images
echo -e "${BLUE}Pulling Docker base images...${NC}"
docker-compose pull postgres redis 2>/dev/null || docker compose pull postgres redis
echo -e "${GREEN}✓ Base images pulled${NC}"

# Build service images
echo -e "${BLUE}Building service images...${NC}"
docker-compose build 2>/dev/null || docker compose build
echo -e "${GREEN}✓ Service images built${NC}"

# Start infrastructure services
echo -e "${BLUE}Starting infrastructure services (PostgreSQL, Redis)...${NC}"
docker-compose up -d postgres redis 2>/dev/null || docker compose up -d postgres redis

# Wait for PostgreSQL to be ready
echo -e "${BLUE}Waiting for PostgreSQL to be ready...${NC}"
attempt=0
max_attempts=30
until docker-compose exec -T postgres pg_isready -U edgecrew 2>/dev/null || [ $attempt -eq $max_attempts ]; do
    attempt=$((attempt+1))
    echo -n "."
    sleep 2
done
echo ""

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}Error: PostgreSQL did not become ready in time${NC}"
    exit 1
fi

echo -e "${GREEN}✓ PostgreSQL is ready${NC}"

# Initialize database schema
echo -e "${BLUE}Initializing database schema...${NC}"
if [ -f "infrastructure/db/schema.sql" ]; then
    docker-compose exec -T postgres psql -U edgecrew -d edgecrew -f /docker-entrypoint-initdb.d/01-schema.sql 2>/dev/null || \
        docker compose exec -T postgres psql -U edgecrew -d edgecrew -f /docker-entrypoint-initdb.d/01-schema.sql
    echo -e "${GREEN}✓ Database schema initialized${NC}"
else
    echo -e "${YELLOW}⚠ schema.sql not found, skipping schema initialization${NC}"
fi

# Stop infrastructure services
echo -e "${BLUE}Stopping infrastructure services...${NC}"
docker-compose down 2>/dev/null || docker compose down
echo -e "${GREEN}✓ Setup complete!${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   Setup completed successfully!            ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Edit ${YELLOW}.env${NC} file and add your API keys"
echo -e "  2. Run ${YELLOW}make up${NC} or ${YELLOW}docker-compose up -d${NC} to start all services"
echo -e "  3. Access the web app at ${GREEN}http://localhost:3000${NC}"
echo -e "  4. API documentation at ${GREEN}http://localhost:8000/docs${NC}"
echo ""
echo -e "Useful commands:"
echo -e "  ${YELLOW}make up${NC}          - Start all services"
echo -e "  ${YELLOW}make down${NC}        - Stop all services"
echo -e "  ${YELLOW}make logs${NC}        - View logs"
echo -e "  ${YELLOW}make test${NC}        - Run tests"
echo -e "  ${YELLOW}make seed${NC}        - Seed sample data"
echo ""
