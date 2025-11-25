"""Pytest configuration and fixtures for TrojanHorse API tests."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import json
from datetime import datetime

from ..config import Config
from ..processor import Processor, ProcessingStats
from ..rag import RAGIndex
from ..index_db import IndexDB
from ..models import NoteMeta


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def test_config(temp_dir):
    """Create a test configuration."""
    from pathlib import Path

    # Create directories
    vault_path = temp_dir / "vault"
    inbox_path = vault_path / "Inbox"
    processed_path = temp_dir / "processed"
    state_path = temp_dir / "state"

    for path in [vault_path, inbox_path, processed_path, state_path]:
        path.mkdir(parents=True, exist_ok=True)

    return Config(
        vault_root=vault_path,
        capture_dirs=[inbox_path],
        processed_root=processed_path,
        state_dir=state_path,
        openrouter_api_key="test-key",
        openrouter_model="test-model",
        embedding_provider="test-provider",
        embedding_model_name="test-embedding-model",
        embedding_api_key="test-embedding-key",
        embedding_api_base="test-base",
        openrouter_embedding_model="test-embedding-model"
    )


@pytest.fixture
def mock_processor():
    """Create a mock processor."""
    from datetime import datetime, timedelta

    processor = Mock(spec=Processor)
    stats = ProcessingStats()
    stats.files_scanned = 10
    stats.files_processed = 5
    stats.files_skipped = 5
    stats.errors = []
    # Mock the duration to return a specific value
    stats.finish()  # Set end_time
    # Override the duration property with a specific value for testing
    type(stats).duration_seconds = property(lambda self: 15.5)
    processor.process_once.return_value = stats
    return processor


@pytest.fixture
def mock_rag_index():
    """Create a mock RAG index."""
    rag_index = Mock(spec=RAGIndex)
    rag_index.get_stats.return_value = {
        "total_notes": 100,
        "categories": {"meeting": 20, "idea": 15, "task": 10},
        "projects": {"project-x": 25, "project-y": 15, "none": 60}
    }
    rag_index.close = Mock()
    return rag_index


@pytest.fixture
def mock_index_db():
    """Create a mock index database."""
    db = Mock(spec=IndexDB)
    db.get_all_files = Mock(return_value=[
        {
            "id": "test-note-1",
            "original_path": "/test/path1.md",
            "dest_path": "/test/dest1.md",
            "mtime": 1642248000.0
        },
        {
            "id": "test-note-2",
            "original_path": "/test/path2.md",
            "dest_path": "/test/dest2.md",
            "mtime": 1642248100.0
        }
    ])
    db.get_file_by_id = Mock(return_value={
        "id": "test-note-1",
        "original_path": "/test/path1.md",
        "dest_path": "/test/dest1.md",
        "mtime": 1642248000.0
    })
    db.get_stats = Mock(return_value={
        "total_files": 2,
        "processed_files": 2,
        "categories": {"meeting": 1, "idea": 1},
        "projects": {"project-x": 1, "project-y": 1}
    })
    return db


@pytest.fixture
def sample_note_metadata():
    """Sample note metadata for testing."""
    return NoteMeta(
        id="test-note-123",
        source="drafts",
        raw_type="meeting_transcript",
        class_type="work",
        category="meeting",
        project="project-x",
        created_at=datetime(2024, 1, 15, 14, 30, 0),
        processed_at=datetime(2024, 1, 15, 14, 35, 0),
        summary="Weekly project sync meeting",
        tags=["project-x", "sync", "weekly"],
        original_path="/test/inbox/test-note.md",
        dest_path="/test/processed/work/meetings/2024/test-note.md"
    )


@pytest.fixture
def sample_note_content():
    """Sample note content for testing."""
    return {
        "meta": {
            "title": "Project Sync Meeting",
            "meeting_type": "weekly_sync",
            "duration_minutes": 45,
            "attendees": ["John", "Sarah", "Mike"]
        },
        "body": "# Project Sync Meeting\n\n## Attendees\n- John (PM)\n- Sarah (Dev)\n\n## Discussion\nDiscussed project timeline and deliverables."
    }


@pytest.fixture
def sample_promoted_note():
    """Sample note payload for Atlas promotion."""
    return {
        "id": "test-note-123",
        "path": "/test/processed/work/meetings/2024/test-note.md",
        "title": "Project Sync Meeting",
        "source": "drafts",
        "raw_type": "meeting_transcript",
        "class_type": "work",
        "category": "meeting",
        "project": "project-x",
        "tags": ["project-x", "sync", "weekly"],
        "created_at": "2024-01-15T14:30:00.000Z",
        "updated_at": "2024-01-15T14:35:00.000Z",
        "summary": "Weekly project sync meeting",
        "body": "# Project Sync Meeting\n\n## Attendees\n- John (PM)",
        "frontmatter": {
            "meeting_type": "weekly_sync",
            "duration_minutes": 45
        }
    }


@pytest.fixture
def mock_rag_response():
    """Sample RAG query response."""
    return {
        "answer": "Based on the meeting notes, the project timeline was extended by 2 weeks due to technical challenges.",
        "sources": [
            {
                "note_id": "test-note-123",
                "title": "Project Sync Meeting",
                "relevance_score": 0.89
            }
        ],
        "contexts": [
            {
                "note_id": "test-note-123",
                "path": "/test/processed/work/meetings/2024/test-note.md",
                "similarity": 0.89,
                "content_snippet": "## Timeline Decision\nAfter discussing challenges, we agreed to extend timeline by 2 weeks..."
            }
        ]
    }


@pytest.fixture
def sample_notes_list():
    """Sample list of notes for testing."""
    return [
        {
            "id": "note-1",
            "source": "drafts",
            "raw_type": "meeting_transcript",
            "class_type": "work",
            "category": "meeting",
            "project": "project-x",
            "created_at": "2024-01-15T14:30:00.000Z",
            "processed_at": "2024-01-15T14:35:00.000Z",
            "summary": "Project sync meeting",
            "tags": ["project-x"],
            "original_path": "/test/inbox/note-1.md",
            "dest_path": "/test/processed/note-1.md"
        },
        {
            "id": "note-2",
            "source": "macwhisper",
            "raw_type": "voice_note",
            "class_type": "personal",
            "category": "idea",
            "project": "none",
            "created_at": "2024-01-15T10:00:00.000Z",
            "processed_at": "2024-01-15T10:05:00.000Z",
            "summary": "New idea for mobile app",
            "tags": ["idea", "mobile"],
            "original_path": "/test/transcripts/note-2.mp3",
            "dest_path": "/test/processed/idea-2.md"
        }
    ]


@pytest.fixture
def create_test_file(temp_dir):
    """Helper function to create test files."""
    def _create_file(filename: str, content: str = "Test content"):
        file_path = temp_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return file_path
    return _create_file


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("WORKVAULT_ROOT", "/test/vault")
    monkeypatch.setenv("TROJANHORSE_STATE_DIR", "/test/state")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "test-model")
    return monkeypatch


@pytest.fixture
def sample_ask_request():
    """Sample ask request payload."""
    return {
        "question": "What did we decide about the project timeline?",
        "top_k": 5,
        "workspace": "work",
        "category": "meeting"
    }


@pytest.fixture
def sample_promote_request():
    """Sample promote request payload."""
    return {
        "note_ids": ["note-1", "note-2", "note-3"]
    }


# Test client fixture
@pytest.fixture
def test_client():
    """Create a test client for FastAPI app."""
    from fastapi.testclient import TestClient
    from ..api_server import app

    # Mock app state
    app.state.config = Mock()
    app.state.index_db = Mock()
    app.state.rag_index = Mock()

    return TestClient(app)


# Async test client fixture
@pytest.fixture
async def async_test_client():
    """Create an async test client for FastAPI app."""
    import httpx
    from ..api_server import app

    # Mock app state
    app.state.config = Mock()
    app.state.index_db = Mock()
    app.state.rag_index = Mock()

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client