# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-07-30-cloud-intelligence/spec.md

## Technical Requirements

- The `cloud_analyze.py` module will use the `requests` library to interact with the OpenRouter API.
- The module will expose a function:
  - `analyze(text: str, prompt: str) -> str`: Takes a string of text and a prompt and returns the analysis from the cloud AI.
- The module will read the `config.json` file to get the OpenRouter API key.

## External Dependencies

- **requests:** The Python library for making HTTP requests.
  - **Justification:** Required for interacting with the OpenRouter API.
