"""Main batch processor for new files."""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import Config
from .models import (
    NoteMeta, parse_markdown_with_frontmatter, write_markdown,
    generate_note_id, determine_source_from_path, determine_raw_type_from_path
)
from .llm_client import LLMClient
from .classifier import Classifier
from .router import Router
from .index_db import IndexDB

logger = logging.getLogger(__name__)


class ProcessingStats:
    """Statistics for a processing run."""

    def __init__(self):
        self.files_scanned = 0
        self.files_processed = 0
        self.files_skipped = 0
        self.errors = []
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None

    def finish(self):
        """Mark processing as finished."""
        self.end_time = datetime.now()

    @property
    def duration_seconds(self) -> float:
        """Get processing duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()


class Processor:
    """Main processor for scanning and processing new files."""

    def __init__(self, config: Config):
        """
        Initialize processor.

        Args:
            config: Configuration object
        """
        self.config = config
        self.llm_client = LLMClient(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model
        )
        self.classifier = Classifier(self.llm_client)
        self.router = Router(config)
        self.index_db = IndexDB(config.state_dir)

    def _find_files_to_process(self) -> List[Path]:
        """
        Find all files in capture directories that need processing.

        Returns:
            List of file paths that haven't been processed
        """
        files_to_process = []

        # Supported file extensions
        supported_extensions = {'.txt', '.md', '.rtf'}

        for capture_dir in self.config.capture_dirs:
            if not capture_dir.exists():
                logger.debug(f"Capture directory does not exist: {capture_dir}")
                continue

            logger.debug(f"Scanning capture directory: {capture_dir}")

            # Find all supported files
            for file_path in capture_dir.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    # Get file modification time
                    try:
                        mtime = file_path.stat().st_mtime

                        # Check if already processed
                        if not self.index_db.has_been_processed(file_path, mtime):
                            files_to_process.append(file_path)

                    except OSError as e:
                        logger.warning(f"Error getting file stats for {file_path}: {e}")

        logger.info(f"Found {len(files_to_process)} files to process")
        return files_to_process

    def _process_single_file(self, file_path: Path, stats: ProcessingStats) -> bool:
        """
        Process a single file.

        Args:
            file_path: Path to the file to process
            stats: Processing statistics object to update

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            logger.debug(f"Processing file: {file_path}")

            # Get file modification time
            mtime = file_path.stat().st_mtime
            created_at = datetime.fromtimestamp(mtime)

            # Determine source and raw type from path
            source = determine_source_from_path(file_path)
            raw_type = determine_raw_type_from_path(file_path)

            # Parse the file content
            existing_meta, body = parse_markdown_with_frontmatter(file_path)

            # If no existing meta, create new basic metadata
            if existing_meta is None:
                note_id = generate_note_id(file_path, mtime)
            else:
                note_id = existing_meta.id

            # Use LLM to classify and summarize
            classification_result = self.classifier.classify_and_summarize(body)

            # Create complete metadata
            meta = NoteMeta(
                id=note_id,
                source=source,
                raw_type=raw_type,
                class_type=classification_result.class_type,
                category=classification_result.category,
                project=classification_result.project,
                created_at=created_at,
                processed_at=datetime.now(),
                summary=classification_result.summary,
                tags=classification_result.tags,
                original_path=str(file_path.absolute())
            )

            # Route the note to its destination
            dest_path = self.router.route_note(meta, body)

            # Write the processed note
            write_markdown(dest_path, meta, body)

            # Mark as processed in the database
            self.index_db.mark_processed(file_path, mtime, dest_path)

            logger.info(f"Successfully processed {file_path.name} -> {dest_path.relative_to(self.config.vault_root)}")
            return True

        except Exception as e:
            error_msg = f"Error processing {file_path}: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
            return False

    def process_once(self) -> ProcessingStats:
        """
        Run a single batch processing cycle.

        Scans all capture directories and processes any new or changed files.

        Returns:
            ProcessingStats object with information about the run
        """
        logger.info("Starting batch processing cycle")
        stats = ProcessingStats()

        try:
            # Find files to process
            files_to_process = self._find_files_to_process()
            stats.files_scanned = len(files_to_process)

            if not files_to_process:
                logger.info("No new files to process")
                stats.finish()
                return stats

            # Process each file
            for file_path in files_to_process:
                if self._process_single_file(file_path, stats):
                    stats.files_processed += 1
                else:
                    stats.files_skipped += 1

                # Small delay between files to be gentle on APIs
                time.sleep(0.5)

            logger.info(f"Processing complete: {stats.files_processed} processed, {stats.files_skipped} skipped")

        except Exception as e:
            error_msg = f"Fatal error during processing: {e}"
            logger.error(error_msg)
            stats.errors.append(error_msg)

        finally:
            stats.finish()

        return stats

    def workday_loop(self, interval_seconds: int = 300) -> None:
        """
        Run processing in a loop, suitable for a workday session.

        Args:
            interval_seconds: Seconds to wait between processing cycles
        """
        logger.info(f"Starting workday loop with {interval_seconds}s interval")
        logger.info("Press Ctrl+C to stop")

        try:
            while True:
                cycle_start = time.time()

                # Run one processing cycle
                stats = self.process_once()

                # Log summary
                logger.info(
                    f"Cycle completed in {stats.duration_seconds:.1f}s: "
                    f"{stats.files_processed} processed, {stats.files_skipped} skipped"
                )

                if stats.errors:
                    logger.warning(f"Encountered {len(stats.errors)} errors")

                # Calculate sleep time (accounting for processing time)
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, interval_seconds - cycle_duration)

                if sleep_time > 0:
                    logger.debug(f"Sleeping for {sleep_time:.1f}s")
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Workday loop stopped by user")
        except Exception as e:
            logger.error(f"Workday loop stopped due to error: {e}")
            raise