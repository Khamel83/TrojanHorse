"""Client for promoting TrojanHorse notes to Atlas."""

import logging
import os
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class AtlasClient:
    """Client for interacting with Atlas API."""

    def __init__(self, atlas_url: str, api_key: Optional[str] = None, timeout: int = 60):
        """
        Initialize Atlas client.

        Args:
            atlas_url: Base URL for Atlas API (e.g., "http://localhost:8787")
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

    def ingest_notes(self, notes: List[Dict[str, Any]]) -> bool:
        """
        Ingest notes into Atlas.

        Args:
            notes: List of note payloads from TrojanHorse /promote endpoint

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Ingesting {len(notes)} notes into Atlas")

            response = self.session.post(
                f"{self.atlas_url}/ingest/batch",
                json=notes,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"Successfully ingested {result.get('count', len(notes))} notes")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to ingest notes into Atlas: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error ingesting notes: {e}")
            return False


def promote_notes_from_trojanhorse(
    trojanhorse_url: str,
    atlas_client: AtlasClient,
    note_ids: List[str]
) -> int:
    """
    Promote notes from TrojanHorse to Atlas.

    Args:
        trojanhorse_url: URL for TrojanHorse API (e.g., "http://localhost:8765")
        atlas_client: Configured AtlasClient instance
        note_ids: List of note IDs to promote

    Returns:
        Number of notes successfully promoted
    """
    try:
        logger.info(f"Promoting {len(note_ids)} notes from TrojanHorse to Atlas")

        # Step 1: Get notes from TrojanHorse
        logger.info("Fetching notes from TrojanHorse...")
        promote_response = requests.post(
            f"{trojanhorse_url.rstrip('/')}/promote",
            json={"note_ids": note_ids},
            timeout=30
        )
        promote_response.raise_for_status()

        notes_payload = promote_response.json()["items"]
        logger.info(f"Retrieved {len(notes_payload)} notes from TrojanHorse")

        if not notes_payload:
            logger.warning("No notes found to promote")
            return 0

        # Step 2: Ingest notes into Atlas
        logger.info("Ingesting notes into Atlas...")
        if atlas_client.ingest_notes(notes_payload):
            logger.info(f"Successfully promoted {len(notes_payload)} notes")
            return len(notes_payload)
        else:
            logger.error("Failed to ingest notes into Atlas")
            return 0

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to promote notes: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error promoting notes: {e}")
        return 0


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