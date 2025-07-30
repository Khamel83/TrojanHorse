# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-07-30-export-system/spec.md

## Technical Requirements

- The `export.py` module will interact with the SQLite database to retrieve transcribed text and analysis results.
- The module will expose two functions:
  - `export_to_markdown(data: list[dict], file_path: str)`: Takes a list of dictionaries (representing transcriptions/analysis) and exports them to a Markdown file.
  - `export_to_json(data: list[dict], file_path: str)`: Takes a list of dictionaries and exports them to a JSON file.
- The module will allow users to specify the output file path and format.

## External Dependencies

- **sqlite3:** Built-in Python library for SQLite database interaction.
  - **Justification:** Required for retrieving transcribed data.
- **json:** Built-in Python library for JSON handling.
  - **Justification:** Required for exporting data to JSON format.
