# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-07-30-privacy-architecture/spec.md

## Technical Requirements

- The `privacy.py` module will use a regular expression-based approach to detect PII.
- The module will expose two functions:
  - `detect_pii(text: str) -> list[tuple[str, str]]`: Takes a string of text and returns a list of tuples, where each tuple contains the detected PII and its type (e.g., `("John Doe", "PERSON")`).
  - `redact_pii(text: str) -> str`: Takes a string of text and returns the text with PII redacted.
- The module will read the `config.json` file to get the PII detection and redaction settings.

## External Dependencies

- **re:** The Python library for regular expressions.
  - **Justification:** Required for PII detection.
