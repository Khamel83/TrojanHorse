"""Tests for TrojanHorse Atlas client."""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
import requests

from ..atlas_client import AtlasClient, promote_notes_from_trojanhorse, get_atlas_client


class TestAtlasClient:
    """Test the AtlasClient class."""

    def test_init_with_url_only(self):
        """Test client initialization with URL only."""
        client = AtlasClient("http://localhost:8787")
        assert client.atlas_url == "http://localhost:8787"
        assert client.api_key is None
        assert client.timeout == 60

    def test_init_with_url_and_api_key(self):
        """Test client initialization with URL and API key."""
        client = AtlasClient("http://localhost:8787", "test-key")
        assert client.atlas_url == "http://localhost:8787"
        assert client.api_key == "test-key"

    def test_init_with_env_api_key(self, monkeypatch):
        """Test client initialization with environment API key."""
        monkeypatch.setenv("ATLAS_API_KEY", "env-key")
        client = AtlasClient("http://localhost:8787")
        assert client.api_key == "env-key"

    def test_init_with_custom_timeout(self):
        """Test client initialization with custom timeout."""
        client = AtlasClient("http://localhost:8787", timeout=120)
        assert client.timeout == 120

    def test_url_normalization(self):
        """Test URL normalization."""
        client = AtlasClient("http://localhost:8787/")
        assert client.atlas_url == "http://localhost:8787"

    @patch('TrojanHorse.atlas_client.requests.Session.get')
    def test_health_check_success(self, mock_get):
        """Test successful health check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client = AtlasClient("http://localhost:8787")
        result = client.health_check()

        assert result is True
        mock_get.assert_called_once_with("http://localhost:8787/health", timeout=10)

    @patch('TrojanHorse.atlas_client.requests.Session.get')
    def test_health_check_failure(self, mock_get):
        """Test health check failure."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        client = AtlasClient("http://localhost:8787")
        result = client.health_check()

        assert result is False

    @patch('TrojanHorse.atlas_client.requests.Session.get')
    def test_health_check_exception(self, mock_get):
        """Test health check with exception."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        client = AtlasClient("http://localhost:8787")
        result = client.health_check()

        assert result is False

    @patch('TrojanHorse.atlas_client.requests.Session.post')
    def test_ingest_notes_success(self, mock_post):
        """Test successful notes ingestion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "count": 3}
        mock_post.return_value = mock_response

        client = AtlasClient("http://localhost:8787")
        notes = [
            {"id": "note1", "title": "Note 1", "body": "Content 1"},
            {"id": "note2", "title": "Note 2", "body": "Content 2"},
            {"id": "note3", "title": "Note 3", "body": "Content 3"}
        ]

        result = client.ingest_notes(notes)

        assert result is True
        mock_post.assert_called_once_with(
            "http://localhost:8787/ingest/batch",
            json=notes,
            timeout=60
        )

    @patch('TrojanHorse.atlas_client.requests.Session.post')
    def test_ingest_notes_with_api_key(self, mock_post):
        """Test notes ingestion with API key."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "count": 1}
        mock_post.return_value = mock_response

        client = AtlasClient("http://localhost:8787", "test-key")
        notes = [{"id": "note1", "title": "Note 1", "body": "Content 1"}]

        client.ingest_notes(notes)

        # Verify API key header is set
        headers = mock_post.call_args[1]['headers']
        assert 'X-API-Key' in headers
        assert headers['X-API-Key'] == 'test-key'

    @patch('TrojanHorse.atlas_client.requests.Session.post')
    def test_ingest_notes_http_error(self, mock_post):
        """Test notes ingestion with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Invalid request"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400 Client Error")
        mock_post.return_value = mock_response

        client = AtlasClient("http://localhost:8787")
        notes = [{"id": "note1", "title": "Note 1", "body": "Content 1"}]

        result = client.ingest_notes(notes)

        assert result is False

    @patch('TrojanHorse.atlas_client.requests.Session.post')
    def test_ingest_notes_connection_error(self, mock_post):
        """Test notes ingestion with connection error."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        client = AtlasClient("http://localhost:8787")
        notes = [{"id": "note1", "title": "Note 1", "body": "Content 1"}]

        result = client.ingest_notes(notes)

        assert result is False

    @patch('TrojanHorse.atlas_client.requests.Session.post')
    def test_ingest_notes_timeout(self, mock_post):
        """Test notes ingestion with timeout."""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        client = AtlasClient("http://localhost:8787")
        notes = [{"id": "note1", "title": "Note 1", "body": "Content 1"}]

        result = client.ingest_notes(notes)

        assert result is False


class TestAtlasClientIntegration:
    """Test Atlas client integration functions."""

    @patch('TrojanHorse.atlas_client.AtlasClient')
    def test_get_atlas_client_with_env(self, mock_client_class, monkeypatch):
        """Test get_atlas_client with environment variable."""
        monkeypatch.setenv("ATLAS_API_URL", "http://localhost:8787")
        monkeypatch.setenv("ATLAS_API_KEY", "test-key")

        result = get_atlas_client()

        assert result is not None
        mock_client_class.assert_called_once_with("http://localhost:8787", "test-key")

    @patch('TrojanHorse.atlas_client.AtlasClient')
    def test_get_atlas_client_without_env(self, mock_client_class, monkeypatch):
        """Test get_atlas_client without environment variables."""
        monkeypatch.delenv("ATLAS_API_URL", raising=False)

        result = get_atlas_client()

        assert result is None
        mock_client_class.assert_not_called()

    @patch('TrojanHorse.atlas_client.get_atlas_client')
    def test_promote_notes_from_trojanhorse_success(self, mock_get_client, monkeypatch):
        """Test successful promotion from TrojanHorse."""
        # Setup environment and mocks
        monkeypatch.setenv("ATLAS_API_URL", "http://localhost:8787")

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.health_check.return_value = True
        mock_client.ingest_notes.return_value = True

        # Mock TrojanHorse API response
        mock_promote_response = Mock()
        mock_promote_response.json.return_value = {
            "items": [
                {"id": "note1", "title": "Note 1", "body": "Content 1"},
                {"id": "note2", "title": "Note 2", "body": "Content 2"}
            ]
        }

        with patch('TrojanHorse.atlas_client.requests.post') as mock_post:
            mock_post.return_value = mock_promote_response

            result = promote_notes_from_trojanhorse(
                "http://localhost:8765",
                mock_client,
                ["note1", "note2"]
            )

        assert result == 2
        mock_client.health_check.assert_called_once()
        mock_client.ingest_notes.assert_called_once()

    @patch('TrojanHorse.atlas_client.get_atlas_client')
    def test_promote_notes_no_client(self, mock_get_client, monkeypatch):
        """Test promotion when Atlas client is not configured."""
        monkeypatch.delenv("ATLAS_API_URL", raising=False)
        mock_get_client.return_value = None

        result = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            None,
            ["note1", "note2"]
        )

        assert result == 0

    @patch('TrojanHorse.atlas_client.get_atlas_client')
    def test_promote_notes_atlas_unhealthy(self, mock_get_client, monkeypatch):
        """Test promotion when Atlas API is unhealthy."""
        monkeypatch.setenv("ATLAS_API_URL", "http://localhost:8787")

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.health_check.return_value = False

        result = promote_notes_from_trojanhorse(
            "http://localhost:8765",
            mock_client,
            ["note1", "note2"]
        )

        assert result == 0
        mock_client.health_check.assert_called_once()
        mock_client.ingest_notes.assert_not_called()

    @patch('TrojanHorse.atlas_client.get_atlas_client')
    def test_promote_notes_trojanhorse_error(self, mock_get_client, monkeypatch):
        """Test promotion with TrojanHorse API error."""
        monkeypatch.setenv("ATLAS_API_URL", "http://localhost:8787")

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.health_check.return_value = True

        with patch('TrojanHorse.atlas_client.requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

            result = promote_notes_from_trojanhorse(
                "http://localhost:8765",
                mock_client,
                ["note1", "note2"]
            )

        assert result == 0

    @patch('TrojanHorse.atlas_client.get_atlas_client')
    def test_promote_notes_atlas_ingest_error(self, mock_get_client, monkeypatch):
        """Test promotion with Atlas ingestion error."""
        monkeypatch.setenv("ATLAS_API_URL", "http://localhost:8787")

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.health_check.return_value = True
        mock_client.ingest_notes.return_value = False

        # Mock TrojanHorse API response
        mock_promote_response = Mock()
        mock_promote_response.json.return_value = {
            "items": [{"id": "note1", "title": "Note 1", "body": "Content 1"}]
        }

        with patch('TrojanHorse.atlas_client.requests.post') as mock_post:
            mock_post.return_value = mock_promote_response

            result = promote_notes_from_trojanhorse(
                "http://localhost:8765",
                mock_client,
                ["note1"]
            )

        assert result == 0


class TestAtlasClientErrorHandling:
    """Test Atlas client error handling scenarios."""

    @patch('TrojanHorse.atlas_client.requests.Session.post')
    def test_ingest_notes_response_body_access(self, mock_post):
        """Test error when response body can't be accessed."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        client = AtlasClient("http://localhost:8787")
        notes = [{"id": "note1", "title": "Note 1", "body": "Content 1"}]

        result = client.ingest_notes(notes)

        assert result is False

    @patch('TrojanHorse.atlas_client.requests.Session.get')
    def test_health_check_invalid_response(self, mock_get):
        """Test health check with invalid response."""
        mock_get.side_effect = requests.exceptions.RequestException("Invalid response")

        client = AtlasClient("http://localhost:8787")
        result = client.health_check()

        assert result is False

    def test_client_session_management(self):
        """Test that client properly manages HTTP session."""
        with patch('TrojanHorse.atlas_client.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            client = AtlasClient("http://localhost:8787", "test-key")

            # Verify session is created
            mock_session_class.assert_called_once()

            # Verify headers are set with API key
            assert 'X-API-Key' in mock_session.headers
            assert mock_session.headers['X-API-Key'] == 'test-key'

    @patch('TrojanHorse.atlas_client.requests.Session.post')
    def test_ingest_notes_empty_list(self, mock_post):
        """Test ingesting empty notes list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "count": 0}
        mock_post.return_value = mock_response

        client = AtlasClient("http://localhost:8787")
        result = client.ingest_notes([])

        assert result is True
        mock_post.assert_called_once_with(
            "http://localhost:8787/ingest/batch",
            json=[],
            timeout=60
        )


class TestAtlasClientTimeouts:
    """Test Atlas client timeout behavior."""

    @patch('TrojanHorse.atlas_client.requests.Session.post')
    def test_health_check_timeout(self, mock_get):
        """Test health check with custom timeout."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        client = AtlasClient("http://localhost:8787")
        result = client.health_check()

        assert result is False
        mock_get.assert_called_once_with("http://localhost:8787/health", timeout=10)

    @patch('TrojanHorse.atlas_client.requests.Session.post')
    def test_ingest_notes_custom_timeout(self, mock_post):
        """Test notes ingestion with custom timeout."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "count": 1}
        mock_post.return_value = mock_response

        client = AtlasClient("http://localhost:8787", timeout=120)
        notes = [{"id": "note1", "title": "Note 1", "body": "Content 1"}]

        result = client.ingest_notes(notes)

        assert result is True
        mock_post.assert_called_once_with(
            "http://localhost:8787/ingest/batch",
            json=notes,
            timeout=120
        )


class TestPromotionWorkflow:
    """Test complete promotion workflow."""

    @patch('TrojanHorse.atlas_client.promote_notes_from_trojanhorse')
    @patch('TrojanHorse.atlas_client.get_atlas_client')
    def test_complete_promotion_workflow(self, mock_get_client, mock_promote, monkeypatch):
        """Test complete promotion workflow setup."""
        monkeypatch.setenv("ATLAS_API_URL", "http://localhost:8787")
        monkeypatch.setenv("ATLAS_API_KEY", "test-key")

        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_promote.return_value = 3

        # Simulate the promotion process
        note_ids = ["note1", "note2", "note3"]
        trojanhorse_url = "http://localhost:8765"

        count = promote_notes_from_trojanhorse(trojanhorse_url, mock_client, note_ids)

        assert count == 3
        mock_promote.assert_called_once_with(trojanhorse_url, mock_client, note_ids)

    def test_promotion_workflow_env_setup(self):
        """Test that environment variables are properly set for promotion."""
        env_vars = {
            "ATLAS_API_URL": "http://localhost:8787",
            "ATLAS_API_KEY": "test-key"
        }

        for key, value in env_vars.items():
            import os
            os.environ[key] = value

        client = get_atlas_client()
        assert client is not None
        assert client.atlas_url == "http://localhost:8787"
        assert client.api_key == "test-key"