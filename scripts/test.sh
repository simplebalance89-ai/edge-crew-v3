#!/bin/bash
# Edge Crew v3.0 - Test Runner Script
# Usage: ./scripts/test.sh [service_name|all]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SERVICE=${1:-all}
VERBOSE=${2:-}

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   Edge Crew v3.0 - Test Runner             ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if running in the correct directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: docker-compose.yml not found.${NC}"
    echo -e "${YELLOW}Please run this script from the project root directory.${NC}"
    exit 1
fi

# Function to run tests for a Python service
run_python_tests() {
    local service_name=$1
    local extra_args=$2
    
    echo -e "${BLUE}Running tests for ${service_name}...${NC}"
    
    # Check if service exists
    if ! docker-compose config --services | grep -q "^${service_name}$"; then
        echo -e "${YELLOW}⚠ Service '${service_name}' not found in docker-compose.yml${NC}"
        return 0
    fi
    
    # Run tests
    if docker-compose run --rm "${service_name}" pytest ${extra_args} -v; then
        echo -e "${GREEN}✓ ${service_name} tests passed${NC}"
        return 0
    else
        echo -e "${RED}✗ ${service_name} tests failed${NC}"
        return 1
    fi
}

# Function to run tests for a Node.js service
run_node_tests() {
    local service_name=$1
    
    echo -e "${BLUE}Running tests for ${service_name}...${NC}"
    
    # Check if service exists
    if ! docker-compose config --services | grep -q "^${service_name}$"; then
        echo -e "${YELLOW}⚠ Service '${service_name}' not found in docker-compose.yml${NC}"
        return 0
    fi
    
    # Run tests
    if docker-compose run --rm "${service_name}" npm test; then
        echo -e "${GREEN}✓ ${service_name} tests passed${NC}"
        return 0
    else
        echo -e "${RED}✗ ${service_name} tests failed${NC}"
        return 1
    fi
}

# Track overall results
FAILED=0

# Run tests based on service parameter
case $SERVICE in
    all)
        echo -e "${BLUE}Running all tests...${NC}\n"
        
        # Python services
        run_python_tests "grading-engine" "$VERBOSE" || FAILED=$((FAILED+1))
        echo ""
        
        run_python_tests "ai-processor" "$VERBOSE" || FAILED=$((FAILED+1))
        echo ""
        
        run_python_tests "convergence" "$VERBOSE" || FAILED=$((FAILED+1))
        echo ""
        
        run_python_tests "data-ingestion" "$VERBOSE" || FAILED=$((FAILED+1))
        echo ""
        
        # Node.js services
        run_node_tests "api-gateway" || FAILED=$((FAILED+1))
        echo ""
        
        run_node_tests "web" || FAILED=$((FAILED+1))
        echo ""
        ;;
        
    grading-engine|ai-processor|convergence|data-ingestion)
        run_python_tests "$SERVICE" "$VERBOSE" || FAILED=$((FAILED+1))
        ;;
        
    api-gateway|web)
        run_node_tests "$SERVICE" || FAILED=$((FAILED+1))
        ;;
        
    *)
        echo -e "${RED}Error: Unknown service '${SERVICE}'${NC}"
        echo ""
        echo "Available services:"
        echo "  - all (default)"
        echo "  - grading-engine"
        echo "  - ai-processor"
        echo "  - convergence"
        echo "  - data-ingestion"
        echo "  - api-gateway"
        echo "  - web"
        echo ""
        echo "Usage:"
        echo "  ./scripts/test.sh              # Run all tests"
        echo "  ./scripts/test.sh all          # Run all tests"
        echo "  ./scripts/test.sh grading      # Run grading-engine tests"
        echo "  ./scripts/test.sh ai           # Run ai-processor tests"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}============================================${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}   All tests passed!                        ${NC}"
    echo -e "${GREEN}============================================${NC}"
    exit 0
else
    echo -e "${RED}   ${FAILED} test suite(s) failed             ${NC}"
    echo -e "${RED}============================================${NC}"
    exit 1
fi
