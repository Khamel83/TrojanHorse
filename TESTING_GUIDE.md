# Comprehensive Testing Guide for TrojanHorse

This guide covers all aspects of testing the TrojanHorse REST API integration, including unit tests, integration tests, and manual validation procedures.

## 🚀 Quick Start

### Run All Tests

```bash
# TrojanHorse
cd /path/to/TrojanHorse
./run_tests.sh

# Atlas
cd /path/to/atlas
./run_tests.sh
```

### Run Specific Test Categories

```bash
# TrojanHorse unit tests only
pytest TrojanHorse/tests/test_api_server.py -v

# Atlas TrojanHorse integration tests only
pytest tests/test_trojanhorse_router.py -v

# Integration tests only
pytest TrojanHorse/tests/test_integration.py -v

# Tests with coverage
pytest --cov=TrojanHorse --cov-report=html
```

## 📋 Test Structure

### Directory Structure

```
TrojanHorse/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Test configuration and fixtures
│   ├── test_api_server.py        # API server unit tests
│   ├── test_atlas_client.py     # Atlas client tests
│   └── test_integration.py       # Integration tests
├── run_tests.sh                  # Test runner script
└── TESTING_GUIDE.md             # This file
```

### Test Categories

1. **Unit Tests**: Individual component testing
2. **Integration Tests**: End-to-end workflow testing
3. **Performance Tests**: Load and stress testing
4. **Security Tests**: Authentication and validation testing
5. **Smoke Tests**: Basic functionality verification

## 🔧 Test Configuration

### Environment Setup

```bash
# Set up test environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)/TrojanHorse"
export WORKVAULT_ROOT="/tmp/test_vault"
export TROJANHORSE_STATE_DIR="/tmp/test_state"

# Install test dependencies
pip install pytest pytest-asyncio httpx fastapi[testing]
```

### Test Fixtures

The test suite uses comprehensive fixtures defined in `conftest.py`:

- `temp_dir()`: Temporary directory for test files
- `test_config()`: Test configuration object
- `sample_trojanhorse_note()`: Sample note for testing
- `mock_processor()`: Mock processor object
- `mock_rag_index()`: Mock RAG index
- `mock_index_db()`: Mock database object

## 🧪 Unit Tests

### API Server Tests (`test_api_server.py`)

#### Health Endpoint Tests
```python
def test_health_check(self, test_client):
    """Test basic health check."""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

#### Processing Endpoint Tests
```python
def test_process_once_success(self, test_client, mock_processor):
    """Test successful processing endpoint."""
    response = test_client.post("/process")
    assert response.status_code == 200
    data = response.json()
    assert "files_processed" in data
```

#### Search and Query Tests
```python
def test_ask_question_success(self, test_client, sample_ask_request, mock_rag_response):
    """Test successful question asking."""
    response = test_client.post("/ask", json=sample_ask_request)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
```

#### Note Management Tests
```python
def test_get_specific_note_success(self, test_client, mock_index_db, sample_note_content):
    """Test getting a specific note."""
    response = test_client.get("/notes/test-note-123")
    assert response.status_code == 200
    data = response.json()
    assert "meta" in data
    assert "content" in data
```

### Atlas Client Tests (`test_atlas_client.py`)

#### Client Initialization Tests
```python
def test_init_with_url_only(self):
    """Test client initialization with URL only."""
    client = AtlasClient("http://localhost:8787")
    assert client.atlas_url == "http://localhost:8787"
    assert client.api_key is None
