# Technical Specification

This is the technical specification for the spec detailed in @.agent-os/specs/2025-07-30-cost-optimization/spec.md

## Technical Requirements

- The `router.py` module will expose a function:
  - `choose_ai_service(cost_preference: str, performance_preference: str) -> str`: Takes user preferences and returns either "local" or "cloud".
- The module will read the `config.json` file to get the user's cost and performance preferences.

## External Dependencies

- None.
