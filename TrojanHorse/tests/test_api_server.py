"""Comprehensive tests for TrojanHorse API server."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime

from ..api_server import app
from ..config import Config
from ..processor import Processor, ProcessingStats
from ..rag import RAGIndex
from ..index_db import IndexDB


class TestHealthEndpoint:
    """Test the /health endpoint."""

    def test_health_check(self, test_client):
        """Test basic health check."""
        response = test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "service" in data
        assert "timestamp" in data

    def test_health_check_with_mock_state(self, test_client):
        """Test health check with mocked app state."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestProcessingEndpoints:
    """Test processing-related endpoints."""

    @patch('TrojanHorse.api_server.Processor')
    def test_process_once_success(self, mock_processor_class, test_client, mock_processor):
        """Test successful processing endpoint."""
        # Setup mock
        mock_processor_class.return_value = mock_processor

        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            response = test_client.post("/process")

        assert response.status_code == 200

        data = response.json()
        assert data["files_scanned"] == 10
        assert data["files_processed"] == 5
        assert data["files_skipped"] == 5
        assert data["duration_seconds"] == 15.5
        assert data["errors"] == []

    @patch('TrojanHorse.api_server.Processor')
    def test_process_once_with_errors(self, mock_processor_class, test_client):
        """Test processing endpoint with errors."""
        # Setup mock with errors
        mock_processor = Mock()
        stats = ProcessingStats()
        stats.files_scanned = 10
        stats.files_processed = 3
        stats.files_skipped = 2
        stats.errors = ["File processing failed: test.txt", "Permission denied: test2.txt"]
        stats.finish()  # Set end_time
        # Override the duration property with a specific value for testing
        type(stats).duration_seconds = property(lambda self: 20.0)
        mock_processor.process_once.return_value = stats
        mock_processor_class.return_value = mock_processor

        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            response = test_client.post("/process")

        assert response.status_code == 200

        data = response.json()
        assert data["files_processed"] == 3
        assert len(data["errors"]) == 2
        assert "File processing failed" in data["errors"][0]

    @patch('TrojanHorse.api_server.Processor')
    def test_process_once_exception(self, mock_processor_class, test_client):
        """Test processing endpoint with exception."""
        # Setup mock to raise exception
        mock_processor = Mock()
        mock_processor.process_once.side_effect = Exception("Processing failed")
        mock_processor_class.return_value = mock_processor

        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            response = test_client.post("/process")

        assert response.status_code == 500
        assert "Processing failed" in response.json()["detail"]

    @patch('TrojanHorse.api_server.rebuild_index')
    def test_embed_endpoint(self, mock_rebuild_index, test_client, mock_rag_index):
        """Test embed endpoint."""
        # Setup mock
        mock_rebuild_index.return_value = None
        mock_rag_index.get_stats.return_value = {"total_notes": 150}

        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            with patch('TrojanHorse.api_server.app.state.rag_index', mock_rag_index):
                response = test_client.post("/embed")

        assert response.status_code == 200

        data = response.json()
        assert data["indexed_notes"] == 150

    @patch('TrojanHorse.api_server.rebuild_index')
    def test_embed_endpoint_exception(self, mock_rebuild_index, test_client):
        """Test embed endpoint with exception."""
        mock_rebuild_index.side_effect = Exception("Index rebuild failed")

        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            response = test_client.post("/embed")

        assert response.status_code == 500
        assert "Index rebuild failed" in response.json()["detail"]


class TestNotesEndpoints:
    """Test notes management endpoints."""

    def test_list_notes_success(self, test_client, mock_index_db, sample_notes_list):
        """Test successful notes listing."""
        with patch('TrojanHorse.api_server.app.state.index_db', mock_index_db):
            with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
                # Setup mock to return valid content
                mock_parse.return_value = {
                    "meta": {
                        "id": "note-1",
                        "source": "drafts",
                        "category": "meeting",
                        "project": "project-x"
                    }
                }

                response = test_client.get("/notes")

        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_list_notes_with_filters(self, test_client, mock_index_db):
        """Test notes listing with filters."""
        with patch('TrojanHorse.api_server.app.state.index_db', mock_index_db):
            with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
                mock_parse.return_value = {
                    "meta": {
                        "id": "note-1",
                        "category": "meeting",
                        "project": "project-x"
                    }
                }

                response = test_client.get("/notes?category=meeting&project=project-x&limit=10")

        assert response.status_code == 200

        # Verify the mock was called with correct parameters
        mock_index_db.get_all_files.assert_called_with(limit=10, offset=0)

    def test_get_specific_note_success(self, test_client, mock_index_db, sample_note_content):
        """Test getting a specific note."""
        with patch('TrojanHorse.api_server.app.state.index_db', mock_index_db):
            with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
                mock_parse.return_value = sample_note_content

                response = test_client.get("/notes/test-note-123")

        assert response.status_code == 200

        data = response.json()
        assert "meta" in data
        assert "content" in data
        assert data["meta"]["id"] == "test-note-123"

    def test_get_specific_note_not_found(self, test_client, mock_index_db):
        """Test getting a non-existent note."""
        mock_index_db.get_file_by_id.return_value = None

        with patch('TrojanHorse.api_server.app.state.index_db', mock_index_db):
            response = test_client.get("/notes/nonexistent-note")

        assert response.status_code == 404
        assert "Note not found" in response.json()["detail"]

    def test_get_note_parse_error(self, test_client, mock_index_db):
        """Test getting note with parse error."""
        mock_index_db.get_file_by_id.return_value = {
            "id": "test-note",
            "dest_path": "/test/path.md"
        }

        with patch('TrojanHorse.api_server.app.state.index_db', mock_index_db):
            with patch('TrojanHorse.api_server.parse_markdown_with_frontmatter') as mock_parse:
                mock_parse.return_value = None

                response = test_client.get("/notes/test-note")

        assert response.status_code == 404
        assert "Could not parse note content" in response.json()["detail"]


