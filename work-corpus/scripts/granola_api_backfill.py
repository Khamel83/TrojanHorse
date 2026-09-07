#!/usr/bin/env python3
"""Run the Granola REST backfill from a checkout or over SSH."""

from work_corpus.granola_api import main


if __name__ == "__main__":
    raise SystemExit(main())
