"""OPML to Markdown converter."""

import logging
import xml.etree.ElementTree as ET
from typing import Optional

logger = logging.getLogger(__name__)


def opml_to_markdown(opml_content: str) -> str:
    """
    Convert OPML outline to nested markdown bullets.

    Args:
        opml_content: Raw OPML XML content

    Returns:
        Markdown string with nested bullet lists
    """
    try:
        root = ET.fromstring(opml_content)
        lines = []

        # Find the body element
        body = root.find(".//body")
        if body is None:
            logger.warning("No body element found in OPML")
            return ""

        # Process all top-level outlines
        for outline in body.findall(".//outline"):
            _process_outline(outline, lines, depth=0)

        return "\n".join(lines)

    except ET.ParseError as e:
        logger.error(f"Failed to parse OPML: {e}")
        raise ValueError(f"Invalid OPML: {e}")


def _process_outline(outline: ET.Element, lines: list, depth: int):
    """
    Recursively process an outline element.

    Args:
        outline: XML element for outline
        lines: List to append markdown lines to
        depth: Current nesting depth (for indentation)
    """
    # Get text content
    text = outline.get("text", "")
    if not text:
        text = outline.get("_title", "")

    if text:
        # Create bullet with appropriate indentation
        indent = "  " * depth
        lines.append(f"{indent}- {text}")

    # Process children (nested outlines)
    for child in outline.findall(".//outline"):
        # Only process direct children by checking if they're nested
        # This is a simplification - proper OPML may need more complex handling
        _process_outline(child, lines, depth + 1)
        break  # Only process first level to avoid duplication


def opml_file_to_markdown(file_path: str) -> str:
    """
    Read an OPML file and convert to markdown.

    Args:
        file_path: Path to OPML file

    Returns:
        Markdown string
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return opml_to_markdown(content)
