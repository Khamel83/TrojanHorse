#!/usr/bin/env bash
# TrojanHorse Workday Starter
# Run this at the start of your workday to begin continuous processing

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}🐴 TrojanHorse Workday Starter${NC}"
echo "=================================="

# Find the TrojanHorse directory
if [[ -n "${TROJANHORSE_DIR:-}" ]]; then
    cd "$TROJANHORSE_DIR"
elif [[ -f "./pyproject.toml" ]] && [[ -d "./trojanhorse" ]]; then
    echo -e "${GREEN}✓ Found TrojanHorse in current directory${NC}"
else
    # Try common locations
    if [[ -d "$HOME/TrojanHorse" ]]; then
        cd "$HOME/TrojanHorse"
    elif [[ -d "$HOME/dev/TrojanHorse" ]]; then
        cd "$HOME/dev/TrojanHorse"
    else
        echo -e "${RED}❌ Could not find TrojanHorse directory${NC}"
        echo "Set TROJANHORSE_DIR environment variable or run from TrojanHorse directory"
        exit 1
    fi
    echo -e "${GREEN}✓ Found TrojanHorse at $(pwd)${NC}"
fi

# Check if virtual environment exists
if [[ ! -d "venv" ]]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found, creating one...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -e .
    echo -e "${GREEN}✓ Virtual environment created and dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Virtual environment found${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# Check configuration
if [[ ! -f ".env" ]]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# Run setup to ensure everything is ready
echo -e "${BLUE}🔧 Running setup check...${NC}"
if th setup; then
    echo -e "${GREEN}✓ Setup check passed${NC}"
else
    echo -e "${RED}❌ Setup check failed${NC}"
    exit 1
fi

# Show status
echo -e "${BLUE}📊 Current status:${NC}"
th status

# Start workday loop
echo ""
echo -e "${BLUE}🚀 Starting TrojanHorse workday loop...${NC}"
echo -e "${YELLOW}• Processing every 5 minutes${NC}"
echo -e "${YELLOW}• Press Ctrl+C to stop${NC}"
echo -e "${YELLOW}• Logs will appear below${NC}"
echo ""
echo "=================================="

# Start the workday loop
exec th workday