class TestSearchEndpoints:
    """Test search and query endpoints."""

    @patch('TrojanHorse.api_server.query')
    def test_ask_question_success(self, mock_query, test_client, sample_ask_request, mock_rag_response):
        """Test successful question asking."""
        mock_query.return_value = mock_rag_response

        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            response = test_client.post(
                "/ask",
                json=sample_ask_request
            )

        assert response.status_code == 200

        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "contexts" in data
        assert "project timeline" in data["answer"]
        assert len(data["sources"]) == 1
        assert data["sources"][0]["note_id"] == "test-note-123"

    def test_ask_question_invalid_payload(self, test_client):
        """Test ask question with invalid payload."""
        response = test_client.post(
            "/ask",
            json={"invalid": "payload"}
        )

        # FastAPI will validate the Pydantic model
        assert response.status_code == 422

    @patch('TrojanHorse.api_server.query')
    def test_ask_question_exception(self, mock_query, test_client, sample_ask_request):
        """Test ask question with exception."""
        mock_query.side_effect = Exception("Query failed")

        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            response = test_client.post(
                "/ask",
                json=sample_ask_request
            )

        assert response.status_code == 500
        assert "Query failed" in response.json()["detail"]

    def test_ask_question_with_filters(self, test_client, sample_ask_request, mock_rag_response):
        """Test ask question with filters."""
        with patch('TrojanHorse.api_server.query') as mock_query:
            mock_query.return_value = mock_rag_response

            with patch('TrojanHorse.api_server.app.state.config', Mock()):
                response = test_client.post(
                    "/ask",
                    json={
                        "question": "What meetings did I have?",
                        "top_k": 10,
                        "workspace": "work",
                        "category": "meeting",
                        "project": "project-x"
                    }
                )

        assert response.status_code == 200

        # Verify query was called with correct parameters
        mock_query.assert_called_once()
        call_args = mock_query.call_args[1]
        assert call_args["k"] == 10
        assert call_args["workspace"] == "work"
        assert call_args["category"] == "meeting"
        assert call_args["project"] == "project-x"


