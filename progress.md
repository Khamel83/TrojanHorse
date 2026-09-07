# Session Progress Log: TrojanHorse → "The Bridge"

> Tracks progress through continuous plan execution. Use `bd ready` to see next tasks.

## Current corpus status — 2026-09-04

The old Bridge log below is historical. The current project is the separate,
local-only work corpus described in `CONTEXT.md`.

- [x] Reviewed the raw `data/` inventory without mutating it.
- [x] Resolved local access status for Capacities, Notion, OneNote, Zoom, and
  formal records.
- [x] Committed the design specification and Antigravity adversarial review.
- [x] Committed the implementation plan and Gemini 3.1 Pro review.
- [x] Promote the reviewed bootstrap scaffold into the root `work-corpus/`
  package (`fb67385`; Task 0 review approved).
- [x] Establish the immutable local boundary and package entry point
  (`a6fe51f`, `df5b3c5`, `4edaa06`; Task 1 review approved).
- [x] Build the immutable source manifest, source-version ledger, scope gates,
  Zoom meeting grouping, legacy migration retention, and derived-path boundary
  (`a115057` through `add7e97`; Task 2 package suite: 56 passed).
- [x] Define the provenance-first SQLite schema, deterministic evidence/review
  APIs, FTS table, current-task boundary, and safe legacy migration
  (`37e50d6`, `bf3b7a6`, `800ad7c`, `6773540`; Task 3 review approved).
- [x] Run the full local extraction in the order defined by the amended plan:
  315 source versions normalized, 418 scope-review records retained, 1
  optional parser case unsupported, and 0 parsing errors.
- [x] Run the complete Zoom coverage pass: 4 existing media-bearing transcript
  groups linked, 68 transcript-only groups kept separate, 231 eligible media
  items terminally `blocked`, 114 raw artifacts visible, and 0 eligible media
  without a terminal status.
- [x] Run the 29-file OneNote acceptance pass. The converter is unavailable,
  so 29 files are `blocked` and 0 pages were extracted; the reviewed expected
  result is 295 pages.
- [x] Rebuild and verify FTS and relationship indexes, run the seven-category
  Work-scoped query suite, and confirm the real current-task view has 0 rows.
- [x] Compare the raw corpus before and after acceptance: 1,414 files and
  58,965,738,600 bytes match with zero path, size, mtime, or hash mismatches.

## Operational update — 2026-09-07

- [x] Correct the Wispr Flow importer to map `meetings[].start` to event dates,
  the saved capture envelope's `captured_at` to local capture/retrieval dates,
  and `end`/`modified_at` to separate derived metadata. The live local result
  is 13/13 capture dates, 12/13 meeting event dates, 12/12 meeting end dates,
  13/13 provider-modified dates, and 13/13 retrieval dates. The one scratchpad
  has no event date in its source object; no event date was invented.
- [x] Supersede the 13 stale unknown-Wispr-date review rows created by the old
  mapping and refresh their derived metadata without changing raw files.
- [x] Apply the initial safe first-pass triage: 4,411 policy-stable rows
  resolved, 622 provisional duplicate/version display choices retained, and 68
  grouped exception items left in the response sheet for the subsequent policy
  decision.
- [x] Apply the approved unified-corpus policy pass: resolve all 68 grouped
  exception rows without changing raw files, include all nonblank parseable
  scopes in the default `All` query, preserve original labels as provenance,
  record 48 ambiguous titles as generic topic labels, and accept the one Zoom
  partial result. The residual ledger now has 0 pending entries.

See `docs/LOCAL_WORK_CORPUS_STATUS.md` and `docs/REMAINING_WORK.md` for the
current boundary. The older Bridge log below is historical.

Current authoritative documents:

- `CONTEXT.md`
- `docs/superpowers/specs/2026-09-04-local-work-corpus-design.md`
- `docs/superpowers/plans/2026-09-04-local-work-corpus-implementation.md`
- `01_INVENTORY/coverage_and_gaps.md`

Tasks 0–9 are mechanically accepted. The remaining operational gates are a
local OneNote converter and a verified local transcription engine. Do not run
the old Atlas bridge against `data/`.

Acceptance artifacts:

- `work-corpus/corpus/reports/status.json`
- `work-corpus/corpus/reports/what_we_have_and_need.md`
- `work-corpus/state/transcription_queue.csv`
- `work-corpus/state/raw_immutability.json`

---

## Historical bridge log — not current project status

The following entries describe the retired Atlas bridge work. They are kept
for provenance only. Do not use them as instructions for the local work
corpus.

## Session History

### 2026-02-02 - Implementation Complete

**Phase 1: Cleanup - ✅ COMPLETED**
- Removed entire `src/` directory (Mac-specific code)
- Removed vault processing: `classifier.py`, `router.py`, `processor.py`, `rag.py`, `index_db.py`, `meeting_synthesizer.py`
- Removed web UI: `static/`, `templates/`, `notes/`, `docs/`, `.agent-os/`
- Removed documentation: `CLAUDE.md`, `README.md`, `MACHINE_SETUP.md`, `MANUAL_SETUP.md`, `CHANGELOG.md`
- Removed Mac-specific files: `.plist`, setup scripts
- Stripped `models.py` to only keep frontmatter parsing
- Updated `requirements.txt`: removed numpy, added watchdog, python-dotenv, tenacity

