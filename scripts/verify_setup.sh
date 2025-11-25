#!/usr/bin/env bash
# TrojanHorse Setup Verification Script
# Run this to verify your setup is working correctly

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 TrojanHorse Setup Verification${NC}"
echo "=================================="

# Find TrojanHorse directory
if [[ -n "${TROJANHORSE_DIR:-}" ]]; then
    cd "$TROJANHORSE_DIR"
elif [[ -f "./pyproject.toml" ]] && [[ -d "./trojanhorse" ]]; then
    echo -e "${GREEN}✓ Found TrojanHorse in current directory${NC}"
else
    echo -e "${RED}❌ Could not find TrojanHorse directory${NC}"
    echo "Set TROJANHORSE_DIR environment variable or run from TrojanHorse directory"
    exit 1
fi

# Check virtual environment
echo -e "\n${BLUE}📦 Checking virtual environment...${NC}"
if [[ -d "venv" ]]; then
    source venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment found and activated${NC}"
else
    echo -e "${RED}❌ Virtual environment not found${NC}"
    echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -e ."
    exit 1
fi

# Check installation
echo -e "\n${BLUE}🔧 Checking installation...${NC}"
if command -v th >/dev/null 2>&1; then
    echo -e "${GREEN}✓ 'th' command is available${NC}"
else
    echo -e "${RED}❌ 'th' command not found${NC}"
    echo "Run: pip install -e ."
    exit 1
fi

# Check configuration
echo -e "\n${BLUE}⚙️  Checking configuration...${NC}"
if [[ -f ".env" ]]; then
    echo -e "${GREEN}✓ .env file found${NC}"

    # Check key configuration variables
    if grep -q "WORKVAULT_ROOT=" .env; then
        echo -e "${GREEN}✓ WORKVAULT_ROOT configured${NC}"
    else
        echo -e "${YELLOW}⚠️  WORKVAULT_ROOT not set in .env${NC}"
    fi

    if grep -q "OPENROUTER_API_KEY=" .env && ! grep -q "OPENROUTER_API_KEY=$" .env; then
        echo -e "${GREEN}✓ OpenRouter API key configured${NC}"
    else
        echo -e "${YELLOW}⚠️  OpenRouter API key not set${NC}"
    fi

    if grep -q "EMBEDDING_API_KEY=" .env && ! grep -q "EMBEDDING_API_KEY=$" .env; then
        echo -e "${GREEN}✓ Embedding API key configured${NC}"
    else
        echo -e "${YELLOW}⚠️  Embedding API key not set (will use fallback)${NC}"
    fi
else
    echo -e "${RED}❌ .env file not found${NC}"
    echo "Copy .env.example to .env and configure it"
    exit 1
fi

# Check vault directories
echo -e "\n${BLUE}📁 Checking vault structure...${NC}"
WORKVAULT_ROOT=$(grep WORKVAULT_ROOT .env | cut -d'=' -f2)
if [[ -n "$WORKVAULT_ROOT" ]] && [[ -d "$WORKVAULT_ROOT" ]]; then
    echo -e "${GREEN}✓ Vault root exists: $WORKVAULT_ROOT${NC}"

    # Check capture directories
    CAPTURE_DIRS=$(grep WORKVAULT_CAPTURE_DIRS .env | cut -d'=' -f2)
    IFS=',' read -ra DIRS <<< "$CAPTURE_DIRS"
    for dir in "${DIRS[@]}"; do
        FULL_PATH="$WORKVAULT_ROOT/${dir}"
        if [[ -d "$FULL_PATH" ]]; then
            echo -e "${GREEN}✓ Capture directory exists: $dir${NC}"
        else
            echo -e "${YELLOW}⚠️  Capture directory missing: $dir (will be created)${NC}"
        fi
    done
else
    echo -e "${RED}❌ Vault root not found or WORKVAULT_ROOT not set${NC}"
fi

# Run setup command
echo -e "\n${BLUE}🚀 Running setup command...${NC}"
if th setup; then
    echo -e "${GREEN}✓ Setup command completed successfully${NC}"
else
    echo -e "${RED}❌ Setup command failed${NC}"
    exit 1
fi

# Test basic functionality
echo -e "\n${BLUE}🧪 Testing basic functionality...${NC}"

# Create test file
TEST_DIR="$WORKVAULT_ROOT/Inbox"
mkdir -p "$TEST_DIR"
TEST_FILE="$TEST_DIR/test_note.txt"
echo "This is a test note for TrojanHorse verification." > "$TEST_FILE"

echo -e "${GREEN}✓ Created test file: $TEST_FILE${NC}"

# Run process command
echo "Running: th process"
if th process; then
    echo -e "${GREEN}✓ Process command completed successfully${NC}"
else
    echo -e "${RED}❌ Process command failed${NC}"
    exit 1
fi

# Check if processed file exists
if [[ -f "$TEST_FILE" ]]; then
    echo -e "${YELLOW}⚠️  Original test file still exists (may have been processed)${NC}"
else
    echo -e "${GREEN}✓ Test file was processed and removed${NC}"
fi

# Clean up
if [[ -f "$TEST_FILE" ]]; then
    rm "$TEST_FILE"
    echo -e "${GREEN}✓ Cleaned up test file${NC}"
fi

# Show final status
echo -e "\n${BLUE}📊 Final status:${NC}"
th status

echo -e "\n${GREEN}🎉 Setup verification completed successfully!${NC}"
echo -e "${GREEN}   You're ready to use TrojanHorse.${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "• Start workday: ./scripts/start_workday.sh"
echo "• Process files: th process"
echo "• Query notes: th ask 'your question'"
echo "• View workflows: cat WORKFLOWS.md"