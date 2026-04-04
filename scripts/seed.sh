#!/bin/bash
# Edge Crew v3.0 - Database Seeding Script
# Usage: ./scripts/seed.sh [environment]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENVIRONMENT=${1:-development}

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Edge Crew v3.0 - Database Seeding        ${NC}"
echo -e "${BLUE}   Environment: ${ENVIRONMENT}                ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if running in the correct directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found.${NC}"
    echo -e "${YELLOW}Please run this script from the project root directory.${NC}"
    exit 1
fi

# Check if database is running
if ! docker-compose ps | grep -q "postgres.*Up" 2>/dev/null; then
    echo -e "${YELLOW}PostgreSQL is not running. Starting it...${NC}"
    docker-compose up -d postgres redis
    
    # Wait for PostgreSQL
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
fi

# Function to execute SQL
db_exec() {
    docker-compose exec -T postgres psql -U edgecrew -d edgecrew -q -c "$1"
}

# Seed Sports
echo -e "${BLUE}Seeding sports...${NC}"
db_exec "
INSERT INTO sports (key, name, active) VALUES
    ('basketball_nba', 'NBA', true),
    ('basketball_ncaab', 'NCAAB', true),
    ('baseball_mlb', 'MLB', true),
    ('americanfootball_nfl', 'NFL', true),
    ('icehockey_nhl', 'NHL', true)
ON CONFLICT (key) DO NOTHING;
"
echo -e "${GREEN}✓ Sports seeded${NC}"

# Seed Teams (Sample NBA Teams)
echo -e "${BLUE}Seeding teams...${NC}"
db_exec "
INSERT INTO teams (sport_key, external_id, name, city, abbreviation, active) VALUES
    ('basketball_nba', 'lal', 'Lakers', 'Los Angeles', 'LAL', true),
    ('basketball_nba', 'gsw', 'Warriors', 'Golden State', 'GSW', true),
    ('basketball_nba', 'bos', 'Celtics', 'Boston', 'BOS', true),
    ('basketball_nba', 'mia', 'Heat', 'Miami', 'MIA', true),
    ('basketball_nba', 'den', 'Nuggets', 'Denver', 'DEN', true),
    ('basketball_nba', 'mil', 'Bucks', 'Milwaukee', 'MIL', true),
    ('basketball_nba', 'phx', 'Suns', 'Phoenix', 'PHX', true),
    ('basketball_nba', 'phi', '76ers', 'Philadelphia', 'PHI', true)
ON CONFLICT (external_id) DO NOTHING;
"
echo -e "${GREEN}✓ Teams seeded${NC}"

# Seed Sample Users
echo -e "${BLUE}Seeding users...${NC}"
db_exec "
INSERT INTO users (id, email, username, role, active, created_at) VALUES
    ('550e8400-e29b-41d4-a716-446655440000', 'admin@edgecrew.local', 'admin', 'admin', true, NOW()),
    ('550e8400-e29b-41d4-a716-446655440001', 'user@edgecrew.local', 'testuser', 'user', true, NOW())
ON CONFLICT (email) DO NOTHING;
"
echo -e "${GREEN}✓ Users seeded${NC}"

# Seed Sample Predictions
echo -e "${BLUE}Seeding predictions...${NC}"
db_exec "
INSERT INTO predictions (
    id, user_id, sport_key, game_id, prediction_type, 
    prediction_value, odds, stake, confidence, status, created_at
) VALUES
    (
        gen_random_uuid(),
        '550e8400-e29b-41d4-a716-446655440001',
        'basketball_nba',
        'lal-vs-gsw-001',
        'spread',
        'LAL -4.5',
        -110,
        100.00,
        0.75,
        'pending',
        NOW() - INTERVAL '1 day'
    ),
    (
        gen_random_uuid(),
        '550e8400-e29b-41d4-a716-446655440001',
        'basketball_nba',
        'bos-vs-mia-001',
        'moneyline',
        'BOS',
        -150,
        50.00,
        0.82,
        'pending',
        NOW() - INTERVAL '12 hours'
    )
ON CONFLICT DO NOTHING;
"
echo -e "${GREEN}✓ Predictions seeded${NC}"

# Seed Sample Games
echo -e "${BLUE}Seeding games...${NC}"
db_exec "
INSERT INTO games (
    id, sport_key, home_team_id, away_team_id, 
    game_time, status, created_at
) VALUES
    (
        'lal-vs-gsw-001',
        'basketball_nba',
        'lal',
        'gsw',
        NOW() + INTERVAL '2 hours',
        'scheduled',
        NOW()
    ),
    (
        'bos-vs-mia-001',
        'basketball_nba',
        'bos',
        'mia',
        NOW() + INTERVAL '4 hours',
        'scheduled',
        NOW()
    )
ON CONFLICT (id) DO NOTHING;
"
echo -e "${GREEN}✓ Games seeded${NC}"

# Run seed files from infrastructure/db/seeds if they exist
if [ -d "infrastructure/db/seeds" ]; then
    for seed_file in infrastructure/db/seeds/*.sql; do
        if [ -f "$seed_file" ]; then
            echo -e "${BLUE}Running seed file: $(basename $seed_file)${NC}"
            docker-compose exec -T postgres psql -U edgecrew -d edgecrew -f "/docker-entrypoint-initdb.d/seeds/$(basename $seed_file)" 2>/dev/null || \
                echo -e "${YELLOW}⚠ Could not run $(basename $seed_file)${NC}"
        fi
    done
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   Database seeding completed!              ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Seeded data:"
echo "  - 5 Sports"
echo "  - 8 NBA Teams"
echo "  - 2 Users (admin@edgecrew.local, user@edgecrew.local)"
echo "  - 2 Sample Predictions"
echo "  - 2 Sample Games"
echo ""
