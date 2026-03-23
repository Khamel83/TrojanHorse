"""The Bridge - File watcher that syncs notes to Atlas."""

import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from threading import Timer
from typing import Dict, List, Optional, Set

import typer
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
from watchdog.observers import Observer

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from TrojanHorse.atlas_client import AtlasClient, create_note_payload

load_dotenv()

logger = logging.getLogger(__name__)

app = typer.Typer(help="The Bridge - Watch files and sync to Atlas")


class WatchConfig:
    """Configuration for a watched path."""

    def __init__(self, path_str: str):
        """
        Parse watch configuration from string.

        Format: "/path/to/watch|tags:tag1,tag2"
        """
        if "|" in path_str:
            path_part, tags_part = path_str.split("|", 1)
            self.path = Path(path_part.strip())
            # Parse tags: "tags:work,meeting" -> ["work", "meeting"]
            if tags_part.strip().startswith("tags:"):
                self.tags = [t.strip() for t in tags_part.split(":", 1)[1].split(",")]
            else:
                self.tags = []
        else:
            self.path = Path(path_str.strip())
            self.tags = []

        if not self.path.exists():
            logger.warning(f"Watch path does not exist: {self.path}")


class DebouncedFileHandler(FileSystemEventHandler):
    """
    File system event handler with debouncing.

    Waits for a period of silence after the last event before processing.
    """

    def __init__(
        self,
        atlas_client: AtlasClient,
        debounce_seconds: int = 30,
        processed_subdir: str = "processed",
        move_after_sync: bool = True,
    ):
        """
        Initialize debounced handler.

        Args:
            atlas_client: Atlas client for syncing notes
            debounce_seconds: Seconds to wait after last event before processing
            processed_subdir: Subdirectory name for processed files
            move_after_sync: Whether to move files after successful sync
        """
        self.atlas_client = atlas_client
        self.debounce_seconds = debounce_seconds
        self.processed_subdir = processed_subdir
        self.move_after_sync = move_after_sync
        self.pending_files: Dict[Path, Timer] = {}
        self.watched_configs: Dict[Path, WatchConfig] = {}
        self.processed: Set[Path] = set()

    def add_watch_config(self, config: WatchConfig):
        """Add a watch configuration."""
        self.watched_configs[config.path] = config

    def _schedule_processing(self, file_path: Path, tags: List[str]):
        """Schedule processing of a file after debounce delay."""

        def process_file():
            try:
                self._process_file(file_path, tags)
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
            finally:
                self.pending_files.pop(file_path, None)

        # Cancel existing timer if any
        if file_path in self.pending_files:
            self.pending_files[file_path].cancel()

        # Create new timer
        timer = Timer(self.debounce_seconds, process_file)
        self.pending_files[file_path] = timer
        timer.start()

    def _process_file(self, file_path: Path, tags: List[str]):
        """Process a single file: read, create payload, sync to Atlas."""
        if not file_path.exists():
            logger.debug(f"File no longer exists: {file_path}")
            return

        if file_path in self.processed:
            logger.debug(f"Already processed: {file_path}")
            return

        try:
            # Read file content
            content = file_path.read_text(encoding="utf-8")

            # Create note payload
            payload = create_note_payload(
                file_path=file_path,
                content=content,
                tags=tags,
                source="hyprnote"
            )

            # Sync to Atlas with retry
            success = self._sync_to_atlas(payload)

            if success and self.move_after_sync:
                self._move_to_processed(file_path)
                self.processed.add(file_path)

        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, OSError)),
    )
    def _sync_to_atlas(self, payload: dict) -> bool:
        """Sync note to Atlas with retry logic."""
        return self.atlas_client.ingest_note(payload)

    def _move_to_processed(self, file_path: Path):
        """Move file to processed subdirectory."""
        processed_dir = file_path.parent / self.processed_subdir
        processed_dir.mkdir(exist_ok=True)
        dest = processed_dir / file_path.name

        # Handle name conflicts
        counter = 1
        while dest.exists():
            stem = file_path.stem
            suffix = file_path.suffix
            dest = processed_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        shutil.move(str(file_path), str(dest))
        logger.info(f"Moved to processed: {file_path} -> {dest}")

    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if not path.suffix == ".md":
            return

        # Find matching watch config
        tags = []
        for watch_path, config in self.watched_configs.items():
            try:
                path.relative_to(watch_path)
                tags = config.tags
                break
            except ValueError:
                continue

        logger.debug(f"File created: {path} (tags: {tags})")
        self._schedule_processing(path, tags)

    def on_modified(self, event):
        """Handle file modification event."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if not path.suffix == ".md":
            return

        # Find matching watch config
        tags = []
        for watch_path, config in self.watched_configs.items():
            try:
                path.relative_to(watch_path)
                tags = config.tags
                break
            except ValueError:
                continue

        logger.debug(f"File modified: {path} (tags: {tags})")
        self._schedule_processing(path, tags)


def parse_watch_paths() -> List[WatchConfig]:
    """Parse WATCH_PATHS from environment."""
    watch_paths_str = os.getenv("WATCH_PATHS", "")
    if not watch_paths_str:
        logger.warning("WATCH_PATHS not configured")
        return []

    configs = []
    for path_str in watch_paths_str.split(";"):
        path_str = path_str.strip()
        if path_str:
            configs.append(WatchConfig(path_str))

    return configs


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """Configure logging."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


