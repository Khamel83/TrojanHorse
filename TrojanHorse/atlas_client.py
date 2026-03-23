"""Client for promoting notes to Atlas."""

import logging
import os
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AtlasClient:
    """Client for interacting with Atlas API."""

    def __init__(self, atlas_url: str, api_key: Optional[str] = None, timeout: int = 60):
        """
        Initialize Atlas client.

        Args:
            atlas_url: Base URL for Atlas API (e.g., "http://localhost:7444")
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        self.atlas_url = atlas_url.rstrip('/')
        self.api_key = api_key or os.getenv('ATLAS_API_KEY')
        self.timeout = timeout
        self.session = requests.Session()

        # Set up authentication headers
        if self.api_key:
            self.session.headers.update({'X-API-Key': self.api_key})

    def health_check(self) -> bool:
        """Check if Atlas API is healthy."""
        try:
            response = self.session.get(f"{self.atlas_url}/health", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Atlas health check failed: {e}")
            return False

    def ingest_note(self, note: Dict[str, Any]) -> bool:
        """
        Ingest a single note into Atlas.

        Args:
            note: Note payload with title, content, source, tags, created_at

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug(f"Ingesting note: {note.get('title', 'untitled')}")

            response = self.session.post(
                f"{self.atlas_url}/api/notes/",
                json=note,
                timeout=self.timeout
            )
            response.raise_for_status()

            logger.debug(f"Successfully ingested note: {note.get('title')}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to ingest note '{note.get('title', 'unknown')}': {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error ingesting note: {e}")
            return False

    def ingest_notes(self, notes: List[Dict[str, Any]]) -> int:
        """
        Ingest multiple notes into Atlas.

        Args:
            notes: List of note payloads

        Returns:
            Number of successfully ingested notes
        """
        success_count = 0
        for note in notes:
            if self.ingest_note(note):
                success_count += 1
        return success_count


def create_note_payload(
    file_path: Path,
    content: str,
    tags: List[str],
    source: str = "hyprnote"
) -> Dict[str, Any]:
    """
    Create a note payload for Atlas API.

    Args:
        file_path: Path to the note file
        content: Raw markdown content
        tags: Tags to apply
        source: Source identifier

    Returns:
        Dictionary payload for Atlas API
    """
    # Extract title from filename or content
    title = file_path.stem

    # Get file modification time for created_at
    mtime = file_path.stat().st_mtime
    created_at = datetime.fromtimestamp(mtime).isoformat() + 'Z'

    return {
        "title": title,
        "content": content,
        "source": source,
        "tags": tags,
        "created_at": created_at
    }


def get_atlas_client() -> Optional[AtlasClient]:
    """
    Get AtlasClient from environment configuration.

    Returns:
        AtlasClient if configured, None otherwise
    """
    atlas_url = os.getenv('ATLAS_API_URL')
    if not atlas_url:
        logger.warning("ATLAS_API_URL not configured")
        return None

    api_key = os.getenv('ATLAS_API_KEY')
    return AtlasClient(atlas_url, api_key)
