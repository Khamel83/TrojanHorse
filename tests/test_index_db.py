"""Tests for the index_db module."""

import pytest
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory
import time
import sqlite3

from trojanhorse.index_db import IndexDB


@pytest.fixture
def temp_state_dir():
    """Create a temporary state directory."""
    temp_dir = TemporaryDirectory()
    yield Path(temp_dir.name)
    temp_dir.cleanup()


@pytest.fixture
def index_db(temp_state_dir):
    """Create an IndexDB instance with temporary directory."""
    return IndexDB(temp_state_dir)


@pytest.fixture
def sample_file_path(temp_state_dir):
    """Create a sample file path for testing."""
    return temp_state_dir / "test_file.txt"


def test_index_db_initialization(temp_state_dir):
    """Test that IndexDB initializes database correctly."""
    db_path = temp_state_dir / "processed_files.db"

    # Database shouldn't exist initially
    assert not db_path.exists()

    # Create IndexDB
    index_db = IndexDB(temp_state_dir)

    # Database should now exist
    assert db_path.exists()
    assert db_path.is_file()

    # Check that tables were created
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "processed_files" in tables


def test_file_key_generation(index_db, sample_file_path, temp_state_dir):
    """Test file key generation."""
    mtime = 1637856000.0  # Fixed timestamp

    key1 = index_db._generate_file_key(sample_file_path, mtime)
    key2 = index_db._generate_file_key(sample_file_path, mtime)
    key3 = index_db._generate_file_key(sample_file_path, mtime + 1.0)  # Different mtime
    key4 = index_db._generate_file_key(temp_state_dir / "other_file.txt", mtime)  # Different path

    # Same file and mtime should generate same key
    assert key1 == key2

    # Different mtime should generate different key
    assert key1 != key3

    # Different path should generate different key
    assert key1 != key4

    # Keys should be valid SHA256 hex strings
    assert len(key1) == 64
    assert all(c in "0123456789abcdef" for c in key1)


def test_mark_and_check_processed(index_db, sample_file_path, temp_state_dir):
    """Test marking files as processed and checking status."""
    # Create the sample file
    sample_file_path.write_text("Test content")

    # Get file info
    mtime = sample_file_path.stat().st_mtime
    dest_path = temp_state_dir / "processed" / "test_file.md"

    # Initially should not be processed
    assert not index_db.has_been_processed(sample_file_path, mtime)

    # Mark as processed
    index_db.mark_processed(sample_file_path, mtime, dest_path)

    # Now should be processed
    assert index_db.has_been_processed(sample_file_path, mtime)

    # Different mtime should not be considered processed
    assert not index_db.has_been_processed(sample_file_path, mtime + 1.0)


def test_mark_processed_with_file_size(index_db, sample_file_path, temp_state_dir):
    """Test marking files as processed with custom file size."""
    # Create the sample file
    content = "Test content for file size"
    sample_file_path.write_text(content)
    actual_size = len(content.encode())

    mtime = sample_file_path.stat().st_mtime
    dest_path = temp_state_dir / "processed" / "test_file.md"

    # Mark with custom size
    custom_size = 999
    index_db.mark_processed(sample_file_path, mtime, dest_path, file_size=custom_size)

    # Check that custom size was stored
    processed_info = index_db.get_processed_info(sample_file_path, mtime)
    assert processed_info is not None
    assert processed_info["file_size"] == custom_size


def test_mark_processed_without_file_size(index_db, sample_file_path, temp_state_dir):
    """Test marking files as processed without specifying file size."""
    # Create the sample file
    content = "Test content"
    sample_file_path.write_text(content)
    expected_size = len(content.encode())

    mtime = sample_file_path.stat().st_mtime
    dest_path = temp_state_dir / "processed" / "test_file.md"

    # Mark without specifying size (should auto-detect)
    index_db.mark_processed(sample_file_path, mtime, dest_path)

    # Check that size was auto-detected
    processed_info = index_db.get_processed_info(sample_file_path, mtime)
    assert processed_info is not None
    assert processed_info["file_size"] == expected_size


def test_get_processed_info_not_found(index_db, sample_file_path):
    """Test getting processed info for non-existent file."""
    mtime = 1637856000.0

    # Should return None for unprocessed file
    info = index_db.get_processed_info(sample_file_path, mtime)
    assert info is None


def test_get_processed_info_existing(index_db, sample_file_path, temp_state_dir):
    """Test getting processed info for existing file."""
    # Create and mark file
    sample_file_path.write_text("Test content")
    mtime = sample_file_path.stat().st_mtime
    dest_path = temp_state_dir / "processed" / "test_file.md"

    index_db.mark_processed(sample_file_path, mtime, dest_path)

    # Get processed info
    info = index_db.get_processed_info(sample_file_path, mtime)
    assert info is not None

    # Check fields
    assert info["original_path"] == str(sample_file_path.absolute())
    assert info["dest_path"] == str(dest_path.absolute())
    assert info["mtime"] == mtime
    assert info["file_size"] == len("Test content".encode())
    assert "processed_at" in info
    assert "id" in info