@app.command()
def run(
    watch_paths: Optional[str] = typer.Option(
        None,
        help="Watch paths (overrides WATCH_PATHS env var). Format: /path|tags:tag1,tag2;/path2|tags:tag3",
    ),
    debounce: int = typer.Option(
        None,
        help="Debounce delay in seconds (overrides DEBOUNCE_SECONDS env var)",
    ),
    atlas_url: Optional[str] = typer.Option(
        None,
        help="Atlas API URL (overrides ATLAS_API_URL env var)",
    ),
    log_level: str = typer.Option(
        None,
        help="Log level (overrides LOG_LEVEL env var)",
    ),
):
    """Start the bridge service."""
    # Load configuration
    atlas_url = atlas_url or os.getenv("ATLAS_API_URL", "http://localhost:7444")
    api_key = os.getenv("ATLAS_API_KEY")
    debounce = debounce or int(os.getenv("DEBOUNCE_SECONDS", "30"))
    log_level = log_level or os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE")

    setup_logging(log_level, log_file)

    logger.info("Starting The Bridge service")
    logger.info(f"Atlas URL: {atlas_url}")
    logger.info(f"Debounce: {debounce}s")

    # Initialize Atlas client
    atlas_client = AtlasClient(atlas_url, api_key)

    # Health check
    if not atlas_client.health_check():
        logger.warning("Atlas health check failed, but continuing anyway")

    # Parse watch configurations
    if watch_paths:
        configs = [WatchConfig(p) for p in watch_paths.split(";")]
    else:
        configs = parse_watch_paths()

    if not configs:
        logger.error("No watch paths configured!")
        raise typer.Exit(1)

    # Set up file watcher
    processed_subdir = os.getenv("PROCESSED_SUBDIR", "processed")
    move_after_sync = os.getenv("MOVE_AFTER_SYNC", "true").lower() == "true"

    handler = DebouncedFileHandler(
        atlas_client=atlas_client,
        debounce_seconds=debounce,
        processed_subdir=processed_subdir,
        move_after_sync=move_after_sync,
    )

    observer = Observer()

    for config in configs:
        if not config.path.exists():
            logger.warning(f"Path does not exist, skipping: {config.path}")
            continue

        handler.add_watch_config(config)
        observer.schedule(handler, str(config.path), recursive=True)
        logger.info(f"Watching: {config.path} (tags: {config.tags})")

    observer.start()
    logger.info("Bridge service is running. Press Ctrl+C to stop.")

    try:
        observer.join()
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Shutting down...")

    observer.join()


@app.command()
def test(
    atlas_url: str = typer.Option(..., help="Atlas API URL"),
    test_file: Path = typer.Option(..., help="Test file to sync"),
):
    """Test sync with a single file."""
    setup_logging("INFO", None)

    api_key = os.getenv("ATLAS_API_KEY")
    atlas_client = AtlasClient(atlas_url, api_key)

    logger.info(f"Testing sync of: {test_file}")

    content = test_file.read_text()
    payload = create_note_payload(test_file, content, ["test"], "hyprnote")

    success = atlas_client.ingest_note(payload)
    if success:
        logger.info("Test successful!")
        raise typer.Exit(0)
    else:
        logger.error("Test failed!")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
