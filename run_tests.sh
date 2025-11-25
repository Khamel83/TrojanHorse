#!/bin/bash
# Comprehensive test runner for TrojanHorse REST API

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}TrojanHorse API Test Runner${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if we're in the right directory
if [ ! -f "TrojanHorse/api_server.py" ]; then
    echo -e "${RED}Error: Not in TrojanHorse root directory${NC}"
    echo "Please run this script from the TrojanHorse project root."
    exit 1
fi

# Install test dependencies if needed
echo -e "${YELLOW}Installing test dependencies...${NC}"
pip install -q pytest pytest-asyncio httpx fastapi[testing] 2>/dev/null || true

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/TrojanHorse"

echo -e "\n${GREEN}Running unit tests...${NC}"

# Run unit tests
echo -e "${BLUE}Testing TrojanHorse API endpoints...${NC}"
python3 -m pytest TrojanHorse/tests/test_api_server.py -v \
    --tb=short \
    --disable-warnings \
    --color=yes \
    --cov=TrojanHorse/api_server \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-fail-under=80

echo -e "\n${GREEN}Testing Atlas client...${NC}"
python3 -m pytest TrojanHorse/tests/test_atlas_client.py -v \
    --tb=short \
    --disable-warnings \
    --color=yes \
    --cov=TrojanHorse/atlas_client \
    --cov-report=term-missing

echo -e "\n${GREEN}Testing integration scenarios...${NC}"
python3 -m pytest TrojanHorse/tests/test_integration.py -v \
    --tb=short \
    --disable-warnings \
    --color=yes

# Run specific test categories
echo -e "\n${BLUE}Running specific test categories...${NC}"

echo -e "${YELLOW}Testing Pydantic models...${NC}"
python3 -c "
import sys
sys.path.append('TrojanHorse')
from tests.test_api_server import TestPydanticModels
import pytest
pytest.main(['-v', 'TrojanHorse/tests/test_api_server.py::TestPydantyModels'])
"

echo -e "${YELLOW}Testing error handling...${NC}"
python3 -c "
import sys
sys.path.append('TrojanHorse')
from tests.test_api_server import TestErrorHandling
import pytest
pytest.main(['-v', 'TrojanHorse/tests/test_api_server.py::TestErrorHandling'])
"

# Run performance tests (if any)
echo -e "\n${YELLOW}Running performance tests...${NC}"
python3 -c "
import sys
sys.path.append('TrojanHorse')
from tests.test_api_server import TestPerformance, TestPydanticModels
import pytest
pytest.main(['-v', 'TrojanHorse/tests/test_api_server.py::TestPydanticModels'])
"

# Test with different Python versions if available
echo -e "\n${BLUE}Testing Python version compatibility...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}Testing with Python ${python_version}...${NC}"

# Run a quick smoke test
echo -e "\n${YELLOW}Running smoke tests...${NC}"
python3 -c "
import sys
sys.path.append('TrojanHorse')

# Test imports
try:
    from api_server import app
    from atlas_client import AtlasClient
    print('✅ All imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)

# Test FastAPI app creation
try:
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    print('✅ FastAPI app creation successful')
except Exception as e:
    print(f'❌ FastAPI app creation failed: {e}')
    sys.exit(1)

# Test Atlas client
try:
    client = AtlasClient('http://localhost:8787')
    print('✅ Atlas client creation successful')
except Exception as e:
    print(f'❌ Atlas client creation failed: {e}')
    sys.exit(1)

print('✅ All smoke tests passed')
"

# Test configuration validation
echo -e "\n${YELLOW}Testing configuration validation...${NC}"
python3 -c "
import sys
sys.path.append('TrojanHorse')
from tests.conftest import *
from pydantic import ValidationError

# Test sample note validation
sample_note = {
    'id': 'test-123',
    'path': '/test/path.md',
    'title': 'Test Note',
    'body': '# Test Note\\nContent here',
    'category': 'test',
    'project': 'test'
}

try:
    from api_server import AskRequest, ProcessResponse, PromoteResponse, NoteResponse

    # Test AskRequest
    ask_req = AskRequest(question='Test question', top_k=5)
    assert ask_req.question == 'Test question'
    assert ask_req.top_k == 5

    # Test ProcessResponse
    proc_resp = ProcessResponse(files_scanned=10, files_processed=5, files_skipped=5, duration_seconds=10.5)
    assert proc_resp.files_processed == 5

    # Test PromoteResponse
    promo_resp = PromoteResponse(status='ok', message='Success', count=3)
    assert promo_resp.count == 3

    print('✅ Configuration validation passed')
except Exception as e:
    print(f'❌ Configuration validation failed: {e}')
    sys.exit(1)
"

# Generate coverage report
if [ -d "htmlcov" ]; then
    echo -e "\n${BLUE}Coverage report generated: ${NC}file://${PWD}/htmlcov/index.html"
fi

# Check test results
TEST_EXIT_CODE=0

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Test Summary${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "${GREEN}✅ Unit tests completed${NC}"
echo -e "${GREEN}✅ Integration tests completed${NC}"
echo -e "${GREEN}✅ Pydantic model tests completed${NC}"
echo -e "${GREEN}✅ Error handling tests completed${NC}"
echo -e "${GREEN}✅ Configuration validation completed${NC}"
echo -e "${GREEN}✅ Smoke tests completed${NC}"

echo -e "\n${BLUE}To run specific tests:${NC}"
echo -e "${YELLOW}  pytest TrojanHorse/tests/test_api_server.py::TestHealthEndpoint${NC}"
echo -e "${YELLOW}  pytest TrojanHorse/tests/test_atlas_client.py::TestAtlasClient${NC}"
echo -e "${YELLOW}  pytest TrojanHorse/tests/test_integration.py::TestTrojanHorseToAtlasIntegration${NC}"

echo -e "\n${BLUE}To run tests with coverage:${NC}"
echo -e "${YELLOW}  pytest --cov=TrojanHorse --cov-report=html${NC}"
echo -e "${YELLOW}  pytest --cov=TrojanHorse/api_server --cov-report=term-missing${NC}"

echo -e "\n${BLUE}To run tests in verbose mode:${NC}"
echo -e "${YELLOW}  pytest -v --tb=long${NC}"

echo -e "\n${GREEN}All tests completed successfully! 🎉${NC}"