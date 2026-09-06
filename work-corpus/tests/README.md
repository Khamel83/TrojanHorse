# Tests

From the repository root:

```bash
PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m pytest -q work-corpus/tests
```

The current full suite is the verification gate for the local corpus. It covers
the immutable source boundary, normalization, MCP merge behavior, OneNote
adapter contracts, Zoom coverage, transcription state, reports, and queries.
