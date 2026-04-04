# Edge Crew v3.0 - Initial Setup Script (PowerShell)
# Usage: .\scripts\setup.ps1

$ErrorActionPreference = "Stop"

$Red = "`e[0;31m"
$Green = "`e[0;32m"
$Yellow = "`e[1;33m"
$Blue = "`e[0;34m"
$NC = "`e[0m"

Write-Host "$Blue============================================$NC"
Write-Host "$Blue   Edge Crew v3.0 - Setup Script            $NC"
Write-Host "$Blue============================================$NC"
Write-Host ""

# Check if running in the correct directory
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "$Red Error: docker-compose.yml not found.$NC"
    Write-Host "$Yellow Please run this script from the project root directory.$NC"
    exit 1
}

# Check prerequisites
Write-Host "$Blue Checking prerequisites...$NC"

# Check Docker
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Host "$Red Error: Docker is not installed.$NC"
    Write-Host "$Yellow Please install Docker: https://docs.docker.com/get-docker/$NC"
    exit 1
}

# Check Docker Compose
$dockerCompose = Get-Command docker-compose -ErrorAction SilentlyContinue
if (-not $dockerCompose) {
    try {
        docker compose version | Out-Null
    } catch {
        Write-Host "$Red Error: Docker Compose is not installed.$NC"
        Write-Host "$Yellow Please install Docker Compose: https://docs.docker.com/compose/install/$NC"
        exit 1
    }
}

Write-Host "$Green Docker and Docker Compose are installed$NC"

# Check .env file
if (-not (Test-Path ".env")) {
    Write-Host "$Yellow Creating .env file from template...$NC"
    Copy-Item ".env.example" ".env"
    Write-Host "$Green .env file created$NC"
    Write-Host "$Yellow NOTE: Please edit .env and add your API keys$NC"
} else {
    Write-Host "$Green .env file already exists$NC"
}

# Create necessary directories
Write-Host "$Blue Creating project directories...$NC"
New-Item -ItemType Directory -Force -Path "infrastructure\db\migrations" | Out-Null
New-Item -ItemType Directory -Force -Path "infrastructure\db\seeds" | Out-Null
New-Item -ItemType Directory -Force -Path "infrastructure\db\functions" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
Write-Host "$Green Directories created$NC"

# Pull base images
Write-Host "$Blue Pulling Docker base images...$NC"
try {
    docker-compose pull postgres redis
} catch {
    docker compose pull postgres redis
}
Write-Host "$Green Base images pulled$NC"

# Build service images
Write-Host "$Blue Building service images...$NC"
try {
    docker-compose build
} catch {
    docker compose build
}
Write-Host "$Green Service images built$NC"

# Start infrastructure services
Write-Host "$Blue Starting infrastructure services (PostgreSQL, Redis)...$NC"
try {
    docker-compose up -d postgres redis
} catch {
    docker compose up -d postgres redis
}

# Wait for PostgreSQL to be ready
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

# Initialize database schema
Write-Host "$Blue Initializing database schema...$NC"
if (Test-Path "infrastructure\db\schema.sql") {
    try {
        docker-compose exec -T postgres psql -U edgecrew -d edgecrew -f /docker-entrypoint-initdb.d/01-schema.sql
    } catch {
        docker compose exec -T postgres psql -U edgecrew -d edgecrew -f /docker-entrypoint-initdb.d/01-schema.sql
    }
    Write-Host "$Green Database schema initialized$NC"
} else {
    Write-Host "$Yellow schema.sql not found, skipping schema initialization$NC"
}

# Stop infrastructure services
Write-Host "$Blue Stopping infrastructure services...$NC"
try {
    docker-compose down
} catch {
    docker compose down
}
Write-Host "$Green Setup complete!$NC"

Write-Host ""
Write-Host "$Green============================================$NC"
Write-Host "$Green   Setup completed successfully!            $NC"
Write-Host "$Green============================================$NC"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit $Yellow.env$NC file and add your API keys"
Write-Host "  2. Run $Yellow make up $NC or $Yellow docker-compose up -d $NC to start all services"
Write-Host "  3. Access the web app at $Green http://localhost:3000 $NC"
Write-Host "  4. API documentation at $Green http://localhost:8000/docs $NC"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  $Yellow make up $NC         - Start all services"
Write-Host "  $Yellow make down $NC       - Stop all services"
Write-Host "  $Yellow make logs $NC       - View logs"
Write-Host "  $Yellow make test $NC       - Run tests"
Write-Host "  $Yellow make seed $NC       - Seed sample data"
Write-Host ""