```

#### Health Check Tests
```python
def test_health_check_success(self):
    """Test successful health check."""
    client = AtlasClient("http://localhost:8787")
    with patch('requests.Session.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client.health_check()
        assert result is True
```

#### Ingestion Tests
```python
def test_ingest_notes_success(self, sample_trojanhorse_notes_batch):
    """Test successful notes ingestion."""
    client = AtlasClient("http://localhost:8787", "test-key")
    with patch('requests.Session.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "count": 3}
        mock_post.return_value = mock_response

        result = client.ingest_notes(sample_trojanhorse_notes_batch)
        assert result is True
```

## 🔄 Integration Tests

### TrojanHorse to Atlas Tests (`test_integration.py`)

#### Complete Workflow Tests
```python
def test_full_promotion_workflow(self, trojanhorse_client, atlas_mock_client, sample_integration_note):
    """Test complete promotion workflow from TrojanHorse to Atlas."""
    # Step 1: Get notes from TrojanHorse
    # Step 2: Send to Atlas
    # Step 3: Verify data integrity
```

#### Concurrency Tests
```python
def test_concurrent_api_requests(self, trojanhorse_client, atlas_mock_client):
    """Test handling concurrent API requests."""
    # Create multiple threads for concurrent requests
    # Verify system stability under load
```

#### Performance Tests
```python
def test_large_batch_performance(self, trojanhorse_client, atlas_mock_client):
    """Test performance with large batches of notes."""
    # Create large batch of notes
    # Measure processing time
    # Verify performance constraints
```

## 🔒 Security Tests

### Authentication Tests

```python
def test_api_key_validation(self, monkeypatch):
    """Test API key validation."""
    # Test with correct key
    monkeypatch.setenv("ATLAS_API_KEY", "correct-key")
    result = validate_api_key("correct-key")
    assert result is True

    # Test with incorrect key
    with pytest.raises(HTTPException):
        validate_api_key("incorrect-key")
```

### Input Validation Tests

```python
def test_ingest_note_validation(self, sample_trojanhorse_note):
    """Test IngestNote model validation."""
    note = IngestNote(**sample_trojanhorse_note)
    assert note.id == "test-note-123"
    assert note.title == "Project Sync Meeting"
    assert len(note.tags) == 3
```

### Size Limit Tests

```python
def test_oversized_content_rejection(self):
    """Test rejection of oversized content."""
    oversized_note = {
        "id": "oversized-note",
        "title": "Oversized Note",
        "body": "x" * 2000000,  # 2MB+ content
        "category": "test",
        "project": "test"
    }

    with pytest.raises(ValidationError):
        IngestNote(**oversized_note)
```

## 📊 Test Reports

### Coverage Reports

Generate comprehensive coverage reports:

```bash
# HTML coverage report
pytest --cov=TrojanHorse --cov-report=html

# Terminal coverage with missing lines
pytest --cov=TrojanHorse --cov-report=term-missing

# Coverage for specific modules
pytest --cov=TrojanHorse/api_server --cov=TrojanHorse/atlas_client
```

### Coverage Targets

- **API Server**: 95% coverage target
- **Atlas Client**: 95% coverage target
- **Integration Tests**: 90% coverage target

### Coverage Analysis

```bash
# Show coverage report
coverage report

# Generate detailed HTML report
coverage html
open htmlcov/index.html
```

## 🚨 Error Handling Tests

### HTTP Error Handling

```python
def test_invalid_endpoint(self, test_client):
    """Test accessing invalid endpoint."""
    response = test_client.get("/invalid-endpoint")
    assert response.status_code == 404

def test_invalid_method(self, test_client):
    """Test using invalid HTTP method."""
    response = test_client.delete("/health")
    assert response.status_code == 405

def test_malformed_json(self, test_client):
    """Test malformed JSON payload."""
    response = test_client.post(
        "/ask",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
```

### Database Error Handling

```python
def test_database_connection_error(self, test_client):
    """Test handling of database connection errors."""
    with patch('helpers.simple_database.SimpleDatabase') as mock_db:
        mock_db.side_effect = Exception("Database connection failed")

        response = test_client.get("/trojanhorse/stats")
        assert response.status_code == 500
```

### Service Unavailable Handling

```python
def test_service_unavailable_handling(self):
    """Test handling when Atlas service is unavailable."""
    with patch('TrojanHorse.atlas_client.requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.ConnectionError("Service unavailable")

        result = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            None,  # No Atlas client
            ["note-1"]
        )
        assert result == 0
```

## ⚡ Performance Tests

### Load Testing

```python
def test_concurrent_requests_stress(self):
    """Test system behavior under concurrent request stress."""
    # Create multiple threads
    # Make concurrent requests
    # Verify system stability
    # Measure response times
```

### Memory Usage Tests

```python
def test_memory_usage_large_batch(self):
    """Test memory usage with large data batches."""
    import psutil
    import gc

    # Measure baseline memory
    process = psutil.Process()
    baseline_memory = process.memory_info().rss

    # Process large batch
    large_batch = create_large_note_batch(1000)

    # Measure memory after processing
    after_memory = process.memory_info().rss
    memory_increase = after_memory - baseline_memory

    # Verify memory constraints
    assert memory_increase < 100 * 1024 * 1024  # 100MB limit

    # Clean up
    del large_batch
    gc.collect()
```

### Response Time Tests

```python
def test_response_time_constraints(self, test_client):
    """Test API response time constraints."""
    import time

    start_time = time.time()

    response = test_client.post("/process")

    response_time = time.time() - start_time
    assert response_time < 5.0  # 5 second limit
```

## 🔍 Manual Testing Guide

### API Endpoint Testing

#### Health Checks

```bash
# TrojanHorse API
curl -f http://localhost:8765/health

# Atlas TrojanHorse integration
curl -f http://localhost:8787/trojanhorse/health
```

#### Processing Testing

```bash
# Trigger processing
curl -X POST http://localhost:8765/process

# Rebuild embeddings
curl -X POST http://localhost:8765/embed

# Get statistics
curl http://localhost:8765/stats
```

#### Search Testing

```bash
# List notes
curl "http://localhost:8765/notes?category=meeting&limit=10"

# Ask question
curl -X POST http://localhost:8765/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What meetings did I have this week?", "top_k": 5}'

# Promote notes
curl -X POST http://localhost:8765/promote \
  -H "Content-Type: application/json" \
  -d '{"note_ids": ["note-1", "note-2"]}'
```

#### Atlas Integration Testing

```bash
# Ingest single note
curl -X POST http://localhost:8787/trojanhorse/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "id": "test-note",
    "title": "Test Note",
    "body": "# Test Note\nContent here",
    "category": "test",
    "project": "test-project"
  }'

# Ingest batch notes
curl -X POST http://localhost:8787/trojanhorse/ingest/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "notes": [
      {"id": "note-1", "title": "Note 1", "body": "Content 1"},
      {"id": "note-2", "title": "Note 2", "body": "Content 2"}
    ]
  }'