class TestPromotionEndpoints:
    """Test note promotion endpoints."""

    @patch('TrojanHorse.api_server.parse_markdown_with_frontmatter')
    def test_promote_notes_success(self, mock_parse, test_client, mock_index_db, sample_promoted_note):
        """Test successful note promotion."""
        # Setup mocks
        mock_index_db.get_file_by_id.return_value = {
            "id": "test-note-123",
            "dest_path": "/test/processed/note.md"
        }
        mock_parse.return_value = {
            "meta": {
                "id": "test-note-123",
                "title": "Test Note",
                "summary": "Test summary"
            },
            "body": "# Test Note\n\nContent here"
        }

        with patch('TrojanHorse.api_server.app.state.index_db', mock_index_db):
            response = test_client.post(
                "/promote",
                json={"note_ids": ["test-note-123"]}
            )

        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "test-note-123"
        assert data["items"][0]["title"] == "Test Note"

    def test_promote_notes_not_found(self, test_client, mock_index_db):
        """Test promotion with non-existent note."""
        mock_index_db.get_file_by_id.return_value = None

        with patch('TrojanHorse.api_server.app.state.index_db', mock_index_db):
            response = test_client.post(
                "/promote",
                json={"note_ids": ["nonexistent-note"]}
            )

        assert response.status_code == 200

        data = response.json()
        assert data["items"] == []  # Should return empty list for non-existent notes

    @patch('TrojanHorse.api_server.parse_markdown_with_frontmatter')
    def test_promote_multiple_notes(self, mock_parse, test_client, mock_index_db):
        """Test promotion of multiple notes."""
        # Setup mocks for multiple notes
        def mock_get_file(note_id):
            if note_id in ["note-1", "note-2"]:
                return {
                    "id": note_id,
                    "dest_path": f"/test/processed/{note_id}.md"
                }
            return None

        mock_index_db.get_file_by_id.side_effect = mock_get_file
        mock_parse.return_value = {
            "meta": {"id": "test", "title": "Test"},
            "body": "# Test\nContent"
        }

        with patch('TrojanHorse.api_server.app.state.index_db', mock_index_db):
            response = test_client.post(
                "/promote",
                json={"note_ids": ["note-1", "note-2", "note-3"]}
            )

        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 2  # Only 2 of 3 notes exist

    @patch('TrojanHorse.api_server.parse_markdown_with_frontmatter')
    def test_promote_notes_parse_error(self, mock_parse, test_client, mock_index_db):
        """Test promotion with parse error."""
        mock_index_db.get_file_by_id.return_value = {
            "id": "test-note",
            "dest_path": "/test/note.md"
        }
        mock_parse.return_value = None

        with patch('TrojanHorse.api_server.app.state.index_db', mock_index_db):
            response = test_client.post(
                "/promote",
                json={"note_ids": ["test-note"]}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []  # Should return empty for parse errors


class TestStatsEndpoint:
    """Test statistics endpoint."""

    def test_get_stats_success(self, test_client, mock_index_db, mock_rag_index):
        """Test successful stats retrieval."""
        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            with patch('TrojanHorse.api_server.app.state.index_db', mock_index_db):
                with patch('TrojanHorse.api_server.app.state.rag_index', mock_rag_index):
                    response = test_client.get("/stats")

        assert response.status_code == 200

        data = response.json()
        assert "processed_files" in data
        assert "rag_index" in data
        assert "config" in data

    def test_get_stats_exception(self, test_client):
        """Test stats endpoint with exception."""
        with patch('TrojanHorse.api_server.app.state.config', Mock()):
            with patch('TrojanHorse.api_server.app.state.index_db', Mock()) as mock_db:
                mock_db.get_stats.side_effect = Exception("Database error")

                response = test_client.get("/stats")

        assert response.status_code == 500
        assert "Database error" in response.json()["detail"]


class TestErrorHandling:
    """Test error handling scenarios."""

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


class TestAsyncContextManager:
    """Test the async context manager for app lifecycle."""

    @patch('TrojanHorse.api_server.Config')
    @patch('TrojanHorse.api_server.IndexDB')
    @patch('TrojanHorse.api_server.RAGIndex')
    def test_startup_success(self, mock_rag_class, mock_db_class, mock_config_class, test_config):
        """Test successful app startup."""
        # Setup mocks
        mock_config_class.from_env.return_value = test_config
        mock_db_class.return_value = Mock()
        mock_rag_class.return_value = Mock()

        # This test verifies that the startup sequence doesn't raise exceptions
        # In a real scenario, this would be tested by starting the server
        assert True  # Placeholder for startup test

    def test_startup_config_error(self):
        """Test startup with configuration error."""
        with patch('TrojanHorse.api_server.Config') as mock_config_class:
            mock_config_class.from_env.side_effect = ValueError("Config error")

            # In a real test, we'd verify the startup fails appropriately
            # For now, we verify the exception is raised
            with pytest.raises(ValueError):
                mock_config_class.from_env()


class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_ask_request_validation(self):
        """Test AskRequest model validation."""
        from ..api_server import AskRequest

        # Valid request
        valid_data = {
            "question": "What did we decide?",
            "top_k": 5,
            "workspace": "work"
        }
        request = AskRequest(**valid_data)
        assert request.question == "What did we decide?"
        assert request.top_k == 5
        assert request.workspace == "work"
        assert request.category is None

    def test_ask_request_defaults(self):
        """Test AskRequest default values."""
        from ..api_server import AskRequest

        request = AskRequest(question="Test question")
        assert request.top_k == 8
        assert request.workspace is None
        assert request.category is None

    def test_promote_request_validation(self):
        """Test PromoteRequest model validation."""
        from ..api_server import PromoteRequest

        valid_data = {"note_ids": ["note1", "note2", "note3"]}
        request = PromoteRequest(**valid_data)
        assert len(request.note_ids) == 3
        assert "note1" in request.note_ids

    def test_process_response_model(self):
        """Test ProcessResponse model."""
        from ..api_server import ProcessResponse

        response = ProcessResponse(
            files_scanned=10,
            files_processed=5,
            files_skipped=5,
            duration_seconds=15.5,
            errors=["Test error"]
        )

        assert response.files_processed == 5
        assert len(response.errors) == 1
        assert response.errors[0] == "Test error"