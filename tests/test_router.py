"""Tests for the router module."""

import pytest
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
import shutil

from trojanhorse.config import Config
from trojanhorse.models import NoteMeta
from trojanhorse.router import Router


@pytest.fixture
def temp_vault():
    """Create a temporary vault directory."""
    temp_dir = TemporaryDirectory()
    yield Path(temp_dir.name)
    temp_dir.cleanup()


@pytest.fixture
def config(temp_vault):
    """Create a config object with temporary vault."""
    # Mock the minimum required config
    config = Config(
        vault_root=temp_vault,
        capture_dirs=[temp_vault / "Inbox"],
        processed_root=temp_vault / "Processed",
        state_dir=temp_vault / ".trojanhorse",
        openrouter_api_key="test_key",
        openrouter_model="test_model",
        embedding_model_name="test_model",
        embedding_api_key=None,
        embedding_api_base="https://api.openai.com/v1"
    )
    return config


@pytest.fixture
def router(config):
    """Create a router with test config."""
    return Router(config)


@pytest.fixture
def sample_work_meeting_meta():
    """Create sample work meeting metadata."""
    return NoteMeta(
        id="2025-11-25T14:30:00Z_test123",
        source="macwhisper",
        raw_type="meeting_transcript",
        class_type="work",
        category="meeting",
        project="warn_dashboard",
        created_at=datetime(2025, 11, 25, 14, 25, 0),
        processed_at=datetime(2025, 11, 25, 14, 30, 0),
        summary="Weekly team sync to discuss dashboard analytics.",
        tags=["work", "meeting", "warn", "analytics"],
        original_path="/test/transcripts/team_sync.txt"
    )


@pytest.fixture
def sample_personal_idea_meta():
    """Create sample personal idea metadata."""
    return NoteMeta(
        id="2025-11-25T20:15:00Z_idea456",
        source="drafts",
        raw_type="voice_note",
        class_type="personal",
        category="idea",
        project="none",
        created_at=datetime(2025, 11, 25, 20, 10, 0),
        processed_at=datetime(2025, 11, 25, 20, 15, 0),
        summary="Idea for a personal productivity app that helps track habits.",
        tags=["personal", "idea", "productivity"],
        original_path="/test/inbox/voice_note.txt"
    )


def test_router_initialization(router, config):
    """Test router initialization."""
    assert router.config == config


def test_base_directory_with_processed_root(router, config):
    """Test base directory when processed_root is configured."""
    base_dir = router._determine_base_directory()
    assert base_dir == config.processed_root


def test_base_directory_without_processed_root(config):
    """Test base directory when processed_root is not configured."""
    config_no_processed = Config(
        vault_root=config.vault_root,
        capture_dirs=config.capture_dirs,
        processed_root=None,  # No processed root
        state_dir=config.state_dir,
        openrouter_api_key="test_key",
        openrouter_model="test_model",
        embedding_model_name="test_model",
        embedding_api_key=None,
        embedding_api_base="https://api.openai.com/v1"
    )
    router = Router(config_no_processed)

    base_dir = router._determine_base_directory()
    assert base_dir == config.vault_root


def test_directory_path_construction(router, sample_work_meeting_meta):
    """Test directory path construction for work meeting."""
    base_dir = router._determine_base_directory()
    dir_path = router._build_directory_path(sample_work_meeting_meta, base_dir)

    expected = base_dir / "work" / "meetings" / "2025"
    assert dir_path == expected


def test_directory_path_personal_idea(router, sample_personal_idea_meta):
    """Test directory path construction for personal idea."""
    base_dir = router._determine_base_directory()
    dir_path = router._build_directory_path(sample_personal_idea_meta, base_dir)

    expected = base_dir / "personal" / "ideas" / "2025"
    assert dir_path == expected


def test_directory_path_email(router):
    """Test directory path construction for email."""
    email_meta = NoteMeta(
        id="2025-11-25T09:00:00Z_email789",
        source="drafts",
        raw_type="email_dump",
        class_type="work",
        category="email",
        project="hub_ops",
        created_at=datetime(2025, 11, 25, 9, 0, 0),
        processed_at=datetime(2025, 11, 25, 9, 5, 0),
        summary="Project update email from the team.",
        tags=["work", "email"],
        original_path="/test/inbox/email_dump.txt"
    )

    base_dir = router._determine_base_directory()
    dir_path = router._build_directory_path(email_meta, base_dir)

    expected = base_dir / "work" / "emails" / "2025"
    assert dir_path == expected


def test_filename_generation_with_summary(router, sample_work_meeting_meta):
    """Test filename generation with available summary."""
    filename = router._generate_filename(sample_work_meeting_meta)

    # Should be in format: YYYY-MM-DD_project_short_slug.md
    assert filename.startswith("2025-11-25_")
    assert "warn_dashboard" in filename
    assert filename.endswith(".md")
    assert len(filename) <= 100  # Should respect max length


