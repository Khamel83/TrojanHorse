"""Test OpenRouter embedding functionality."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import requests

from trojanhorse.rag import RAGIndex, EmbeddingError
from trojanhorse.config import Config


@pytest.fixture
def temp_state_dir():
    """Create a temporary state directory."""
    temp_dir = TemporaryDirectory()
    yield Path(temp_dir.name)
    temp_dir.cleanup()


@pytest.fixture
def openrouter_config(temp_state_dir):
    """Create a config object with OpenRouter embeddings."""
    return Config(
        vault_root=Path("/test/vault"),
        capture_dirs=[Path("/test/vault/Inbox")],
        processed_root=Path("/test/vault/Processed"),
        state_dir=temp_state_dir,
        openrouter_api_key="test_openrouter_key",
        openrouter_model="google/gemini-2.5-flash-lite-001",
        embedding_provider="openrouter",
        embedding_model_name="openai/text-embedding-3-small",
        embedding_api_key=None,
        embedding_api_base="https://api.openai.com/v1",
        openrouter_embedding_model="openai/text-embedding-3-small"
    )


@pytest.fixture
def openai_config(temp_state_dir):
    """Create a config object with OpenAI embeddings."""
    return Config(
        vault_root=Path("/test/vault"),
        capture_dirs=[Path("/test/vault/Inbox")],
        processed_root=Path("/test/vault/Processed"),
        state_dir=temp_state_dir,
        openrouter_api_key="test_openrouter_key",
        openrouter_model="google/gemini-2.5-flash-lite-001",
        embedding_provider="openai",
        embedding_model_name="text-embedding-3-small",
        embedding_api_key="test_openai_key",
        embedding_api_base="https://api.openai.com/v1",
        openrouter_embedding_model="openai/text-embedding-3-small"
    )


def test_openrouter_embedding_api_success(openrouter_config):
    """Test successful OpenRouter embedding API call."""
    rag_index = RAGIndex(openrouter_config.state_dir, openrouter_config)

    # Mock the requests.post call for OpenRouter
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "data": [
            {"embedding": [0.1, 0.2, 0.3]}
        ]
    }

    with patch('trojanhorse.rag.requests.post', return_value=mock_response) as mock_post:
        result = rag_index._generate_openrouter_embedding("test text")

        # Verify the correct API endpoint was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "openrouter.ai/api/v1/embeddings" in call_args[0][0]

        # Verify headers
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test_openrouter_key"
        assert headers["HTTP-Referer"] == "https://github.com/Khamel83/TrojanHorse"
        assert headers["X-Title"] == "TrojanHorse Note Processor"

        # Verify data
        data = call_args[1]["json"]
        assert data["model"] == "openai/text-embedding-3-small"
        assert data["input"] == "test text"

        # Verify result
        assert result == [0.1, 0.2, 0.3]


def test_openrouter_embedding_no_api_key(openrouter_config):
    """Test OpenRouter embedding with no API key."""
    config_no_key = Config(
        vault_root=openrouter_config.vault_root,
        capture_dirs=openrouter_config.capture_dirs,
        processed_root=openrouter_config.processed_root,
        state_dir=openrouter_config.state_dir,
        openrouter_api_key="",  # No API key
        openrouter_model=openrouter_config.openrouter_model,
        embedding_provider="openrouter",
        embedding_model_name=openrouter_config.embedding_model_name,
        embedding_api_key=None,
        embedding_api_base=openrouter_config.embedding_api_base,
        openrouter_embedding_model=openrouter_config.openrouter_embedding_model
    )

    rag_index = RAGIndex(config_no_key.state_dir, config_no_key)

    with pytest.raises(EmbeddingError, match="No OpenRouter API key configured"):
        rag_index._generate_openrouter_embedding("test text")


def test_openrouter_embedding_api_error(openrouter_config):
    """Test OpenRouter embedding API error handling."""
    rag_index = RAGIndex(openrouter_config.state_dir, openrouter_config)

    with patch('trojanhorse.rag.requests.post') as mock_post:
        mock_post.side_effect = requests.RequestException("Network error")

        with pytest.raises(EmbeddingError, match="OpenRouter embedding API request failed"):
            rag_index._generate_openrouter_embedding("test text")


def test_openrouter_embedding_invalid_response(openrouter_config):
    """Test OpenRouter embedding with invalid response."""
    rag_index = RAGIndex(openrouter_config.state_dir, openrouter_config)

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"invalid": "response"}

    with patch('trojanhorse.rag.requests.post', return_value=mock_response):
        with pytest.raises(EmbeddingError, match="Invalid OpenRouter embedding response format"):
            rag_index._generate_openrouter_embedding("test text")


def test_embedding_provider_routing_openrouter(openrouter_config):
    """Test that openrouter provider routes to OpenRouter embedding."""
    rag_index = RAGIndex(openrouter_config.state_dir, openrouter_config)

    # Mock OpenRouter embedding
    with patch.object(rag_index, '_generate_openrouter_embedding', return_value=[0.1, 0.2]) as mock_openrouter:
        with patch.object(rag_index, '_generate_openai_embedding') as mock_openai:
            result = rag_index._generate_embedding_api("test text")

            mock_openrouter.assert_called_once_with("test text")
            mock_openai.assert_not_called()
            assert result == [0.1, 0.2]


def test_embedding_provider_routing_openai(openai_config):
    """Test that openai provider routes to OpenAI embedding."""
    rag_index = RAGIndex(openai_config.state_dir, openai_config)

    # Mock OpenAI embedding
    with patch.object(rag_index, '_generate_openai_embedding', return_value=[0.1, 0.2]) as mock_openai:
        with patch.object(rag_index, '_generate_openrouter_embedding') as mock_openrouter:
            result = rag_index._generate_embedding_api("test text")

            mock_openai.assert_called_once_with("test text")
            mock_openrouter.assert_not_called()
            assert result == [0.1, 0.2]