```

### Integration Workflow Testing

#### Complete Promotion Test

```bash
# 1. Start TrojanHorse API
cd /path/to/TrojanHorse
th api --host 127.0.0.1 --port 8765 &

# 2. Start Atlas API
cd /path/to/atlas
atlas api --host 127.0.0.1 --port 8787 &

# 3. Configure environment
export ATLAS_API_URL="http://localhost:8787"
export ATLAS_API_KEY="your-test-key"

# 4. Create test note
echo '# Test Note
This is a test note for integration validation.' > /tmp/test_note.md

# 5. Process and promote
th process
th promote-to-atlas "test-note-id"

# 6. Verify in Atlas
curl http://localhost:8787/trojanhorse/stats
```

### Debugging Failed Tests

#### Run Single Test with Debugging

```bash
# Run specific test with full output
pytest tests/test_api_server.py::TestHealthEndpoint::test_health_check -v -s

# Run with PDB debugger
pytest tests/test_api_server.py::TestHealthEndpoint::test_health_check -v --pdb

# Run with log capture
pytest tests/test_api_server.py::TestHealthEndpoint::test_health_check -v --log-cli-level=DEBUG
```

#### Test Environment Variables

```bash
# Set debug environment
export TROJANHORSE_LOG_LEVEL=DEBUG
export PYTEST_CURRENT_TEST=test_health_check

# Run with custom configuration
pytest tests/test_api_server.py -c test_config.py

# Run with markers
pytest tests/ -m "not slow" -v
```

## 📈 Test Metrics and Reporting

### Test Metrics Collection

```python
# Test execution time
pytest --durations=10

# Test performance profiling
pytest --profile

# Generate benchmark reports
pytest --benchmark-only
```

### Continuous Integration

#### GitHub Actions Workflow

```yaml
name: TrojanHorse API Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio httpx fastapi[testing]

    - name: Run tests
      run: |
        ./run_tests.sh

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./htmlcov/index.html
```

### Local CI/CD

```bash
#!/bin/bash
# pre-commit hook for running tests

echo "Running pre-commit tests..."
./run_tests.sh

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ All tests passed"
    exit 0
else
    echo "❌ Tests failed"
    exit 1
fi
```

## 🛠️ Troubleshooting

### Common Test Issues

#### Import Errors

```bash
# Fix Python path issues
export PYTHONPATH="${PYTHONPATH}:$(pwd)/TrojanHorse"

# Install missing dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx fastapi[testing]
```

#### Database Connection Errors

```bash
# Mock database in tests
export ATLAS_DB_PATH=":memory:"
export DATABASE_URL="sqlite:///:memory:"

# Check test database setup
python -c "from helpers.simple_database import SimpleDatabase; print('DB OK')"
```

#### Port Conflicts

```bash
# Check port availability
lsof -i :8765
lsof -i :8787

# Use different test ports
export TROJANHORSE_API_PORT=9876
export ATLAS_API_PORT=9877
```

#### Memory Issues

```bash
# Limit test memory usage
export PYTEST_CURRENT_TEST=test_subset
pytest tests/ -k "not memory_heavy"

# Clean up between tests
pytest tests/ -x --disable-warnings
```

### Test Debugging Checklist

#### Before Debugging
- [ ] Test fails consistently
- [ ] Error message is clear
- [ ] Test isolation is working
- [ ] Mock setup is correct

#### During Debugging
- [ ] Run single test with `-v`
- [ ] Check mock call patterns
- [] Verify request/response data
- [ ] Check environment variables

#### After Debugging
- [ ] Fix identified issues
- [ ] Re-run specific test
- [] Run related tests to verify fix
- [] Update test if needed

## 📚 Test Documentation

### Test Documentation Sources

- **API Docs**: http://localhost:8765/docs
- **Coverage Reports**: `htmlcov/index.html`
- **Test Reports**: pytest output and logs
- **Source Code**: Comments in test files

### Updating Tests

When adding new features:

1. **Add unit tests** for new endpoints
2. **Update fixtures** if data structures change
3. **Add integration tests** for new workflows
4. **Update smoke tests** for new functionality
5. **Update documentation** with new test cases

### Test Maintenance

- **Regular updates**: Keep tests in sync with code changes
- **Coverage monitoring**: Track coverage trends over time
- **Performance monitoring**: Watch for regression
- **Security testing**: Validate new vulnerabilities

This comprehensive testing guide ensures that all TrojanHorse REST API functionality is thoroughly validated and maintained.