def test_remove_processed_entry(index_db, sample_file_path, temp_state_dir):
    """Test removing processed file entries."""
    # Create and mark file
    sample_file_path.write_text("Test content")
    mtime = sample_file_path.stat().st_mtime
    dest_path = temp_state_dir / "processed" / "test_file.md"

    index_db.mark_processed(sample_file_path, mtime, dest_path)

    # Should be processed
    assert index_db.has_been_processed(sample_file_path, mtime)

    # Remove entry
    removed = index_db.remove_entry(sample_file_path, mtime)
    assert removed is True

    # Should no longer be processed
    assert not index_db.has_been_processed(sample_file_path, mtime)


def test_remove_nonexistent_entry(index_db, sample_file_path):
    """Test removing entry that doesn't exist."""
    mtime = 1637856000.0

    # Should return False for non-existent entry
    removed = index_db.remove_entry(sample_file_path, mtime)
    assert removed is False


def test_get_all_processed_files(index_db, temp_state_dir):
    """Test getting all processed files."""
    # Create and mark multiple files
    files = []
    for i in range(3):
        file_path = temp_state_dir / f"test_file_{i}.txt"
        file_path.write_text(f"Content {i}")
        dest_path = temp_state_dir / "processed" / f"test_file_{i}.md"

        mtime = file_path.stat().st_mtime
        index_db.mark_processed(file_path, mtime, dest_path)
        files.append((file_path, mtime, dest_path))

        # Small delay to ensure different processed_at times
        time.sleep(0.1)

    # Get all processed files
    all_files = index_db.get_all_processed_files()

    assert len(all_files) == 3

    # Should be ordered by processed_at DESC (newest first)
    assert all_files[0]["original_path"] == str(files[2][0].absolute())
    assert all_files[1]["original_path"] == str(files[1][0].absolute())
    assert all_files[2]["original_path"] == str(files[0][0].absolute())


def test_get_stats_empty(index_db):
    """Test getting stats for empty database."""
    stats = index_db.get_stats()

    assert stats["total_files"] == 0
    assert stats["total_size_bytes"] == 0
    assert stats["oldest_processed"] is None
    assert stats["newest_processed"] is None
    assert "db_path" in stats


def test_get_stats_with_files(index_db, temp_state_dir):
    """Test getting stats with files in database."""
    # Create and mark multiple files with different sizes
    contents = ["Short", "Medium length content", "Much longer content with more text"]
    total_size = 0

    for i, content in enumerate(contents):
        file_path = temp_state_dir / f"test_file_{i}.txt"
        file_path.write_text(content)
        dest_path = temp_state_dir / "processed" / f"test_file_{i}.md"

        total_size += len(content.encode())

        mtime = file_path.stat().st_mtime
        index_db.mark_processed(file_path, mtime, dest_path)

        time.sleep(0.1)  # Ensure different timestamps

    # Get stats
    stats = index_db.get_stats()

    assert stats["total_files"] == 3
    assert stats["total_size_bytes"] == total_size
    assert stats["oldest_processed"] is not None
    assert stats["newest_processed"] is not None


def test_cleanup_stale_entries(index_db, temp_state_dir):
    """Test cleaning up entries for files that no longer exist."""
    # Create files and mark them
    existing_file = temp_state_dir / "existing.txt"
    existing_file.write_text("I exist")

    stale_file = temp_state_dir / "stale.txt"
    stale_file.write_text("I will be deleted")

    existing_mtime = existing_file.stat().st_mtime
    stale_mtime = stale_file.stat().st_mtime

    existing_dest = temp_state_dir / "processed" / "existing.md"
    stale_dest = temp_state_dir / "processed" / "stale.md"

    index_db.mark_processed(existing_file, existing_mtime, existing_dest)
    index_db.mark_processed(stale_file, stale_mtime, stale_dest)

    # Delete one file to make it "stale"
    stale_file.unlink()

    # Should have 2 entries initially
    all_files = index_db.get_all_processed_files()
    assert len(all_files) == 2

    # Cleanup stale entries
    removed_count = index_db.cleanup_stale_entries()

    # Should have removed 1 stale entry
    assert removed_count == 1

    # Should have 1 entry remaining
    all_files = index_db.get_all_processed_files()
    assert len(all_files) == 1
    assert "existing" in all_files[0]["original_path"]


def test_overwrite_processed_entry(index_db, sample_file_path, temp_state_dir):
    """Test that marking an already processed file overwrites the entry."""
    # Create the sample file
    sample_file_path.write_text("Original content")
    mtime = sample_file_path.stat().st_mtime

    dest_path1 = temp_state_dir / "processed" / "version1.md"
    dest_path2 = temp_state_dir / "processed" / "version2.md"

    # Mark as processed first time
    index_db.mark_processed(sample_file_path, mtime, dest_path1)

    info1 = index_db.get_processed_info(sample_file_path, mtime)
    assert info1["dest_path"] == str(dest_path1.absolute())

    # Mark as processed again with different destination
    index_db.mark_processed(sample_file_path, mtime, dest_path2)

    info2 = index_db.get_processed_info(sample_file_path, mtime)
    assert info2["dest_path"] == str(dest_path2.absolute())

    # Should still only have one entry
    all_files = index_db.get_all_processed_files()
    assert len(all_files) == 1