**Phase 2: Bridge Service - ✅ COMPLETED**
- Created `bridge/__init__.py`
- Created `bridge/bridge_service.py`:
  - Watchdog-based file watcher
  - Debounced file processing (configurable delay)
  - Support for per-path tags via WATCH_PATHS config
  - Retry logic with tenacity
  - Moves processed files to `processed/` subfolder
  - CLI with `run` and `test` commands
- Updated `atlas_client.py`:
  - Added `ingest_note()` for single note sync
  - Added `create_note_payload()` helper
  - Updated to use `/api/notes/` endpoint

**Phase 3: Vacuum Migration Tool - ✅ COMPLETED**
- Created `bridge/vacuum.py`:
  - CLI with `migrate` and `check` commands
  - Support for `.md`, `.txt`, and `.opml` formats
  - Configurable delay between API calls (rate limiting)
  - Recursive directory scanning
  - Dry-run mode
- Created `bridge/parsers/`:
  - `opml.py`: OPML to markdown converter
  - `markdown.py`: Title extraction, tag extraction, frontmatter parsing

**Phase 4: Environment & Config - ✅ COMPLETED**
- Created `.env.template`:
  - Atlas configuration
  - Watch paths with tag format
  - Debounce and processed folder settings
  - Logging configuration
- Created `systemd/bridge.service`:
  - Systemd service file for deployment
  - Proper environment loading
  - Journal logging

---

## Phase Status

| Phase | Description | Status | Tasks |
|-------|-------------|--------|-------|
| 1 | Cleanup - Remove vault, classifier, UI, audio | ✅ COMPLETED | All unnecessary files removed |
| 2 | Watcher - `bridge_service.py` | ✅ COMPLETED | File watching with debouncing and retry |
| 3 | Vacuum - `vacuum.py` migration tool | ✅ COMPLETED | OPML parser, CLI, rate limiting |
| 4 | Config - `.env.template` and systemd | ✅ COMPLETED | Service file, environment template |

---

## Final Project Structure

```
trojanhorse/
├── bridge/
│   ├── __init__.py
│   ├── bridge_service.py    # Main watcher
│   ├── vacuum.py            # Migration tool
│   └── parsers/
│       ├── __init__.py
│       ├── opml.py          # OPML parser
│       └── markdown.py      # Markdown helpers
├── TrojanHorse/
│   ├── __init__.py
│   ├── api_server.py        # (existing - REST API)
│   ├── atlas_client.py      # UPDATED - single note sync
│   ├── cli.py               # (existing - CLI)
│   ├── config.py            # (existing - config)
│   ├── llm_client.py        # (existing - LLM client)
│   └── models.py            # STRIPPED - frontmatter only
├── systemd/
│   └── bridge.service       # Systemd service file
├── tests/
│   ├── conftest.py
│   ├── test_classifier.py   # (may need cleanup)
│   ├── test_index_db.py     # (may need cleanup)
│   ├── test_models.py
│   ├── test_rag_openrouter.py # (may need cleanup)
│   └── test_router.py       # (may need cleanup)
├── .env.template            # NEW
├── requirements.txt         # UPDATED
└── pyproject.toml           # (existing)
```

---

## Deployment Instructions

### 1. Install Dependencies
```bash
cd /home/ubuntu/github/trojanhorse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.template .env
# Edit .env with your settings
```

### 3. Test Sync
```bash
# Test with a single file
python bridge/bridge_service.py test --atlas-url http://localhost:7444 --test-file /path/to/test.md
```

### 4. Run Migration (Vacuum)
```bash
# Check what would be migrated
python bridge/vacuum.py check /path/to/legacy/notes

# Do the migration
python bridge/vacuum.py migrate /path/to/legacy/notes --tag "Archive" --delay 1
```

### 5. Deploy as Systemd Service
```bash
# Copy service file
sudo cp systemd/bridge.service /etc/systemd/system/

# Reload and start
sudo systemctl daemon-reload
sudo systemctl enable bridge
sudo systemctl start bridge

# Check status
sudo systemctl status bridge
sudo journalctl -u bridge -f
```

---

## Blockers / Dependencies

| Blocker | Impact | Resolution |
|---------|--------|------------|
| Atlas API endpoint | Phase 2 | ✅ Confirmed `/api/notes/` endpoint |
| Atlas auth format | Phase 2 | ✅ Using `X-API-Key` header |

---

## Next Steps

1. **Test bridge_service.py**: Run with test file to verify Atlas sync
2. **Test vacuum.py**: Run in dry-run mode against legacy notes
3. **Deploy to oci-dev**: Use `push-to-cloud` skill to deploy
4. **Clean up old tests**: Remove tests for deleted modules

---

**Last Updated:** 2026-02-02
**Plan Status:** ✅ ALL PHASES COMPLETED