def test_filename_generation_without_summary(router):
    """Test filename generation without summary."""
    meta_no_summary = NoteMeta(
        id="2025-11-25T10:00:00Z_test000",
        source="unknown",
        raw_type="other",
        class_type="personal",
        category="other",
        project="none",
        created_at=datetime(2025, 11, 25, 10, 0, 0),
        processed_at=datetime(2025, 11, 25, 10, 5, 0),
        summary="",  # Empty summary
        tags=["personal"],
        original_path="/test/file.txt"
    )

    filename = router._generate_filename(meta_no_summary)

    assert filename.startswith("2025-11-25_")
    assert "misc" in filename  # Project should be "misc" when project is "none"
    assert "untitled" in filename  # Should use "untitled" when no summary
    assert filename.endswith(".md")


def test_filename_generation_with_none_project(router):
    """Test filename generation with project='none'."""
    meta_none_project = NoteMeta(
        id="2025-11-25T15:00:00Z_test001",
        source="drafts",
        raw_type="voice_note",
        class_type="personal",
        category="log",
        project="none",
        created_at=datetime(2025, 11, 25, 15, 0, 0),
        processed_at=datetime(2025, 11, 25, 15, 5, 0),
        summary="Daily log entry about personal activities.",
        tags=["personal", "log"],
        original_path="/test/log.txt"
    )

    filename = router._generate_filename(meta_none_project)

    assert "misc" in filename  # Should convert "none" to "misc"


def test_filename_length_truncation(router):
    """Test that very long filenames are truncated appropriately."""
    # Create metadata with a very long summary
    meta_long_summary = NoteMeta(
        id="2025-11-25T16:00:00Z_test002",
        source="drafts",
        raw_type="voice_note",
        class_type="work",
        category="idea",
        project="very_long_project_name_that_should_be_truncated",
        created_at=datetime(2025, 11, 25, 16, 0, 0),
        processed_at=datetime(2025, 11, 25, 16, 5, 0),
        summary="This is a very long summary that would normally result in a filename that is much longer than the maximum allowed length of one hundred characters so it should be truncated appropriately while maintaining readability",
        tags=["work", "idea"],
        original_path="/test/long_summary.txt"
    )

    filename = router._generate_filename(meta_long_summary)

    # Should not exceed maximum length
    assert len(filename) <= 100
    assert filename.endswith(".md")
    assert "2025-11-25_" in filename


def test_directory_creation(router, sample_work_meeting_meta, temp_vault):
    """Test that directories are created when routing notes."""
    base_dir = router._determine_base_directory()
    dir_path = router._build_directory_path(sample_work_meeting_meta, base_dir)

    # Directory shouldn't exist initially
    assert not dir_path.exists()

    # Ensure directory exists
    router._ensure_directory_exists(dir_path)

    # Directory should now exist
    assert dir_path.exists()
    assert dir_path.is_dir()


def test_complete_routing(router, sample_work_meeting_meta, temp_vault):
    """Test complete routing process."""
    body = "# Team Sync Meeting\n\nWe discussed the dashboard analytics and decided to prioritize the real-time features."

    # Route the note
    dest_path = router.route_note(sample_work_meeting_meta, body)

    # Check that path is correctly constructed
    assert dest_path.parent.name == "2025"
    assert dest_path.parent.parent.name == "meetings"
    assert dest_path.parent.parent.parent.name == "work"
    assert dest_path.suffix == ".md"
    assert "2025-11-25" in dest_path.name
    assert "warn_dashboard" in dest_path.name


def test_filename_conflict_resolution(router, sample_work_meeting_meta, temp_vault):
    """Test that filename conflicts are resolved by adding suffixes."""
    body = "# Test Content\n\nThis is test content."

    # Route first note
    dest_path1 = router.route_note(sample_work_meeting_meta, body)

    # Create the file to simulate a conflict
    dest_path1.parent.mkdir(parents=True, exist_ok=True)
    dest_path1.write_text("Existing content")

    # Route second note with same metadata (would cause conflict)
    dest_path2 = router.route_note(sample_work_meeting_meta, body)

    # Paths should be different (second should have suffix)
    assert dest_path1 != dest_path2
    assert dest_path2.stem.endswith("_1")  # Should have _1 suffix


def test_example_paths(router):
    """Test that example paths are generated correctly."""
    examples = router.get_example_paths()

    # Should have all expected example types
    assert "work_meeting" in examples
    assert "personal_idea" in examples
    assert "work_email" in examples
    assert "personal_log" in examples

    # Check that paths are correctly structured
    work_meeting_path = examples["work_meeting"]
    assert "work" in str(work_meeting_path)
    assert "meetings" in str(work_meeting_path)
    assert "2025" in str(work_meeting_path)