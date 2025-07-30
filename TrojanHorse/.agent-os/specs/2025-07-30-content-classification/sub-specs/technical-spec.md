# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-07-30-content-classification/spec.md

## Technical Requirements

- The `classify.py` module will use a keyword-based approach to categorize text.
- The module will expose two functions:
  - `categorize(text: str, categories: dict[str, list[str]]) -> list[str]`: Takes a string of text and a dictionary of categories and keywords, and returns a list of matching categories.
  - `extract_action_items(text: str) -> list[str]`: Takes a string of text and returns a list of action items.
- The module will read the `config.json` file to get the user-defined categories.

## External Dependencies

- **re:** The Python library for regular expressions.
  - **Justification:** Required for keyword matching and action item extraction.
