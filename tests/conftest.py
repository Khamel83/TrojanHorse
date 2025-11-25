"""Pytest configuration and fixtures."""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock


@pytest.fixture(autouse=True)
def test_env_vars(monkeypatch):
    """Set up test environment variables."""
    # Prevent loading of real .env files during tests
    monkeypatch.delenv("WORKVAULT_ROOT", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL_NAME", raising=False)


@pytest.fixture
def mock_openrouter_response():
    """Mock OpenRouter API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "Test response from LLM"
                }
            }
        ]
    }


@pytest.fixture
def mock_embedding_response():
    """Mock embedding API response."""
    return {
        "data": [
            {
                "embedding": [0.1] * 1536  # Dummy embedding vector
            }
        ]
    }