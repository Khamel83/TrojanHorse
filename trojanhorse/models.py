"""Data models for TrojanHorse notes and metadata."""

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Any, Dict, List
import logging

import yaml

logger = logging.getLogger(__name__)


@dataclass
class NoteMeta:
    """Metadata for a processed note."""
    id: str
    source: str            # "drafts" | "macwhisper" | "clipboard" | "unknown"
    raw_type: str          # "email_dump" | "slack_dump" | "voice_note" | "meeting_transcript" | "other"
    class_type: str        # "work" | "personal"
    category: str          # "email" | "slack" | "meeting" | "idea" | "task" | "log" | "other"
    project: str           # "warn_dashboard" | "hub_ops" | "none" | etc.
    created_at: datetime
    processed_at: datetime
    summary: str
    tags: List[str]
    original_path: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NoteMeta":
        """Create NoteMeta from dictionary, handling datetime conversion."""
        # Convert string timestamps to datetime objects
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("processed_at"), str):
            data["processed_at"] = datetime.fromisoformat(data["processed_at"])

        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert NoteMeta to dictionary for YAML serialization."""
        return asdict(self)


def generate_note_id(original_path: Path, mtime: float) -> str:
    """Generate a unique note ID based on file path and modification time."""
    timestamp = datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%SZ")
    path_hash = hashlib.sha256(str(original_path).encode()).hexdigest()[:8]
    return f"{timestamp}_{path_hash}"


def parse_markdown_with_frontmatter(path: Path) -> Tuple[Optional[NoteMeta], str]:
    """
    Parse a markdown file and extract frontmatter if present.

    Returns:
        (NoteMeta | None, body_text)
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Try with latin-1 as fallback
        content = path.read_text(encoding="latin-1")

    # Check for YAML frontmatter
    if content.startswith("---\n"):
        try:
            # Find the end of frontmatter
            end_idx = content.find("\n---\n", 4)
            if end_idx == -1:
                # No closing --- found, treat entire file as body
                return None, content

            frontmatter_str = content[4:end_idx]
            body = content[end_idx + 5:]  # Skip the closing ---\n

            # Parse YAML
            frontmatter_data = yaml.safe_load(frontmatter_str)
            if not isinstance(frontmatter_data, dict):
                logger.warning(f"Invalid frontmatter in {path}, treating as body only")
                return None, content

            try:
                meta = NoteMeta.from_dict(frontmatter_data)
                return meta, body
            except Exception as e:
                logger.warning(f"Failed to parse NoteMeta from {path}: {e}")
                return None, content

        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML frontmatter in {path}: {e}")
            return None, content

    # No frontmatter found
    return None, content


def write_markdown(path: Path, meta: NoteMeta, body: str) -> None:
    """
    Write a markdown file with YAML frontmatter.

    Args:
        path: Destination path
        meta: Note metadata
        body: Markdown body content
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Build frontmatter
    frontmatter_data = meta.to_dict()

    # Convert datetime objects to ISO strings for YAML serialization
    if isinstance(frontmatter_data["created_at"], datetime):
        frontmatter_data["created_at"] = frontmatter_data["created_at"].isoformat()
    if isinstance(frontmatter_data["processed_at"], datetime):
        frontmatter_data["processed_at"] = frontmatter_data["processed_at"].isoformat()

    frontmatter_str = yaml.dump(frontmatter_data, default_flow_style=False, sort_keys=False)

    # Write file
    content = f"---\n{frontmatter_str}---\n\n{body}"
    path.write_text(content, encoding="utf-8")
    logger.debug(f"Wrote markdown file: {path}")


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to a URL-friendly slug."""
    # Basic slugification - convert to lowercase, replace spaces with underscores
    # and remove special characters
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '_', text)
    return text.strip('_')[:max_length] or 'untitled'


def determine_source_from_path(path: Path) -> str:
    """Heuristically determine the source type from file path."""
    path_str = str(path).lower()

    if "draft" in path_str:
        return "drafts"
    elif "transcript" in path_str or "whisper" in path_str:
        return "macwhisper"
    elif "clipboard" in path_str:
        return "clipboard"
    else:
        return "unknown"


def determine_raw_type_from_path(path: Path) -> str:
    """Heuristically determine the raw content type from file path."""
    path_str = str(path).lower()

    if "transcript" in path_str:
        return "meeting_transcript"
    elif "email" in path_str:
        return "email_dump"
    elif "slack" in path_str:
        return "slack_dump"
    else:
        return "voice_note"  # Default assumption