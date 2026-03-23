"""Markdown parsing utilities."""

import logging
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def extract_title(content: str, file_path: Optional[Path] = None) -> str:
    """
    Extract title from markdown content.

    First looks for a first-level heading (# Title),
    then uses filename if provided.

    Args:
        content: Markdown content
        file_path: Optional file path to use as fallback

    Returns:
        Extracted title
    """
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()

    if file_path:
        return file_path.stem

    return "Untitled"


def extract_tags_from_content(content: str) -> List[str]:
    """
    Extract hashtags from markdown content.

    Looks for #tag patterns (excluding markdown headings).

    Args:
        content: Markdown content

    Returns:
        List of extracted tags (without # prefix)
    """
    # Match hashtags but not markdown headers
    # This regex finds #word patterns that aren't at the start of a line
    tag_pattern = r'(?:^|\s)#([a-zA-Z0-9_-]+)'

    # First, let's filter out markdown headers
    lines = content.split('\n')
    text_lines = []
    for line in lines:
        # Skip markdown headers (lines starting with #)
        if not line.strip().startswith('#'):
            text_lines.append(line)

    text_content = '\n'.join(text_lines)

    # Find all tags
    tags = set(re.findall(tag_pattern, text_content))
    return list(tags)


def extract_frontmatter(content: str) -> tuple[Optional[dict], str]:
    """
    Extract YAML frontmatter from markdown.

    Args:
        content: Raw markdown content

    Returns:
        Tuple of (frontmatter_dict or None, body_content)
    """
    if not content.startswith("---\n"):
        return None, content

    try:
        end_idx = content.find("\n---\n", 4)
        if end_idx == -1:
            return None, content

        import yaml
        frontmatter_str = content[4:end_idx]
        body = content[end_idx + 5:]

        frontmatter = yaml.safe_load(frontmatter_str)
        if not isinstance(frontmatter, dict):
            return None, content

        return frontmatter, body

    except Exception as e:
        logger.warning(f"Failed to parse frontmatter: {e}")
        return None, content


def combine_frontmatter_tags(
    content: str,
    additional_tags: Optional[List[str]] = None
) -> List[str]:
    """
    Combine tags from frontmatter and additional tags.

    Args:
        content: Markdown content (may have frontmatter)
        additional_tags: Additional tags to include

    Returns:
        Combined list of unique tags
    """
    tags = set(additional_tags or [])

    # Try to extract tags from frontmatter
    frontmatter, _ = extract_frontmatter(content)
    if frontmatter and "tags" in frontmatter:
        if isinstance(frontmatter["tags"], list):
            tags.update(frontmatter["tags"])
        elif isinstance(frontmatter["tags"], str):
            tags.update([t.strip() for t in frontmatter["tags"].split(",")])

    # Also extract hashtags from content
    content_tags = extract_tags_from_content(content)
    tags.update(content_tags)

    return list(tags)
