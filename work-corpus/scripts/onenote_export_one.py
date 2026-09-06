#!/usr/bin/env python3
"""Render one MS-ONESTORE section into the corpus adapter's text contract.

The upstream exporter is directory-oriented.  The corpus normalizer needs a
single input file to produce a single derived Markdown file, so this wrapper
uses the installer's parser and Markdown renderer directly and adds stable
section/page locators.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from onenote_export.converter.markdown import MarkdownConverter
from onenote_export.parser.content_extractor import extract_section
from onenote_export.parser.one_store import OneStoreParser
from onenote_export.utils import section_name_from_filename


def _heading(value: str, fallback: str) -> str:
    text = " ".join(value.split()).strip()
    return text or fallback


def render(source: Path) -> str:
    parsed = OneStoreParser(source).parse()
    section = extract_section(parsed)
    section.name = section_name_from_filename(source.name)
    converter = MarkdownConverter(Path("."))

    chunks = [f"# Section: {_heading(section.name, 'Untitled')}\n"]
    for index, page in enumerate(section.pages, start=1):
        title = _heading(page.title, f"Untitled {index}")
        chunks.append(f"## Page: {title}\n")
        rendered = converter.render_page(page).strip()
        if rendered:
            chunks.append(rendered + "\n")

    return "\n".join(chunks).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    text = render(args.input.expanduser().resolve())
    args.output.expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.expanduser().resolve().write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
