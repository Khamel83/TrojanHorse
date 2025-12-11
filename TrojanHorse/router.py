"""Routing logic for organizing processed notes."""

import logging
from pathlib import Path
from typing import Optional

from .config import Config
from .models import NoteMeta, slugify

logger = logging.getLogger(__name__)


class Router:
    """Routes processed notes to appropriate directories in the vault."""

    def __init__(self, config: Config):
        """Initialize router with configuration."""
        self.config = config

    def _determine_base_directory(self) -> Path:
        """
        Determine the base directory for processed notes.

        Returns:
            Path where processed notes should be stored
        """
        if self.config.processed_root:
            return self.config.processed_root
        else:
            return self.config.vault_root

    def _build_directory_path(self, meta: NoteMeta, base_dir: Path) -> Path:
        """
        Build the directory path for a note based on its metadata.

        Args:
            meta: Note metadata
            base_dir: Base directory for processed notes

        Returns:
            Path to the directory where the note should be stored
        """
        # Top-level by class_type: work or personal
        class_dir = base_dir / meta.class_type

        # Next-level by category
        category_dir = class_dir / f"{meta.category}s"  # plural form: meetings, emails, etc.

        # Year subdirectory
        year_dir = category_dir / meta.created_at.strftime("%Y")

        return year_dir

    def _generate_filename(self, meta: NoteMeta) -> str:
        """
        Generate a filename for the processed note.

        Format: YYYY-MM-DD_<project_or_none>_<short_slug>.md

        Args:
            meta: Note metadata

        Returns:
            Filename for the note
        """
        # Date prefix
        date_prefix = meta.created_at.strftime("%Y-%m-%d")

        # Project name (or "misc" if none)
        project_part = meta.project if meta.project and meta.project != "none" else "misc"

        # Generate short slug from summary or use a default
        if meta.summary:
            # Take first few words and slugify them
            words = meta.summary.split()[:5]
            slug_part = "_".join(words)
            slug = slugify(slug_part, max_length=30)
        else:
            slug = "untitled"

        # Combine parts
        filename = f"{date_prefix}_{project_part}_{slug}.md"

        # Ensure filename isn't too long
        if len(filename) > 100:
            # Truncate the slug part if needed
            max_slug_length = 100 - len(f"{date_prefix}_{project_part}_.md")
            slug = slug[:max_slug_length]
            filename = f"{date_prefix}_{project_part}_{slug}.md"

        return filename

    def _ensure_directory_exists(self, dir_path: Path) -> None:
        """
        Ensure the directory exists, creating it if necessary.

        Args:
            dir_path: Directory path to ensure exists
        """
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {dir_path}")

    def route_note(self, meta: NoteMeta, body: str) -> Path:
        """
        Route a note to its appropriate location in the vault.

        Args:
            meta: Note metadata
            body: Note body content

        Returns:
            Path where the note was written
        """
        # Determine base directory
        base_dir = self._determine_base_directory()

        # Build directory structure
        target_dir = self._build_directory_path(meta, base_dir)

        # Ensure directory exists
        self._ensure_directory_exists(target_dir)

        # Generate filename
        filename = self._generate_filename(meta)

        # Full path for the note
        target_path = target_dir / filename

        # Handle filename conflicts by adding a suffix
        counter = 1
        original_target_path = target_path
        while target_path.exists():
            # Insert counter before the .md extension
            stem = original_target_path.stem
            target_path = target_dir / f"{stem}_{counter}.md"
            counter += 1

        logger.debug(f"Routing note to: {target_path}")

        return target_path

    def get_example_paths(self) -> dict:
        """
        Get example directory structure for documentation.

        Returns:
            Dictionary with example paths for different note types
        """
        base_dir = self._determine_base_directory()

        examples = {
            "work_meeting": base_dir / "work/meetings/2025/2025-11-25_hub_ops_sync.md",
            "personal_idea": base_dir / "personal/ideas/2025/2025-11-25_misc_idea_about_x.md",
            "work_email": base_dir / "work/emails/2025/2025-11-25_warn_dashboard_update.md",
            "personal_log": base_dir / "personal/logs/2025/2025-11-25_misc_daily_note.md",
        }

        return examples