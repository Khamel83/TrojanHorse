"""Tests for the classifier module."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from trojanhorse.classifier import Classifier, ClassificationResult
from trojanhorse.llm_client import LLMClient, LLMClientError


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = Mock(spec=LLMClient)
    return client


@pytest.fixture
def classifier(mock_llm_client):
    """Create a classifier with mock LLM client."""
    return Classifier(mock_llm_client)


def test_classification_result_creation():
    """Test ClassificationResult dataclass creation."""
    result = ClassificationResult(
        class_type="work",
        category="meeting",
        project="warn_dashboard",
        summary="Team sync discussing project updates.",
        tags=["work", "meeting", "warn"]
    )

    assert result.class_type == "work"
    assert result.category == "meeting"
    assert result.project == "warn_dashboard"
    assert result.summary == "Team sync discussing project updates."
    assert len(result.tags) == 3


def test_classifier_success(classifier, mock_llm_client):
    """Test successful classification with LLM response."""
    # Mock LLM response
    mock_llm_client.call_structured.return_value = {
        "class_type": "work",
        "category": "meeting",
        "project": "warn_dashboard",
        "summary": "Weekly team sync to discuss project progress.",
        "tags": ["work", "meeting", "team"]
    }

    text = "Meeting notes: We discussed the WARN dashboard project and decided to prioritize the analytics features."
    result = classifier.classify_and_summarize(text)

    # Verify LLM was called correctly
    mock_llm_client.call_structured.assert_called_once()

    # Verify result
    assert result.class_type == "work"
    assert result.category == "meeting"
    assert result.project == "warn_dashboard"
    assert "Weekly team sync" in result.summary
    assert "work" in result.tags
    assert "meeting" in result.tags


def test_classifier_with_invalid_category(classifier, mock_llm_client):
    """Test classifier handling invalid category."""
    # Mock LLM response with invalid category
    mock_llm_client.call_structured.return_value = {
        "class_type": "work",
        "category": "invalid_category",
        "project": "warn_dashboard",
        "summary": "Some summary",
        "tags": ["work"]
    }

    text = "Some work-related text."
    result = classifier.classify_and_summarize(text)

    # Invalid category should be normalized to "other"
    assert result.category == "other"
    assert result.class_type == "work"


def test_classifier_with_invalid_class_type(classifier, mock_llm_client):
    """Test classifier handling invalid class_type."""
    # Mock LLM response with invalid class_type
    mock_llm_client.call_structured.return_value = {
        "class_type": "invalid_type",
        "category": "meeting",
        "project": "warn_dashboard",
        "summary": "Some summary",
        "tags": ["work"]
    }

    text = "Some text."
    result = classifier.classify_and_summarize(text)

    # Invalid class_type should be normalized to "personal"
    assert result.class_type == "personal"


def test_classifier_llm_failure_fallback(classifier, mock_llm_client):
    """Test classifier fallback when LLM fails."""
    # Mock LLM failure
    mock_llm_client.call_structured.side_effect = LLMClientError("API Error")

    text = "Meeting about the WARN dashboard project analytics features."
    result = classifier.classify_and_summarize(text)

    # Should use fallback classification
    assert result.category == "meeting"  # Detected from "Meeting" keyword
    assert result.class_type == "work"   # Detected from "project" keyword
    assert result.project == "none"
    assert len(result.tags) >= 1


def test_classifier_email_detection(classifier, mock_llm_client):
    """Test fallback classification for email content."""
    mock_llm_client.call_structured.side_effect = LLMClientError("API Error")

    text = "From: boss@company.com\nSubject: Q4 Project Update\nHey team, here are the updates..."
    result = classifier.classify_and_summarize(text)

    # The test data contains "company" and "project" so should be classified as work email
    assert result.category == "email"
    assert result.class_type == "work"  # Contains "company" and "project"


def test_classifier_slack_detection(classifier, mock_llm_client):
    """Test fallback classification for Slack content."""
    mock_llm_client.call_structured.side_effect = LLMClientError("API Error")

    text = "#general channel\n@john: Hey, did you see the message about the dashboard?"
    result = classifier.classify_and_summarize(text)

    assert result.category == "slack"
    assert result.class_type == "work"


def test_classifier_task_detection(classifier, mock_llm_client):
    """Test fallback classification for task content."""
    mock_llm_client.call_structured.side_effect = LLMClientError("API Error")

    text = "TODO: Review the dashboard analytics\nACTION ITEM: Send update to team"
    result = classifier.classify_and_summarize(text)

    assert result.category == "task"
    # Task defaults to personal unless clearly work-related


def test_classifier_text_truncation(classifier, mock_llm_client):
    """Test that very long text is truncated before LLM call."""
    # Create very long text
    long_text = "This is a test. " * 1000  # Much longer than 10000 chars
    assert len(long_text) > 10000

    mock_llm_client.call_structured.return_value = {
        "class_type": "other",
        "category": "other",
        "project": "none",
        "summary": "Truncated text summary",
        "tags": ["other"]
    }

    result = classifier.classify_and_summarize(long_text)

    # Check that LLM was called with truncated text
    call_args = mock_llm_client.call_structured.call_args[0][0]
    user_message = call_args[1]["content"]
    assert len(user_message) <= 10000 + 100  # Allow some margin for prompt text


def test_classifier_tag_normalization(classifier, mock_llm_client):
    """Test that tags are normalized correctly."""
    mock_llm_client.call_structured.return_value = {
        "class_type": "work",
        "category": "meeting",
        "project": "WARN Dashboard",
        "summary": "Some summary",
        "tags": ["Work Meeting", "Project-Update", "team_sync"]
    }

    text = "Meeting text."
    result = classifier.classify_and_summarize(text)

    # Tags should be lowercase with underscores
    assert "work_meeting" in result.tags
    assert "project_update" in result.tags
    assert "team_sync" in result.tags

    # Project name should be normalized
    assert result.project == "warn_dashboard"


def test_classifier_empty_tags_fallback(classifier, mock_llm_client):
    """Test classifier when LLM returns empty tags."""
    mock_llm_client.call_structured.return_value = {
        "class_type": "work",
        "category": "meeting",
        "project": "none",
        "summary": "Meeting summary",
        "tags": []
    }

    text = "Meeting text."
    result = classifier.classify_and_summarize(text)

    # Should have at least the category as a tag
    assert len(result.tags) >= 1
    assert "meeting" in result.tags


def test_classifier_malformed_tags(classifier, mock_llm_client):
    """Test classifier handling malformed tags list."""
    mock_llm_client.call_structured.return_value = {
        "class_type": "work",
        "category": "meeting",
        "project": "none",
        "summary": "Meeting summary",
        "tags": ["valid_tag", 123, None, ""]
    }

    text = "Meeting text."
    result = classifier.classify_and_summarize(text)

    # Should filter out non-string tags
    assert "valid_tag" in result.tags
    assert 123 not in result.tags
    assert None not in result.tags
    assert "" not in result.tags