"""Vacuum - Migration tool for legacy notes."""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from TrojanHorse.atlas_client import AtlasClient, create_note_payload
from bridge.parsers import opml_to_markdown, extract_title

load_dotenv()

logger = logging.getLogger(__name__)

app = typer.Typer(help="Vacuum - Migrate legacy notes to Atlas")


# Supported file formats
MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd"}
TEXT_EXTENSIONS = {".txt", ".text"}
OPML_EXTENSIONS = {".opml"}


def is_supported_file(path: Path) -> bool:
    """Check if file is a supported format."""
    return (
        path.suffix.lower() in MARKDOWN_EXTENSIONS or
        path.suffix.lower() in TEXT_EXTENSIONS or
        path.suffix.lower() in OPML_EXTENSIONS
    )


def read_file_content(path: Path) -> tuple[str, str]:
    """
    Read file content and normalize to markdown.

    Returns:
        Tuple of (content, format_type)
    """
    if path.suffix.lower() in OPML_EXTENSIONS:
        # Convert OPML to markdown
        content = opml_to_markdown(path.read_text(encoding="utf-8"))
        return content, "opml"
    else:
        # Read as-is for markdown and text
        content = path.read_text(encoding="utf-8")
        return content, path.suffix.lstrip(".")


def find_files(directory: Path, recursive: bool = True) -> List[Path]:
    """
    Find all supported files in directory.

    Args:
        directory: Root directory to search
        recursive: Whether to search recursively

    Returns:
        List of file paths
    """
    files = []

    if recursive:
        for ext in MARKDOWN_EXTENSIONS | TEXT_EXTENSIONS | OPML_EXTENSIONS:
            files.extend(directory.rglob(f"*{ext}"))
    else:
        for ext in MARKDOWN_EXTENSIONS | TEXT_EXTENSIONS | OPML_EXTENSIONS:
            files.extend(directory.glob(f"*{ext}"))

    return sorted(files)


def parse_tags(tags_str: Optional[str]) -> List[str]:
    """Parse comma-separated tags string."""
    if not tags_str:
        return []
    return [t.strip() for t in tags_str.split(",") if t.strip()]


@app.command()
def migrate(
    directory: Path = typer.Argument(..., help="Directory containing legacy notes"),
    tags: Optional[str] = typer.Option(None, "--tag", "-t", help="Tags to apply to all notes"),
    recursive: bool = typer.Option(True, "--recursive", "-r", help="Search recursively"),
    delay: float = typer.Option(1.0, "--delay", "-d", help="Delay between API calls (seconds)"),
    atlas_url: Optional[str] = typer.Option(None, help="Atlas API URL"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without syncing"),
):
    """Migrate notes from a directory to Atlas."""
    setup_logging("INFO")

    # Configuration
    atlas_url = atlas_url or os.getenv("ATLAS_API_URL", "http://localhost:7444")
    api_key = os.getenv("ATLAS_API_KEY")

    if not directory.exists():
        logger.error(f"Directory does not exist: {directory}")
        raise typer.Exit(1)

    # Find files
    logger.info(f"Scanning: {directory}")
    files = find_files(directory, recursive)
    logger.info(f"Found {len(files)} supported files")

    if not files:
        logger.warning("No files to migrate")
        raise typer.Exit(0)

    # Parse tags
    base_tags = parse_tags(tags)

    # Initialize Atlas client
    if not dry_run:
        atlas_client = AtlasClient(atlas_url, api_key)

        if not atlas_client.health_check():
            logger.warning("Atlas health check failed, but continuing anyway")
    else:
        logger.info("DRY RUN MODE - No files will be synced")
        atlas_client = None

    # Migration log
    success_count = 0
    failure_count = 0
    skipped_count = 0

    for i, file_path in enumerate(files, 1):
        logger.info(f"[{i}/{len(files)}] Processing: {file_path.name}")

        try:
            # Read content
            content, format_type = read_file_content(file_path)

            if not content.strip():
                logger.warning(f"  Skipping empty file: {file_path.name}")
                skipped_count += 1
                continue

            # Create payload
            title = extract_title(content, file_path)
            payload = create_note_payload(
                file_path=file_path,
                content=content,
                tags=base_tags + [f"format:{format_type}", "legacy"],
                source="vacuum"
            )
            payload["title"] = title  # Override with extracted title

            if dry_run:
                logger.info(f"  Would sync: {title}")
                logger.info(f"  Tags: {payload['tags']}")
                logger.info(f"  Content length: {len(content)} chars")
            else:
                # Sync to Atlas
                success = atlas_client.ingest_note(payload)

                if success:
                    logger.info(f"  Synced: {title}")
                    success_count += 1
                else:
                    logger.error(f"  Failed to sync: {title}")
                    failure_count += 1

                # Rate limiting
                if delay > 0 and i < len(files):
                    time.sleep(delay)

        except Exception as e:
            logger.error(f"  Error processing {file_path.name}: {e}")
            failure_count += 1

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("Migration Summary:")
    logger.info(f"  Total files: {len(files)}")
    logger.info(f"  Successful: {success_count}")
    logger.info(f"  Failed: {failure_count}")
    logger.info(f"  Skipped: {skipped_count}")

    if dry_run:
        logger.info("\n(DRY RUN - No actual changes made)")

    raise typer.Exit(0 if failure_count == 0 else 1)


@app.command()
def check(
    directory: Path = typer.Argument(..., help="Directory to check"),
    recursive: bool = typer.Option(True, "--recursive", "-r", help="Search recursively"),
):
    """Check what files would be migrated."""
    setup_logging("INFO")

    if not directory.exists():
        logger.error(f"Directory does not exist: {directory}")
        raise typer.Exit(1)

    files = find_files(directory, recursive)

    # Group by extension
    by_ext = {}
    for f in files:
        ext = f.suffix.lower()
        by_ext.setdefault(ext, []).append(f)

    logger.info(f"Found {len(files)} files in {directory}")
    for ext, file_list in sorted(by_ext.items()):
        logger.info(f"  {ext}: {len(file_list)} files")

    # Show first few files
    logger.info("\nFirst 10 files:")
    for f in files[:10]:
        logger.info(f"  {f}")

    if len(files) > 10:
        logger.info(f"  ... and {len(files) - 10} more")


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


if __name__ == "__main__":
    app()
