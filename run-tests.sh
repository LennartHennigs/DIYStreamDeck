#!/bin/bash

# StreamDeck Test Runner
# Activates test environment and runs tests with proper PYTHONPATH

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 StreamDeck Test Runner${NC}"
echo "==============================="

# Activate test environment
if [ -d "test_venv" ]; then
    echo -e "${GREEN}✓ Activating test environment...${NC}"
    source test_venv/bin/activate
else
    echo -e "${RED}✗ Test environment not found. Run: python -m venv test_venv && source test_venv/bin/activate && pip install -r tests/requirements_test.txt${NC}"
    exit 1
fi

# Set PYTHONPATH
export PYTHONPATH=$(pwd):$PYTHONPATH

# Parse command line arguments
case "${1:-all}" in
    "pico")
        echo -e "${BLUE}🔧 Running Pi Pico tests (85 tests)...${NC}"
        pytest tests/unit/pico/ -v
        ;;
    "mac")
        echo -e "${BLUE}💻 Running Mac tests...${NC}"
        pytest tests/unit/mac/ -v
        ;;
    "security")
        echo -e "${BLUE}🔒 Running security tests...${NC}"
        pytest tests/security/ -v
        ;;
    "unit")
        echo -e "${BLUE}🧪 Running all unit tests...${NC}"
        pytest tests/unit/ -v
        ;;
    "quick")
        echo -e "${BLUE}⚡ Running quick Pi Pico tests...${NC}"
        pytest tests/unit/pico/ --tb=line -q
        ;;
    "corruption")
        echo -e "${BLUE}💥 Running JSON corruption tests...${NC}"
        pytest tests/unit/pico/test_json_corruption.py -v
        ;;
    "heartbeat")
        echo -e "${BLUE}💓 Running heartbeat functionality tests...${NC}"
        pytest tests/unit/pico/test_heartbeat_functionality.py -v
        ;;
    "all")
        echo -e "${BLUE}🚀 Running ALL tests (~125 tests)...${NC}"
        pytest tests/ -v
        ;;
    *)
        echo "Usage: $0 [pico|mac|security|unit|quick|corruption|heartbeat|all]"
        echo ""
        echo "Test categories:"
        echo "  pico       - Pi Pico tests only (85 tests)"
        echo "  mac        - Mac watchdog tests only"
        echo "  security   - Security vulnerability tests"
        echo "  unit       - All unit tests (pico + mac)"
        echo "  quick      - Quick Pi Pico tests only"
        echo "  corruption - JSON corruption tests only"
        echo "  heartbeat  - Heartbeat functionality tests only"
        echo "  all        - All tests including security"
        exit 1
        ;;
esac

echo -e "${GREEN}✅ Tests completed!${NC}"