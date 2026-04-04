# Edge Crew v3.0 - Test Runner Script (PowerShell)
# Usage: .\scripts\test.ps1 [service_name|all]

$ErrorActionPreference = "Stop"

$Red = "`e[0;31m"
$Green = "`e[0;32m"
$Yellow = "`e[1;33m"
$Blue = "`e[0;34m"
$NC = "`e[0m"

$Service = if ($args[0]) { $args[0] } else { "all" }
$Verbose = if ($args[1]) { $args[1] } else { "" }

Write-Host "$Blue============================================$NC"
Write-Host "$Blue   Edge Crew v3.0 - Test Runner             $NC"
Write-Host "$Blue============================================$NC"
Write-Host ""

# Check if running in the correct directory
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "$Red Error: docker-compose.yml not found.$NC"
    Write-Host "$Yellow Please run this script from the project root directory.$NC"
    exit 1
}

# Function to run tests for a Python service
function Run-PythonTests($serviceName, $extraArgs) {
    Write-Host "$Blue Running tests for $serviceName...$NC"
    
    # Check if service exists
    $services = docker-compose config --services 2>$null
    if (-not ($services -match "^$serviceName$")) {
        Write-Host "$Yellow Service '$serviceName' not found in docker-compose.yml$NC"
        return $true
    }
    
    # Run tests
    docker-compose run --rm $serviceName pytest $extraArgs -v
    if ($LASTEXITCODE -eq 0) {
        Write-Host "$Green $serviceName tests passed$NC"
        return $true
    } else {
        Write-Host "$Red $serviceName tests failed$NC"
        return $false
    }
}

# Function to run tests for a Node.js service
function Run-NodeTests($serviceName) {
    Write-Host "$Blue Running tests for $serviceName...$NC"
    
    # Check if service exists
    $services = docker-compose config --services 2>$null
    if (-not ($services -match "^$serviceName$")) {
        Write-Host "$Yellow Service '$serviceName' not found in docker-compose.yml$NC"
        return $true
    }
    
    # Run tests
    docker-compose run --rm $serviceName npm test
    if ($LASTEXITCODE -eq 0) {
        Write-Host "$Green $serviceName tests passed$NC"
        return $true
    } else {
        Write-Host "$Red $serviceName tests failed$NC"
        return $false
    }
}

# Track overall results
$Failed = 0

# Run tests based on service parameter
switch ($Service) {
    "all" {
        Write-Host "$Blue Running all tests...$NC"
        Write-Host ""
        
        # Python services
        if (-not (Run-PythonTests "grading-engine" $Verbose)) { $Failed++ }
        Write-Host ""
        
        if (-not (Run-PythonTests "ai-processor" $Verbose)) { $Failed++ }
        Write-Host ""
        
        if (-not (Run-PythonTests "convergence" $Verbose)) { $Failed++ }
        Write-Host ""
        
        if (-not (Run-PythonTests "data-ingestion" $Verbose)) { $Failed++ }
        Write-Host ""
        
        # Node.js services
        if (-not (Run-NodeTests "api-gateway")) { $Failed++ }
        Write-Host ""
        
        if (-not (Run-NodeTests "web")) { $Failed++ }
        Write-Host ""
    }
    
    { $_ -in @("grading-engine", "ai-processor", "convergence", "data-ingestion") } {
        if (-not (Run-PythonTests $Service $Verbose)) { $Failed++ }
    }
    
    { $_ -in @("api-gateway", "web") } {
        if (-not (Run-NodeTests $Service)) { $Failed++ }
    }
    
    default {
        Write-Host "$Red Error: Unknown service '$Service'$NC"
        Write-Host ""
        Write-Host "Available services:"
        Write-Host "  - all (default)"
        Write-Host "  - grading-engine"
        Write-Host "  - ai-processor"
        Write-Host "  - convergence"
        Write-Host "  - data-ingestion"
        Write-Host "  - api-gateway"
        Write-Host "  - web"
        Write-Host ""
        Write-Host "Usage:"
        Write-Host "  .\scripts\test.ps1              # Run all tests"
        Write-Host "  .\scripts\test.ps1 all          # Run all tests"
        Write-Host "  .\scripts\test.ps1 grading      # Run grading-engine tests"
        Write-Host "  .\scripts\test.ps1 ai           # Run ai-processor tests"
        exit 1
    }
}

Write-Host ""
Write-Host "$Blue============================================$NC"

if ($Failed -eq 0) {
    Write-Host "$Green   All tests passed!                        $NC"
    Write-Host "$Green============================================$NC"
    exit 0
} else {
    Write-Host "$Red   $Failed test suite(s) failed             $NC"
    Write-Host "$Red============================================$NC"
    exit 1
}
