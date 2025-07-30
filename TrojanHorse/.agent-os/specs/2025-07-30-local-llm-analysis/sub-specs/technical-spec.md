# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-07-30-local-llm-analysis/spec.md

## Technical Requirements

- The `analyze.py` module will use the `ollama` Python library to interact with the Ollama API.
- The module will expose two functions:
  - `summarize(text: str) -> str`: Takes a string of text and returns a summary.
  - `extract_action_items(text: str) -> list[str]`: Takes a string of text and returns a list of action items.
- The module will read the `config.json` file to get the selected Ollama model.

## External Dependencies

- **ollama:** The Python client for the Ollama API.
  - **Justification:** Required for interacting with the local LLM.
