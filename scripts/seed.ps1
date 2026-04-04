# Edge Crew v3.0 - Database Seeding Script (PowerShell)
# Usage: .\scripts\seed.ps1 [environment]

$ErrorActionPreference = "Stop"

$Red = "`e[0;31m"
$Green = "`e[0;32m"
$Yellow = "`e[1;33m"
$Blue = "`e[0;34m"
$NC = "`e[0m"

$Environment = if ($args[0]) { $args[0] } else { "development" }

Write-Host "$Blue============================================$NC"
Write-Host "$Blue   Edge Crew v3.0 - Database Seeding        $NC"
Write-Host "$Blue   Environment: $Environment                $NC"
Write-Host "$Blue============================================$NC"
Write-Host ""

# Check if running in the correct directory
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "$Red Error: docker-compose.yml not found.$NC"
    Write-Host "$Yellow Please run this script from the project root directory.$NC"
    exit 1
}

# Check if database is running
$postgresRunning = docker-compose ps | Select-String "postgres.*Up"
if (-not $postgresRunning) {
    Write-Host "$Yellow PostgreSQL is not running. Starting it...$NC"
    docker-compose up -d postgres redis
    
    # Wait for PostgreSQL
    Write-Host "$Blue Waiting for PostgreSQL to be ready...$NC"
    $attempt = 0
    $maxAttempts = 30
    $ready = $false
    
    while ($attempt -lt $maxAttempts -and -not $ready) {
        try {
            $result = docker-compose exec -T postgres pg_isready -U edgecrew 2>$null
            if ($LASTEXITCODE -eq 0) {
                $ready = $true
            }
        } catch {
            Write-Host -NoNewline "."
            Start-Sleep -Seconds 2
            $attempt++
        }
    }
    
    Write-Host ""
    
    if (-not $ready) {
        Write-Host "$Red Error: PostgreSQL did not become ready in time$NC"
        exit 1
    }
    Write-Host "$Green PostgreSQL is ready$NC"
}

# Function to execute SQL
function Db-Exec($sql) {
    docker-compose exec -T postgres psql -U edgecrew -d edgecrew -q -c "$sql"
}

# Seed Sports
Write-Host "$Blue Seeding sports...$NC"
$sportsSql = @"
INSERT INTO sports (key, name, active) VALUES
    ('basketball_nba', 'NBA', true),
    ('basketball_ncaab', 'NCAAB', true),
    ('baseball_mlb', 'MLB', true),
    ('americanfootball_nfl', 'NFL', true),
    ('icehockey_nhl', 'NHL', true)
ON CONFLICT (key) DO NOTHING;
"@
Db-Exec $sportsSql
Write-Host "$Green Sports seeded$NC"

# Seed Teams
Write-Host "$Blue Seeding teams...$NC"
$teamsSql = @"
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
"@
Db-Exec $teamsSql
Write-Host "$Green Teams seeded$NC"

# Seed Users
Write-Host "$Blue Seeding users...$NC"
$usersSql = @"
INSERT INTO users (id, email, username, role, active, created_at) VALUES
    ('550e8400-e29b-41d4-a716-446655440000', 'admin@edgecrew.local', 'admin', 'admin', true, NOW()),
    ('550e8400-e29b-41d4-a716-446655440001', 'user@edgecrew.local', 'testuser', 'user', true, NOW())
ON CONFLICT (email) DO NOTHING;
"@
Db-Exec $usersSql
Write-Host "$Green Users seeded$NC"

# Seed Predictions
Write-Host "$Blue Seeding predictions...$NC"
$predictionsSql = @"
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
"@
Db-Exec $predictionsSql
Write-Host "$Green Predictions seeded$NC"

# Seed Games
Write-Host "$Blue Seeding games...$NC"
$gamesSql = @"
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
"@
Db-Exec $gamesSql
Write-Host "$Green Games seeded$NC"

# Run seed files from infrastructure/db/seeds if they exist
$seedsDir = "infrastructure\db\seeds"
if (Test-Path $seedsDir) {
    Get-ChildItem -Path $seedsDir -Filter "*.sql" | ForEach-Object {
        Write-Host "$Blue Running seed file: $($_.Name)$NC"
        docker-compose exec -T postgres psql -U edgecrew -d edgecrew -f "/docker-entrypoint-initdb.d/seeds/$($_.Name)" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "$Yellow Could not run $($_.Name)$NC"
        }
    }
}

Write-Host ""
Write-Host "$Green============================================$NC"
Write-Host "$Green   Database seeding completed!              $NC"
Write-Host "$Green============================================$NC"
Write-Host ""
Write-Host "Seeded data:"
Write-Host "  - 5 Sports"
Write-Host "  - 8 NBA Teams"
Write-Host "  - 2 Users (admin@edgecrew.local, user@edgecrew.local)"
Write-Host "  - 2 Sample Predictions"
Write-Host "  - 2 Sample Games"
Write-Host ""
