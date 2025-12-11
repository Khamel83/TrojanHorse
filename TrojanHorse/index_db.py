"""Processed file tracking using SQLite."""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import sqlite3

logger = logging.getLogger(__name__)


class IndexDB:
    """SQLite database for tracking processed files."""

    def __init__(self, state_dir: Path):
        """
        Initialize index database.

        Args:
            state_dir: Directory where state files are stored
        """
        self.db_path = state_dir / "processed_files.db"
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create the database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    id TEXT PRIMARY KEY,
                    original_path TEXT NOT NULL,
                    mtime REAL NOT NULL,
                    processed_at TEXT NOT NULL,
                    dest_path TEXT NOT NULL,
                    file_size INTEGER
                )
            """)

            # Create indexes for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_original_path
                ON processed_files(original_path)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_mtime
                ON processed_files(mtime)
            """)

            conn.commit()

        logger.debug(f"Initialized index database: {self.db_path}")

    def _generate_file_key(self, path: Path, mtime: float) -> str:
        """
        Generate a unique key for a file based on path and modification time.

        Args:
            path: File path
            mtime: File modification time

        Returns:
            Unique file key
        """
        key_data = f"{path.absolute()}:{mtime}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def has_been_processed(self, path: Path, mtime: float) -> bool:
        """
        Check if a file has already been processed.

        Args:
            path: File path to check
            mtime: File modification time

        Returns:
            True if file has been processed with the same mtime
        """
        file_key = self._generate_file_key(path, mtime)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM processed_files WHERE id = ?",
                    (file_key,)
                )
                result = cursor.fetchone()
                return result is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking processed status for {path}: {e}")
            return False

    def get_processed_info(self, path: Path, mtime: float) -> Optional[dict]:
        """
        Get information about a processed file.

        Args:
            path: File path
            mtime: File modification time

        Returns:
            Dictionary with file info or None if not found
        """
        file_key = self._generate_file_key(path, mtime)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM processed_files WHERE id = ?",
                    (file_key,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except sqlite3.Error as e:
            logger.error(f"Error getting processed info for {path}: {e}")
            return None

    def mark_processed(
        self,
        path: Path,
        mtime: float,
        dest_path: Path,
        file_size: Optional[int] = None
    ) -> None:
        """
        Mark a file as processed.

        Args:
            path: Original file path
            mtime: File modification time
            dest_path: Destination path where processed file was written
            file_size: Optional file size
        """
        file_key = self._generate_file_key(path, mtime)
        processed_at = datetime.now().isoformat()

        if file_size is None and path.exists():
            file_size = path.stat().st_size

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO processed_files
                    (id, original_path, mtime, processed_at, dest_path, file_size)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_key,
                        str(path.absolute()),
                        mtime,
                        processed_at,
                        str(dest_path.absolute()),
                        file_size
                    )
                )
                conn.commit()

            logger.debug(f"Marked file as processed: {path} -> {dest_path}")

        except sqlite3.Error as e:
            logger.error(f"Error marking file as processed {path}: {e}")
            raise

    def remove_entry(self, path: Path, mtime: float) -> bool:
        """
        Remove a processed file entry from the database.

        Args:
            path: Original file path
            mtime: File modification time

        Returns:
            True if entry was removed, False if it didn't exist
        """
        file_key = self._generate_file_key(path, mtime)

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM processed_files WHERE id = ?",
                    (file_key,)
                )
                deleted_count = cursor.rowcount
                conn.commit()

                if deleted_count > 0:
                    logger.debug(f"Removed processed entry for: {path}")
                    return True
                else:
                    logger.debug(f"No processed entry found for: {path}")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Error removing processed entry for {path}: {e}")
            return False

    def get_all_processed_files(self) -> list:
        """
        Get all processed file entries.

        Returns:
            List of dictionaries with file information
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM processed_files ORDER BY processed_at DESC"
                )
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error getting all processed files: {e}")
            return []

    def cleanup_stale_entries(self) -> int:
        """
        Clean up entries for files that no longer exist.

        Returns:
            Number of entries removed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT original_path, id FROM processed_files")
                rows = cursor.fetchall()

                entries_to_remove = []
                for original_path_str, file_id in rows:
                    original_path = Path(original_path_str)
                    if not original_path.exists():
                        entries_to_remove.append(file_id)

                if entries_to_remove:
                    placeholders = ",".join("?" * len(entries_to_remove))
                    cursor.execute(
                        f"DELETE FROM processed_files WHERE id IN ({placeholders})",
                        entries_to_remove
                    )
                    deleted_count = len(entries_to_remove)
                    conn.commit()

                    logger.info(f"Cleaned up {deleted_count} stale processed file entries")
                    return deleted_count
                else:
                    logger.debug("No stale processed file entries found")
                    return 0

        except sqlite3.Error as e:
            logger.error(f"Error cleaning up stale entries: {e}")
            return 0

    def get_stats(self) -> dict:
        """
        Get statistics about processed files.

        Returns:
            Dictionary with statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Total count
                cursor.execute("SELECT COUNT(*) FROM processed_files")
                total_count = cursor.fetchone()[0]

                # Total size (if file_size is available)
                cursor.execute("SELECT SUM(file_size) FROM processed_files WHERE file_size IS NOT NULL")
                total_size = cursor.fetchone()[0] or 0

                # Oldest and newest processed dates
                cursor.execute("SELECT MIN(processed_at), MAX(processed_at) FROM processed_files")
                oldest, newest = cursor.fetchone()

                return {
                    "total_files": total_count,
                    "total_size_bytes": total_size,
                    "oldest_processed": oldest,
                    "newest_processed": newest,
                    "db_path": str(self.db_path)
                }

        except sqlite3.Error as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "oldest_processed": None,
                "newest_processed": None,
                "db_path": str(self.db_path)
            }