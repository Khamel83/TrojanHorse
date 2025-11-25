"""Tests for the models module."""

import pytest
import yaml
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from trojanhorse.models import (
    NoteMeta, generate_note_id, parse_markdown_with_frontmatter,
    write_markdown, slugify, determine_source_from_path,
    determine_raw_type_from_path
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    temp_dir = TemporaryDirectory()
    yield Path(temp_dir.name)
    temp_dir.cleanup()


def test_note_meta_creation():
    """Test NoteMeta dataclass creation."""
    created_at = datetime(2025, 11, 25, 14, 30, 0)
    processed_at = datetime(2025, 11, 25, 14, 35, 0)

    meta = NoteMeta(
        id="test_id_123",
        source="drafts",
        raw_type="voice_note",
        class_type="work",
        category="idea",
        project="warn_dashboard",
        created_at=created_at,
        processed_at=processed_at,
        summary="Test summary",
        tags=["work", "idea"],
        original_path="/test/path.txt"
    )

    assert meta.id == "test_id_123"
    assert meta.source == "drafts"
    assert meta.raw_type == "voice_note"
    assert meta.class_type == "work"
    assert meta.category == "idea"
    assert meta.project == "warn_dashboard"
    assert meta.created_at == created_at
    assert meta.processed_at == processed_at
    assert meta.summary == "Test summary"
    assert meta.tags == ["work", "idea"]
    assert meta.original_path == "/test/path.txt"


def test_note_meta_from_dict():
    """Test creating NoteMeta from dictionary."""
    data = {
        "id": "test_id",
        "source": "macwhisper",
        "raw_type": "meeting_transcript",
        "class_type": "work",
        "category": "meeting",
        "project": "hub_ops",
        "created_at": "2025-11-25T14:30:00",
        "processed_at": "2025-11-25T14:35:00",
        "summary": "Meeting notes",
        "tags": ["work", "meeting"],
        "original_path": "/test/meeting.txt"
    }

    meta = NoteMeta.from_dict(data)

    assert meta.id == "test_id"
    assert meta.source == "macwhisper"
    assert meta.class_type == "work"
    assert isinstance(meta.created_at, datetime)
    assert isinstance(meta.processed_at, datetime)
    assert meta.created_at.isoformat() == "2025-11-25T14:30:00"
    assert meta.processed_at.isoformat() == "2025-11-25T14:35:00"


def test_note_meta_to_dict():
    """Test converting NoteMeta to dictionary."""
    created_at = datetime(2025, 11, 25, 14, 30, 0)
    processed_at = datetime(2025, 11, 25, 14, 35, 0)

    meta = NoteMeta(
        id="test_id",
        source="drafts",
        raw_type="voice_note",
        class_type="personal",
        category="idea",
        project="none",
        created_at=created_at,
        processed_at=processed_at,
        summary="Personal idea",
        tags=["personal", "idea"],
        original_path="/test/idea.txt"
    )

    data = meta.to_dict()

    assert data["id"] == "test_id"
    assert data["source"] == "drafts"
    assert data["class_type"] == "personal"
    assert data["created_at"] == created_at  # Should be datetime object
    assert data["processed_at"] == processed_at  # Should be datetime object


def test_generate_note_id():
    """Test note ID generation."""
    path1 = Path("/test/file1.txt")
    path2 = Path("/test/file2.txt")
    mtime = 1637856000.0

    id1 = generate_note_id(path1, mtime)
    id2 = generate_note_id(path1, mtime)
    id3 = generate_note_id(path2, mtime)
    id4 = generate_note_id(path1, mtime + 1.0)

    # Same path and mtime should generate same ID
    assert id1 == id2

    # Different paths should generate different IDs
    assert id1 != id3

    # Different mtimes should generate different IDs
    assert id1 != id4

    # ID should be in expected format: timestamp_hash
    assert "2021-11-25T14:40:00Z_" in id1
    assert len(id1.split("_")[1]) == 8  # Hash part should be 8 chars


def test_parse_markdown_with_frontmatter_with_valid_frontmatter(temp_dir):
    """Test parsing markdown file with valid frontmatter."""
    file_path = temp_dir / "test.md"
    content = """---
id: test_id
source: drafts
class_type: work
category: meeting
summary: Team sync meeting
tags:
  - work
  - meeting
---

# Meeting Notes

This is the body content of the meeting notes.
"""
    file_path.write_text(content)

    meta, body = parse_markdown_with_frontmatter(file_path)

    assert meta is not None
    assert meta.id == "test_id"
    assert meta.source == "drafts"
    assert meta.class_type == "work"
    assert meta.category == "meeting"
    assert meta.summary == "Team sync meeting"
    assert meta.tags == ["work", "meeting"]

    assert "Meeting Notes" in body
    assert "body content" in body


def test_parse_markdown_with_frontmatter_no_frontmatter(temp_dir):
    """Test parsing markdown file without frontmatter."""
    file_path = temp_dir / "test.md"
    content = """# Simple Note

This is just regular markdown content without any frontmatter.
"""
    file_path.write_text(content)

    meta, body = parse_markdown_with_frontmatter(file_path)

    assert meta is None
    assert "Simple Note" in body
    assert "markdown content" in body


def test_parse_markdown_with_frontmatter_invalid_yaml(temp_dir):
    """Test parsing markdown file with invalid YAML frontmatter."""
    file_path = temp_dir / "test.md"
    content = """---
id: test_id
source: drafts
invalid_yaml: [unclosed array
---

# Content

This should be treated as body content due to invalid YAML.
"""
    file_path.write_text(content)

    meta, body = parse_markdown_with_frontmatter(file_path)

    # Should treat entire file as body due to invalid YAML
    assert meta is None
    assert "Content" in body
    assert "invalid_yaml" in body  # Should include the invalid YAML


def test_parse_markdown_with_frontmatter_nonexistent_file():
    """Test parsing non-existent file."""
    nonexistent_path = Path("/nonexistent/file.md")

    with pytest.raises(FileNotFoundError):
        parse_markdown_with_frontmatter(nonexistent_path)


def test_write_markdown(temp_dir):
    """Test writing markdown file with frontmatter."""
    dest_path = temp_dir / "output.md"
    created_at = datetime(2025, 11, 25, 14, 30, 0)
    processed_at = datetime(2025, 11, 25, 14, 35, 0)

    meta = NoteMeta(
        id="test_write",
        source="macwhisper",
        raw_type="meeting_transcript",
        class_type="work",
        category="meeting",
        project="warn_dashboard",
        created_at=created_at,
        processed_at=processed_at,
        summary="Test write operation",
        tags=["work", "test"],
        original_path="/test/input.txt"
    )

    body = "# Test Meeting\n\nThis is test content for the meeting."

    write_markdown(dest_path, meta, body)

    # File should be created
    assert dest_path.exists()

    # Read and verify content
    content = dest_path.read_text()

    # Should contain frontmatter
    assert "---" in content
    assert "id: test_write" in content
    assert "source: macwhisper" in content
    assert "summary: Test write operation" in content

    # Should contain body
    assert "# Test Meeting" in content
    assert "This is test content" in content


def test_write_markdown_creates_directories(temp_dir):
    """Test that write_markdown creates parent directories."""
    nested_path = temp_dir / "level1" / "level2" / "output.md"

    # Directory shouldn't exist initially
    assert not nested_path.parent.exists()

    created_at = datetime.now()
    processed_at = datetime.now()

    meta = NoteMeta(
        id="test_nested",
        source="drafts",
        raw_type="voice_note",
        class_type="personal",
        category="idea",
        project="none",
        created_at=created_at,
        processed_at=processed_at,
        summary="Test nested directories",
        tags=["test"],
        original_path="/test/input.txt"
    )

    write_markdown(nested_path, meta, "Test content")

    # Directory should be created
    assert nested_path.parent.exists()
    assert nested_path.exists()


def test_slugify():
    """Test slugify function."""
    assert slugify("Hello World") == "hello_world"
    assert slugify("Test with-spaces and-hyphens") == "test_with_spaces_and_hyphens"
    assert slugify("Special! @#$%^&*()Characters") == "special_characters"
    assert slugify("Mixed CASE Text") == "mixed_case_text"
    assert slugify("") == "untitled"
    assert slugify("   spaces around   ") == "spaces_around"
    assert slugify("a" * 100) == "a" * 50  # Should truncate to 50 chars
    assert slugify("very long text that should be truncated", max_length=20) == "very_long_text_that"


def test_determine_source_from_path():
    """Test determining source type from file path."""
    assert determine_source_from_path(Path("/path/drafts_export.txt")) == "drafts"
    assert determine_source_from_path(Path("/path/Drafts_Note.md")) == "drafts"
    assert determine_source_from_path(Path("/path/transcript_file.txt")) == "macwhisper"
    assert determine_source_from_path(Path("/path/whisper_export.md")) == "macwhisper"
    assert determine_source_from_path(Path("/path/clipboard_content.txt")) == "clipboard"
    assert determine_source_from_path(Path("/path/unknown_file.txt")) == "unknown"


def test_determine_raw_type_from_path():
    """Test determining raw type from file path."""
    assert determine_raw_type_from_path(Path("/path/meeting_transcript.txt")) == "meeting_transcript"
    assert determine_raw_type_from_path(Path("/path/transcript_export.md")) == "meeting_transcript"
    assert determine_raw_type_from_path(Path("/path/email_dump.txt")) == "email_dump"
    assert determine_raw_type_from_path(Path("/path/Email_Export.md")) == "email_dump"
    assert determine_raw_type_from_path(Path("/path/slack_dump.txt")) == "slack_dump"
    assert determine_raw_type_from_path(Path("/path/Slack_Export.md")) == "slack_dump"
    assert determine_raw_type_from_path(Path("/path/voice_note.txt")) == "voice_note"  # default


def test_markdown_file_encoding_fallback(temp_dir):
    """Test that markdown parsing falls back to latin-1 for non-UTF8 files."""
    file_path = temp_dir / "test.md"

    # Create file with non-UTF8 content
    content = b"# Test\nContent with non-UTF8: \xff\xfe"
    file_path.write_bytes(content)

    # Should parse without raising UnicodeDecodeError
    meta, body = parse_markdown_with_frontmatter(file_path)

    assert meta is None  # No frontmatter
    assert "Test" in body


def test_frontmatter_with_datetime_strings(temp_dir):
    """Test parsing frontmatter with datetime strings."""
    file_path = temp_dir / "test.md"
    content = """---
id: test_id
created_at: 2025-11-25T14:30:00
processed_at: "2025-11-25T14:35:00"
---

# Test

Content here
"""
    file_path.write_text(content)

    meta, body = parse_markdown_with_frontmatter(file_path)

    assert meta is not None
    assert isinstance(meta.created_at, datetime)
    assert isinstance(meta.processed_at, datetime)
    assert meta.created_at.year == 2025
    assert meta.created_at.month == 11
    assert meta.created_at.day == 25