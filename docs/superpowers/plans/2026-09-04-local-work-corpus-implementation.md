# Local Work Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, single-user work-evidence corpus that preserves the existing files, extracts usable evidence, transcribes all eligible Zoom media locally, normalizes projects and people, and supports source-backed queries over historical records plus future local Wispr Flow and Granola inputs.

**Architecture:** Use the already extracted `work-corpus/` package as the application boundary. Keep the repository's old `TrojanHorse/` and `bridge/` code outside the new runtime until its Atlas behavior is explicitly disabled. Store the immutable source manifest, source versions, evidence, canonical entities, review items, task view, and relationships in SQLite; write normalized text and indexes under `corpus/`, never under `data/`. Use FTS and relationship queries for the first useful query path. Defer embeddings until these paths prove insufficient.

**Tech Stack:** Python 3.9+, the existing `work-corpus/` setuptools package, SQLite with FTS5 and WAL, local filesystem adapters, local PDF/Office/OneNote tools where available, `pytest`, and a configured local transcription engine. No cloud service, network call, Redis, RabbitMQ, read replica, public API, or external model call with raw evidence.

Status: Gemini 3.1 Pro review received. Valid revisions are applied. Tasks
0–9 were executed and mechanically accepted on 2026-09-04. The raw corpus is
unchanged. A local OneNote converter and a verified local transcription engine
remain operational gates.

## Execution record

The task sequence completed in order with focused tests, full package tests,
and a commit after each implementation task. The final no-coverage suite is
146 passed. The acceptance run found 1,414 present files (1,394 substantive
and 20 Finder metadata), normalized 315 source versions, retained 418 scope
reviews, and recorded 1 unsupported optional parser case with 0 parse errors.
The Zoom queue accounted for 231 eligible final media items as terminal
`blocked` because no verified local engine was available; 0 eligible items
remain without a terminal status. OneNote recorded 29 blocked files and 0
pages because its converter was unavailable. Raw immutability passed with
zero mismatches. See `work-corpus/corpus/reports/status.json` for the full
machine-readable result.

All test commands in this plan run with `PYTHONPATH=work-corpus/src` from the
repository root. The implementation may later use `python3 -m pip install -e
work-corpus`, but an editable install is not required for the test gates.

## Global Constraints

- TrojanHorse is independent from Atlas. The Atlas bridge is not a dependency and must be disabled or quarantined before corpus processing.
- Email is completely out of scope. Do not import, inspect, authorize, or write email.
- The raw `data/` tree is immutable. All derived output goes to `corpus/` or `state/`.
- The default query scope is `Work`. `Personal`, `Mixed`, and `Unknown` records stay out of the default query.
- Work scope includes confidential personnel and performance records for this single user. Sensitivity is a label, not a reason to send data away.
- The source manifest accounts for every physical file, including Finder metadata, while extraction excludes metadata and discovery reports.
- The machine-discovery tree `data/note-inventory-20260903-142816/` is inventory evidence only. It is not note content and never enters extraction, task extraction, FTS, or other derived indexes.
- Source IDs are stable across reruns. Content changes create a new source version rather than replacing provenance.
- Existing local transcripts are preferred. Every final MP4 or M4A without a usable transcript enters the durable local transcription queue.
- The operator approves one full local transcription run after the preflight report. The runner processes one media item at a time by default. It saves a checkpoint after each item and resumes from the last checkpoint.
- The coverage run does not stop because one item fails. It records `failed`, `partial`, `blocked`, or `artifact` status and continues with the next item.
- The implementation is not complete while an eligible final media item has no existing transcript and no terminal transcription status.
- Current tasks require an explicit commitment and an event or meeting date within the previous 14 calendar days relative to the run date, or a future event date. Export, modification, and transcription dates do not make old material current.
- Exact aliases and regex rules run before any optional local model proposal. The most common valid spelling is selected only from valid names. Ambiguous or risky changes create review items.
- Raw or unreviewed fallback search is permitted only for source records already classified as `Work`. Returned snippets redact URL-like and secret-like values.
- No automatic historical task backfill, raw-file movement, raw-file deletion, external transcription, or public corpus research.

---

## Repository reality and reuse map

The root repository is a legacy baseline, not a working implementation of this corpus:

- `README.md` describes the old vault/RAG processor.
- `progress.md` describes the later Atlas bridge migration.
- `TrojanHorse/cli.py` still imports modules that are no longer present, including the old processor and RAG modules.
- `TrojanHorse/atlas_client.py`, `bridge/bridge_service.py`, `bridge/vacuum.py`, `systemd/bridge.service`, and `systemd/com.bridge.service.plist` are Atlas-related legacy paths.
- The root `tests/` directory contains tests for removed modules and must not be used as evidence that the new corpus is tested.
- `Omar_Work_Corpus_Bootstrap_v1/work-corpus/` already contains a separate package, schema candidate, local inventory, normalization, Zoom, transcription, report, and MCP-ingest code. It also contains email-specific code and a first-class `career_claim` table. Those parts are reference material only and require the changes below.

The new runtime will be promoted into a root `work-corpus/` package so it can reuse the bootstrap package layout without silently replacing the legacy root package. The first implementation does not modify the raw data or copy the entire bootstrap package blindly. The promoted scaffold is not runnable until the local boundary task removes its out-of-scope surfaces.

### Planned file map

- Create or modify `work-corpus/config.json`: non-sensitive defaults and explicit source-root rules.
- Create `work-corpus/config.local.json` from the existing local example, ignored by Git: machine paths and local tool commands only.
- Promote `work-corpus/config.local.example.json` from the reviewed bootstrap example.
- Modify `work-corpus/src/work_corpus/config.py`: validate root paths, source-root precedence, derived-output paths, and local-only transcription settings.
- Modify `work-corpus/src/work_corpus/util.py`: stable IDs, path containment, atomic derived writes, date parsing, text decoding, and URL/secret redaction helpers.
- Modify `work-corpus/src/work_corpus/db.py`: the SQLite schema, migrations, indexes, views, and connection policy.
- Modify `work-corpus/src/work_corpus/inventory.py`: explicit roots, complete physical-file accounting, discovery exclusion, source versions, and scope proposals.
- Modify `work-corpus/src/work_corpus/normalize.py`: safe text extraction, provenance, parser status, and signed-URL removal from derived searchable text.
- Modify `work-corpus/src/work_corpus/zoom.py`: dated-folder meeting identity, nested recording handling, existing-transcript matching, and transcription-job creation.
- Modify `work-corpus/src/work_corpus/transcription.py`: local-only engine allowlist, one run-level approval gate, sequential resumable coverage, status transitions, and quality checks.
- Modify `work-corpus/src/work_corpus/report.py`: coverage, parser failures, review queues, transcription status, and freshness reports.
- Modify `work-corpus/src/work_corpus/mcp_ingest.py`: local Wispr Flow and Granola snapshots with provider IDs and checkpoints.
- Modify `work-corpus/src/work_corpus/cli.py`: commands for inventory, normalize, Zoom scan, local transcription, report, query, and local MCP import; remove email commands.
- Create `work-corpus/src/work_corpus/entities.py`: canonical projects, people, organizations, aliases, mentions, and merge proposals.
- Create `work-corpus/src/work_corpus/tasks.py`: explicit task extraction, current-task view, and historical-task rules.
- Create `work-corpus/src/work_corpus/query.py`: scope-enforced exact, relationship, and fallback retrieval with evidence labels.
- Create `work-corpus/src/work_corpus/onenote.py`: the selected local `.one` converter adapter and page-location mapping.
- Create `work-corpus/tests/` fixtures and tests. Do not repurpose the stale root tests until the legacy package has a separate cleanup decision.
- Create `docs/adr/0001-local-work-corpus-boundary.md`, `CONTEXT.md`, and a revised `README.md` only after this plan passes review. There is no current `content.md`; do not invent one merely to preserve the old request wording.

The configuration module defines these small value types before any adapter is
implemented:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class SourceRoot:
    key: str
    relative_path: str
    source_system: str
    precedence: int
    enabled: bool = True

@dataclass(frozen=True)
class SourceRootMatch:
    root: Optional[SourceRoot]
    relative_path: str
    kind: str
```

`classify_root` returns `SourceRootMatch`; it never returns a bare string that
would allow an adapter to bypass the explicit-root registry.

The bootstrap files `work-corpus/src/work_corpus/email_ingest.py`, the email commands in `cli.py`, email schemas, Outlook scripts, and email runbooks are not in the planned runtime. The bootstrap `career_claim` schema is not carried into the initial database.

## Task 0: Promote the reviewed bootstrap scaffold — completed (`fb67385`)

**Files:**

- Promote: `work-corpus/pyproject.toml`
- Promote: `work-corpus/config.json`
- Promote: `work-corpus/config.local.example.json`
- Promote: `work-corpus/requirements-optional.txt`
- Promote: `work-corpus/src/work_corpus/__init__.py`
- Promote: `work-corpus/src/work_corpus/__main__.py`
- Promote and modify: `work-corpus/src/work_corpus/cli.py` as the local CLI entry point
- Promote: `work-corpus/src/work_corpus/config.py`
- Promote: `work-corpus/src/work_corpus/db.py`
- Promote: `work-corpus/src/work_corpus/doctor.py`
- Promote: `work-corpus/src/work_corpus/inventory.py`
- Promote: `work-corpus/src/work_corpus/mcp_ingest.py`
- Promote: `work-corpus/src/work_corpus/normalize.py`
- Promote: `work-corpus/src/work_corpus/report.py`
- Promote: `work-corpus/src/work_corpus/transcription.py`
- Promote: `work-corpus/src/work_corpus/util.py`
- Promote: `work-corpus/src/work_corpus/zoom.py`
- Promote: `work-corpus/tests/README.md`
- Promote: `work-corpus/tests/fixtures/sample.vtt`
- Promote: `work-corpus/tests/test_util.py` after retaining only the date-hint and VTT-conversion tests

Promote the listed package files from
`Omar_Work_Corpus_Bootstrap_v1/work-corpus/`. Promote the bootstrap `cli.py`
as a starting point. Remove its email import, email command, email pipeline
call, and email-only paths before the first import or execution. Do not copy
`email_ingest.py`, email schemas, Outlook scripts, email requirements, email
runbooks, `.pyc` files, or any data. Do not use a wildcard copy. The copied
`config.py` and `db.py` are untrusted candidates until Tasks 1 and 3 remove
their email and career-claim surfaces. The promoted utility fixture and tests
are safe reuse. Do not promote the bootstrap `test_pipeline.py` unchanged
because it imports email and creates an email fixture.

**Interfaces:**

- The promoted package has the existing `work_corpus` setuptools entry point.
- `PYTHONPATH=work-corpus/src python -m work_corpus --help` imports without an email module and lists only local corpus command names.

- [ ] Create the listed directories with `mkdir -p`.
- [ ] Copy the listed package files one by one from `Omar_Work_Corpus_Bootstrap_v1/work-corpus/` into the root `work-corpus/` package. Use the exact paths listed above.
- [ ] Copy `tests/fixtures/sample.vtt` and the non-email date/VTT tests from the bootstrap test set. Do not copy `sample.eml`, `test_email.py`, or the email portion of `test_pipeline.py`.
- [ ] Promote the bootstrap `cli.py`, remove its email import, email command, email pipeline call, and email-only paths, and retain the local command names `inventory`, `normalize`, `zoom-scan`, `transcribe`, `report`, `query`, and `mcp-import`. It must not import Atlas or email modules.
- [ ] Confirm that `work-corpus/src/work_corpus/email_ingest.py` and `work-corpus/tests/fixtures/sample.eml` do not exist.
- [ ] Run `PYTHONPATH=work-corpus/src python -m work_corpus --help` and confirm that it exits 0 without importing email or Atlas.
- [ ] Confirm that no path under `data/` was read or written by the scaffold operation.
- [ ] Commit the untrusted scaffold with `git commit -m "chore: promote work corpus package scaffold"`.

## Task 1: Lock the local boundary and package entry point — completed (`4edaa06`)

**Files:**

- Create: `work-corpus/.gitignore`
- Modify: `work-corpus/config.json`
- Modify: `work-corpus/config.local.example.json`
- Modify: `work-corpus/src/work_corpus/config.py`
- Modify: `work-corpus/src/work_corpus/cli.py`
- Create: `work-corpus/tests/test_boundary.py`
- Inspect only: `TrojanHorse/atlas_client.py`, `bridge/bridge_service.py`, `bridge/vacuum.py`, `systemd/bridge.service`, `systemd/com.bridge.service.plist`

**Interfaces:**

- `load_config(root: Path) -> Config` returns a configuration with `root`, `data_dir`, `corpus_dir`, `state_dir`, explicit `source_roots`, and local-only tool settings.
- `Config.source_root(name: str) -> SourceRoot` returns the configured root or raises a clear configuration error.
- `Config.assert_derived_path(path: Path) -> None` rejects any output path inside `data/`.
- `cli.main(argv: Optional[list[str]]) -> int` exposes only local corpus commands. It must not import Atlas or email modules.

- [ ] Write `test_boundary.py::test_config_resolves_data_and_derived_roots` and assert that `data_dir` is the repository `data/` directory, `corpus_dir` is outside it, and `state_dir` is outside it.
- [ ] Write `test_boundary.py::test_derived_path_rejects_data_child` and assert that a path under `data/` raises the configuration error.
- [ ] Write `test_boundary.py::test_cli_command_set_has_no_email_or_atlas_command` and assert that the parser contains `inventory`, `normalize`, `zoom-scan`, `transcribe`, `report`, `query`, and `mcp-import`, but not `email-import`, `promote-to-atlas`, or an Atlas URL option.
- [ ] Write `test_boundary.py::test_local_transcription_is_the_only_allowed_transcription_mode` and assert that configuration rejects remote provider names and accepts an explicit local executable or a supported local engine.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_boundary.py`. Expected result before implementation: the new tests fail because the package still has email and old boundary behavior.
- [ ] Implement the smallest configuration and CLI changes. Do not delete legacy files in this task. Record the required manual service check in `state/` only when a real run is authorized.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_boundary.py`. Expected result: all boundary tests pass and no file under `data/` is created or modified.
- [ ] Commit only the boundary files and tests with `git commit -m "feat: establish local work corpus boundary"`.

**Safety gate:** Before any command that reads source content, verify that no enabled bridge service or launch agent points at `data/`. If one is active, stop and disable it as a separate, explicit local operation. Do not remove the legacy source files as part of an automatic ingestion run.

## Task 2: Build the complete manifest and explicit source registry — completed (`add7e97`)

**Files:**

- Modify: `work-corpus/src/work_corpus/inventory.py`
- Modify: `work-corpus/src/work_corpus/util.py`
- Modify: `work-corpus/src/work_corpus/config.py`
- Modify: `work-corpus/src/work_corpus/report.py`
- Create: `work-corpus/tests/test_inventory.py`
- Create: `work-corpus/tests/fixtures/inventory_tree/` with synthetic files only

**Source-root rules:**

1. `data/Zoom/` is the Zoom root. A dated folder immediately below it is the meeting-group boundary.
2. `data/notes/Notes/` is the Capacities Markdown root.
3. `data/notes/Capacities (2026-09-03 14-19-01).zip` is the Capacities archive source. List its members for accounting, but do not ingest duplicate semantic content when the extracted directory is present.
4. `data/notes/40b7a161-92e3-450d-8dab-c2bb4a080adf_ExportBlock-7045c812-ccf8-4b28-b774-5502ee6696b2/` is the Notion root.
5. Its matching `.zip` is the Notion archive source and is not a second semantic corpus when the extracted directory is present.
6. `.one` files below `data/notes/Backup/` are OneNote source files. The nested notebook name does not change the source system.
7. Formal records are the remaining explicitly approved work document roots after the known roots and discovery tree are excluded. Do not invent a path when the inventory does not show one; report residual paths for review.
8. `data/note-inventory-20260903-142816/` is `inventory_discovery`, not `document` or `note` content.

**Stable identity:**

- `source_id = sha256("source-file:v1:" + source_root_key + ":" + relative_path)`.
- `source_version_id = sha256("source-version:v1:" + source_id + ":" + content_sha256)` after a content hash is available. Size and modification time remain audit fields, not semantic identity.
- `evidence_id = sha256("evidence:v1:" + source_version_id + ":" + locator)`, where `locator` is a page, row, section, timestamp, or text-range locator.
- A changed file keeps its `source_id` and receives a new `source_version_id`. Touching a file without changing its bytes does not create a new semantic version. If a hash is not yet available, the record is inventory-only and cannot enter semantic extraction until hashing succeeds. Existing derived rows remain traceable to the old version.

**Interfaces:**

- `inventory(config: Config, con: sqlite3.Connection, *, full_hash: bool = False) -> InventoryResult` records every physical file, including `.DS_Store`, and returns counts and errors.
- `classify_root(relative_path: str, roots: Sequence[SourceRoot]) -> SourceRootMatch` uses explicit root precedence.
- `stable_source_id(root_key: str, relative_path: str) -> str` is deterministic and independent of file modification time.
- `classify_scope(relative_path: str, source_system: str) -> ScopeProposal` returns `Work`, `Personal`, `Mixed`, or `Unknown` as a proposal with a reason. It does not silently promote uncertain content to `Work`.

- [ ] Write fixture tests for explicit Notion-versus-Capacities classification, nested OneNote paths, discovery exclusion from extraction, and complete inclusion of `.DS_Store` as metadata.
- [ ] Write `test_inventory.py::test_source_and_version_identity_rules` and assert that changing only `mtime_ns` leaves both semantic IDs unchanged, while changing `content_sha256` leaves `source_id` unchanged and changes `source_version_id`.
- [ ] Write `test_inventory.py::test_root_precedence_does_not_use_filename_heuristics` and use a synthetic file whose name contains `notion` under the Capacities root; assert that the root wins.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_inventory.py` and confirm the fixture tests fail against the bootstrap's current filename-heuristic classifier.
- [ ] Replace the classifier with explicit root matching. Keep discovery rows in the manifest with `kind=discovery` and `extraction_status=excluded`.
- [ ] Generate a derived manifest report under `corpus/reports/` without overwriting the reviewed `01_INVENTORY/source_manifest.csv`.
- [x] Run the manifest against the real tree only after the boundary gate. The reviewed expectation was 1,413 physical files, 1,394 substantive files after 19 Finder metadata files, 134 Notion ExportBlock rows, 276 Zoom dated folders, and 29 OneNote files; the live acceptance observed 1,414 files, 20 Finder metadata files, 134 Notion files, 275 dated source-bearing Zoom folders, and 29 OneNote files.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_inventory.py` again. Expected result: all pass and the raw tree's before/after file list, sizes, modification times, and hashes are identical.
- [ ] Commit with `git commit -m "feat: add explicit immutable source manifest"`.

## Task 3: Replace the bootstrap schema with the provenance model — completed (`6773540`)

**Files:**

- Modify: `work-corpus/src/work_corpus/db.py`
- Create: `work-corpus/tests/test_db.py`

The initial schema must contain these tables and no email, career-claim, or
structured decision table. Decision text remains in evidence records.

| Table | Required fields and purpose |
|---|---|
| `schema_meta` | Schema version and migration time. |
| `pipeline_run` | Run ID, command, start/end time, status, safe diagnostics. |
| `source_root` | Root key, relative path, source system, precedence, enabled flag. |
| `source_record` | Stable source ID, root key, relative path, source system, kind, scope, sensitivity, status, first/last seen. |
| `source_version` | Version ID, source ID, size, mtime, content hash, observed dates, created time. |
| `date_observation` | Evidence ID or source version, date value, basis, precision, confidence. |
| `normalized_document` | Source version, derived path, parser/version, character/line counts, content hash, status, error. |
| `meeting_group` | Stable dated Zoom folder identity, folder path, linked media, linked transcript, status. |
| `transcription_job` | Meeting group, media version, approval status, local engine/model, status, timestamps, quality fields, error. |
| `evidence_record` | Stable evidence ID, source version, locator, derived text path, text hash, evidence status. |
| `entity` | Stable entity ID, type (`project`, `person`, `organization`), canonical name, status, confidence. |
| `entity_alias` | Entity, alias, source system, valid dates, rule, confidence, review status. |
| `entity_mention` | Evidence, entity, original mention, location, resolution status. |
| `document` | Evidence-backed title and document type. |
| `task` | Explicit action, owner/assigner, project, source event date, due date, candidate status, task status, source evidence. |
| `relationship` | Evidence-backed typed edge between canonical records or a record and an evidence item. |
| `review_item` | Issue type, source/evidence IDs, proposed result, reason, confidence, status, resolution. |
| `ingestion_checkpoint` | Provider/root, cursor or source version, last successful retrieval, count, error. |
| `mcp_item` | `item_id`, `source_id`, `provider`, `external_record_id`, `capture_date`, `event_date`, `retrieval_date`, `original_response_sha256`, `normalized_evidence_id`, `checkpoint_id`, and `updated_at`. This is an integration index, not a second factual corpus. |

Add indexes for source system, scope, source status, event dates, entity aliases, relationship endpoints, review status, task candidate status, and FTS document IDs. Add a SQLite FTS5 table for searchable derived text. Add a repository query function `current_tasks(con, run_date)` that applies the run-date rule; SQLite views do not accept parameters, so do not pretend that `current_tasks(run_date)` is a SQL view. Do not persist a stale boolean as the source of truth.

**Interfaces:**

- `connect(path: Path) -> sqlite3.Connection` enables foreign keys, WAL, and the schema migration.
- `upsert_source_record(...) -> str` returns the stable source ID without deleting prior versions.
- `record_source_version(...) -> str` returns the deterministic version ID.
- `record_evidence(...) -> str` returns the deterministic evidence ID for a locator.
- `record_review_item(...) -> str` creates an idempotent review item keyed by issue type, source/evidence ID, and proposal hash.

- [ ] Write tests for foreign keys, deterministic IDs, source-version retention, idempotent reruns, and the current-task query boundary.
- [ ] Write `test_db.py::test_schema_has_no_email_career_claim_or_decision_table` and assert those table names are absent.
- [ ] Write `test_db.py::test_current_tasks_use_run_date_and_event_date` with dates on both sides of the run-date minus 14-day boundary, a future date, an export-only date, and a missing event date.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_db.py` against a temporary SQLite file. Expected initial failures: missing tables, stale bootstrap schema, and incorrect task-date behavior.
- [ ] Replace `db.py` schema initialization and add forward-only migrations. Do not drop a user's existing state database automatically; use a new schema version or a documented migration failure.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_db.py` again. Expected result: all pass, and reopening the same database does not duplicate rows.
- [ ] Commit with `git commit -m "feat: define provenance-first corpus schema"`.

## Task 4: Implement safe extraction adapters — completed (`b267b9e`)

**Files:**

- Modify: `work-corpus/src/work_corpus/normalize.py`
- Modify: `work-corpus/src/work_corpus/util.py`
- Create: `work-corpus/src/work_corpus/onenote.py`
- Create: `work-corpus/tests/test_extraction.py`
- Create: `work-corpus/tests/fixtures/` with synthetic Markdown, HTML, CSV, VTT, PDF/Office metadata, and parser-error files only

**Adapter order:**

1. Inventory and source-version creation.
2. Zoom meeting grouping and existing transcript matching.
3. Direct local text: Capacities Markdown/CSV, Notion HTML/CSV/TXT, and transcript candidates.
4. OneNote `.one` conversion through the tested local parser route.
5. Formal PDF, DOCX, PPTX, XLSX, and CSV extraction with page, slide, sheet, row, and table locators.
6. Build the complete local transcription queue and resumable runner for every final media source version without a usable transcript.
7. Deterministic entity aliases and explicit task proposals.
8. FTS and relationship index rebuild.
9. Local Wispr Flow and Granola snapshot intake.

**Extraction rules:**

- Every derived record stores source ID, source version ID, relative path, parser name/version, source date basis, and a locator.
- Directory exports are semantic sources. Matching ZIP files are verified archives and retain archive-member accounting without duplicating directory content.
- Capacities pointer-only File/Image/PDF records are preserved as records with `payload_status=missing`. Never fetch their signed URLs.
- Notion HTML, database CSVs, local attachments, and 12 local transcript TXT files remain separate evidence units until links and dates are normalized.
- OneNote output is derived Markdown or HTML with page and section locators. The 29 real files are an acceptance run, not committed test fixtures.
- Zoom `client_config` files with XML/plist-shaped content are non-failing metadata. They are not transcript evidence.
- Parser errors create `review_item` rows and do not replace a prior successful normalized output with an empty file.
- Derived text used for FTS is scrubbed of signed URLs and secret-like values. The original text remains only in the immutable source.
- Every final Zoom MP4 or M4A has either an existing usable transcript or a transcription job with a terminal result. Raw `.zoom`, `.tmp`, corrupt, and otherwise non-final files receive an explicit artifact or blocked status and a review record when needed.

**OneNote dependency boundary:** The core package does not download or
silently install a converter. `onenote.py` accepts a configured local
`ONENOTE_CONVERTER_ROOT` or converter command and `doctor.py` verifies that the
tested exporter and its `pyOneNote` dependency are available. If they are not
available, the adapter reports `blocked` and does not read `.one` files. The
one-time operator setup may install the dependency in a dedicated local
environment or point to a reviewed local source checkout; the exact converter
path and version are recorded in `state/tool_versions.json`. The corpus run
itself makes no network request. The already promoted
`requirements-optional.txt` covers local Office parsers; it does not invent an
unverified OneNote package name.

**Idempotency:** Each extraction result is keyed by source version, adapter name, adapter version, and locator. Repeating a run updates the same derived row and output path. A failed retry leaves the last good output and records the new failure separately.

- [ ] Write fixture tests for each parser, provenance headers, pointer-only attachment handling, signed-URL removal, and prior-good-output preservation on parser failure.
- [ ] Write `test_extraction.py::test_matching_archive_does_not_duplicate_directory_content` and assert that a directory item and its archive member map to one semantic evidence unit with two source references.
- [ ] Write `test_extraction.py::test_discovery_report_is_not_searchable_evidence` and assert that discovery text produces a manifest row but no normalized document or FTS row.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_extraction.py` and confirm that the bootstrap's generic source classifier fails the Notion/Capacities distinction before the replacement is active.
- [ ] Port only the reusable local parsing functions from `work-corpus/src/work_corpus/normalize.py` and `util.py`; remove email/archive-message branches from the runtime path.
- [ ] Integrate the selected OneNote converter behind a local adapter command or pinned local module. Record converter version and the terminator-node workaround in the adapter metadata.
- [x] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_extraction.py`, then run the documented read-only OneNote acceptance command over all 29 `.one` files. The extraction tests pass. The runtime converter is unavailable, so the acceptance result is 29 blocked files and 0 pages, with no raw file changes.
- [x] Commit with `git commit -m "feat: add provenance-preserving source adapters"` (`b267b9e`).

## Task 5: Correct Zoom grouping and implement complete local transcription coverage — completed (`dda1e78`)

**Files:**

- Modify: `work-corpus/src/work_corpus/zoom.py`
- Modify: `work-corpus/src/work_corpus/transcription.py`
- Modify: `work-corpus/src/work_corpus/config.py`
- Create: `work-corpus/tests/test_zoom.py`
- Create: `work-corpus/tests/test_transcription.py`

**Meeting identity:** A Zoom meeting group is the dated folder immediately below `data/Zoom/`. Nested `Audio Record` folders belong to that parent group. A group ID is the stable hash of the Zoom root key and dated-folder relative path. It must never be based only on the title.

**Transcript selection:** Prefer a usable VTT, then a usable SRT, then an explicit transcript TXT. Exclude chat, participant, and saved-chat files. Match candidates inside the same group first. A transcript-only group remains separate unless a review item establishes a match.

**Queue states:** `not_needed`, `existing_transcript`, `pending_approval`, `queued`, `running`, `succeeded`, `partial`, `failed`, `blocked`, `artifact`, and `skipped`.

`pending_approval` is the default for eligible final media until the operator
approves the full local coverage run. The queue includes every final MP4 and
M4A that has no usable transcript. It does not use a selected subset.

`artifact` identifies a raw `.tmp`, unvalidated `.zoom`, corrupt, or otherwise
non-final file. The system keeps the manifest record and the reason. An
artifact is not a transcription failure.

The transcription runner uses one media item at a time by default. After each
item, it stores the job status, output path, output hash, quality result, and
error text. A restart resumes from the last checkpoint. A failed item does not
erase a prior good transcript or lose the remaining queue.

**Local-only engine contract:** The engine adapter accepts a local media path and writes a derived VTT/TXT result under `corpus/transcripts/`. Use the locally installed Whisper large model when the local configuration provides it. Do not hard-code a model path. Record the executable, model name/version, language, run date, source media version, timestamp coverage, and quality status. The allowlist rejects HTTP URLs, cloud provider names, API keys, and remote upload options. Wispr Flow is a future input source, not an implicit cloud transcription engine.

**Quality checks:** A result must be non-empty, parseable, timestamp-ordered, linked to the intended media group, and sufficiently covered to be useful. Speaker labels are recorded as present, absent, or unresolved. Partial or poor-quality results remain visible but do not become confirmed facts.

- [ ] Write `test_zoom.py::test_nested_audio_record_belongs_to_parent_group` and assert that a nested recording creates no second meeting group.
- [ ] Write `test_zoom.py::test_existing_transcript_wins_over_media_queue` and assert that a usable VTT changes the group to `existing_transcript` and creates no transcription job.
- [ ] Write `test_zoom.py::test_transcript_only_group_is_not_title_matched` and assert that a same-title transcript in another folder creates a review item instead of an automatic link.
- [ ] Write transcription tests for run approval, one-at-a-time execution, checkpoint resume, local-engine rejection of remote commands, idempotent job keys, retry after failure, partial quality, artifact classification, and preservation of a prior successful transcript.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_zoom.py work-corpus/tests/test_transcription.py` against synthetic meeting folders. Expected initial failures: bootstrap immediate-parent grouping, missing approval state, and remote-engine branches.
- [ ] Correct `zoom.py` and `transcription.py` without reading or changing real media during unit tests.
- [x] Run a read-only Zoom scan on the real tree. The scan observed 275 dated source-bearing folders (the reviewed plan expected 276), with existing transcripts and transcript-only groups represented at the dated-folder boundary. Bootstrap pending rows were not treated as meetings.
- [x] Produce a complete queue report listing every eligible final media source version and every artifact or blocked item.
- [x] Run a synthetic coverage test that proves one-at-a-time execution, checkpoint resume, retry, and terminal status recording.
- [x] Run the Task 9 full local coverage pass after extraction and report preflight. Every eligible media item is terminally accounted for; all 231 are `blocked` because no local engine is available.
- [x] Commit with `git commit -m "feat: make Zoom grouping and local transcription explicit"` (`dda1e78`).

## Task 6: Add deterministic names, scope review, and task extraction — completed (`e534838`)

**Files:**

- Create: `work-corpus/src/work_corpus/entities.py`
- Create: `work-corpus/src/work_corpus/tasks.py`
- Create: `work-corpus/entity_aliases.example.json`
- Modify: `work-corpus/src/work_corpus/db.py`
- Modify: `work-corpus/src/work_corpus/normalize.py`
- Create: `work-corpus/tests/test_entities.py`
- Create: `work-corpus/tests/test_tasks.py`

**Entity rules:**

- A canonical entity has a stable ID independent of its display name.
- `entity_alias` records alternate spellings, abbreviations, former names, and source-specific names with evidence and effective dates.
- Matching order is exact alias, regex normalization, source-specific identifier, frequency comparison among valid names, then review.
- The most common spelling is selected only from names marked valid by the source dictionary or user review. Frequency alone cannot make a typo canonical.
- A collision is not a merge. Role, organization, time, project, and participant context must support a merge proposal.
- Every automatic normalization preserves the original mention and the rule that produced the canonical link.

**Local model boundary:** A later local refinement pass may propose entity clusters or task spans from derived work text. It writes proposals to `review_item`. It never directly merges entities, changes scope, or creates a current task without deterministic eligibility and review status. This pass does not block source assembly. Tasks 0–9 do not require this pass.

**Scope rules:** Root/path classification may propose `Work`, `Personal`, `Mixed`, or `Unknown`. A clear work source can be accepted automatically. Personal, mixed, personnel-sensitive, legal, or ambiguous records retain sensitivity labels. `Work` records may be queried by this single user; `Mixed` and `Unknown` never enter the default query until a review resolves them.

**Task rules:** Extract only explicit assignments, promises, deliverables, or follow-ups. Store the source event/meeting date and its basis. The current-task view evaluates the run date, not the source date: `event_date >= run_date - 14 calendar days` or `event_date > run_date`. A missing event date, export-only date, or old note produces historical evidence or a review item, not a current task. No historical backlog is created automatically.

- [ ] Write entity tests for exact aliases, regex spelling normalization, valid-frequency selection, collision separation, former-name links, and ambiguous merge review.
- [ ] Write task tests for explicit versus implied language, future events, the exact 14-day boundary, old notes, export-only dates, and missing dates.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_entities.py work-corpus/tests/test_tasks.py` before implementation and verify that no stale `career_claim` table or generic classifier is used.
- [ ] Implement `entities.py` and `tasks.py` with deterministic proposal keys and review records.
- [ ] Seed the local-only name dictionary template at `work-corpus/entity_aliases.example.json`. Keep actual names in ignored `config.local.json` or the SQLite review state, not in a public commit.
- [ ] Run the entity and task tests against synthetic fixtures only. The real preflight batch is executed in Task 9. Keep the coaching/family caption, personnel files, TAB workbook, legal notes, personal trust notes, OneNote binaries, pointer-only records, raw `.zoom`, and `.tmp` files out of the first semantic batch.
- [ ] Commit with `git commit -m "feat: add canonical entities and current task rules"`.

## Task 7: Implement local query, evidence labels, and rebuildable search indexes — completed (`402f49c`)

**Files:**

- Create: `work-corpus/src/work_corpus/query.py`
- Modify: `work-corpus/src/work_corpus/cli.py`
- Create: `work-corpus/tests/test_query.py`

**Query order:**

1. Validate the question and apply the default `Work` scope.
2. Search canonical evidence and FTS.
3. Traverse SQLite relationships for projects, people, organizations, meetings, evidence, and tasks.
4. Use work-classified derived or raw fallback only when canonical evidence has no answer.
5. Redact URL-like and secret-like values from fallback snippets.
6. Return source path, source ID, source version, locator, evidence status, and date basis.
7. Separate source facts, local-model inferences, conflicts, and missing evidence.

The query builder must make it impossible for the default path to join `Personal`, `Mixed`, or `Unknown` source records. A separate diagnostic command may inspect excluded records locally, but it is not part of the default answer path and must label its output.

**Evidence labels:** `canonical`, `derived_reviewed`, `derived_unreviewed`, `raw_work`, `inference`, `conflict`, `missing`, and `excluded_scope`.

**Redaction:** Redact `http://` and `https://` strings, signed query parameters, bearer/API-key patterns, and token-like values before a snippet is displayed or inserted into the FTS index. Redaction is output-only; it never rewrites the raw source.

- [ ] Write query tests that insert one Work, Personal, Mixed, and Unknown evidence row and assert that the default result contains only Work.
- [ ] Write `test_query.py::test_raw_fallback_requires_work_scope` and assert that raw fallback never returns non-Work evidence even when the text matches exactly.
- [ ] Add redaction tests to the promoted `work-corpus/tests/test_util.py` for signed URLs, bearer values, API-key-shaped strings, ordinary local paths, and timestamp text.
- [ ] Write evidence-label tests for canonical, unreviewed, inference, conflict, and missing results.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_query.py work-corpus/tests/test_util.py` before implementation. Expected failures: the bootstrap fallback has a Work predicate but no complete query layer, FTS scope join, or secret redaction contract.
- [ ] Implement exact search, relationship traversal, and fallback. Keep the first useful query path dependent on FTS and SQLite relationships only.
- [ ] Run the query checks against synthetic fixtures and confirm source locations point to the original relative paths without URL leakage. Defer the real preflight batch to Task 9.
- [ ] Commit with `git commit -m "feat: add scoped source-backed query layer"`.

## Task 8: Add future Wispr Flow and Granola intake without live connections — completed (`3ddabd6`)

**Files:**

- Modify: `work-corpus/src/work_corpus/mcp_ingest.py`
- Modify: `work-corpus/src/work_corpus/db.py`
- Modify: `work-corpus/src/work_corpus/config.py`
- Modify: `work-corpus/src/work_corpus/cli.py`
- Create: `work-corpus/tests/test_mcp_ingest.py`

The initial implementation accepts local JSON, JSONL, Markdown, or TXT snapshots under configured future roots such as `data/mcp/wispr_flow/` and `data/mcp/granola/`. It does not connect to a live MCP server during this phase.

Each `mcp_item` stores exactly these fields: `item_id`, `source_id`,
`provider`, `external_record_id`, `capture_date`, `event_date`,
`retrieval_date`, `original_response_sha256`, `normalized_evidence_id`,
`checkpoint_id`, and `updated_at`. The stable item key is provider plus
external ID when present; otherwise it is the source version plus record index
and content hash. Repeated snapshots update the same item. Overlapping
checkpoints do not duplicate evidence.

- [ ] Write tests for provider classification, external-ID idempotency, content-hash fallback, cursor persistence, malformed-item review, and event-date preservation.
- [ ] Verify that `mcp_ingest.py` has no email import or email behavior. Remove email-only paths from the promoted CLI and configuration before importing the MCP adapter.
- [ ] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_mcp_ingest.py` with local snapshot fixtures and no network-enabled code path. Expected result: repeat import creates no duplicate item or evidence row.
- [ ] Add feed freshness to `report.py`. Unknown retrieval time must be reported as unknown, not as current.
- [ ] Commit with `git commit -m "feat: add local Wispr and Granola snapshot intake"`.

## Task 9: Reports, acceptance run, and documentation handoff — completed mechanically (`ff7699a`)

**Files:**

- Modify: `work-corpus/src/work_corpus/report.py`
- Modify: `work-corpus/src/work_corpus/cli.py`
- Create: `work-corpus/tests/test_reports.py`
- Create after plan review: `docs/adr/0001-local-work-corpus-boundary.md`
- Create after plan review: `CONTEXT.md`
- Modify after plan review: `README.md`, `progress.md`, and `TODO.md`

**Reports must show:**

- physical-file count and substantive-file count;
- source counts by explicit root and source system;
- discovery rows excluded from extraction;
- normalized, unsupported, failed, and prior-good-retained records;
- Zoom group counts, existing transcripts, transcription results by terminal status, and unmatched transcript-only groups;
- eligible Zoom media with no terminal status, local transcription attempts, retries, output hashes, and failure reasons;
- OneNote parsed files/pages and converter status;
- Capacities pointer-only payload count without exposing signed URLs;
- Notion page/database/attachment counts and unresolved relationships;
- scope and sensitivity review queues;
- entity aliases and ambiguous merge proposals;
- historical versus current task candidates;
- FTS and relationship index freshness;
- Wispr/Granola checkpoint freshness;
- a raw immutability result.

**Acceptance sequence:**

1. Capture a manifest of every file's relative path, size, mtime, and hash.
2. Run `work-corpus` inventory and compare its counts to `01_INVENTORY/`.
3. Run only the safe preflight batch: three clearly work-labeled Zoom VTTs and five clearly work-labeled Capacities Markdown notes.
4. Verify source IDs, source versions, evidence locators, scope, and task candidates.
5. Verify no current task is created from an old note, export-only date, or missing event date.
6. Run the 29-file OneNote read-only acceptance pass and record its actual
   converter result. The reviewed expectation is 295 pages; the current run
   fails closed with 29 blocked files and 0 pages because no converter is
   installed.
7. Run Zoom grouping and existing-transcript matching.
8. Run the full local extraction for every readable source. Exclude only discovery evidence and source payloads that the inventory marks as missing.
9. Build the complete Zoom transcription queue. Include every final MP4 or M4A without a usable transcript.
10. Approve one full local transcription run. Process one media item at a time with a resumable checkpoint after each item.
11. Continue until every eligible media item has an existing transcript or a terminal local status. Keep failed, partial, blocked, and artifact items in the report.
12. Rebuild FTS and relationship indexes from SQLite evidence records.
13. Run a query suite for work history, project changes, decision evidence, people, current tasks, conflicts, and evidence locations.
14. Re-run every command and confirm idempotency and raw immutability.

The full local coverage pass is complete when the report shows zero eligible
Zoom media items without a terminal status. A failed or blocked item counts as
accounted for. It does not count as successfully transcribed.

**Documentation handoff after Gemini review:**

- `CONTEXT.md` records the domain terms: raw evidence, source record, source version, evidence record, meeting group, canonical entity, alias, review item, current task, and derived view.
- `docs/adr/0001-local-work-corpus-boundary.md` records the local-only, single-user, no-email, no-Atlas decision and the immutable raw boundary.
- `README.md` becomes the operational entry point for the new `work-corpus/` package and points to the inventory, design, access matrix, and plan.
- `progress.md` is marked as historical bridge context and replaced with current corpus milestones.
- `TODO.md` receives the final reviewed implementation checklist. It must not claim tasks are complete before their verification gates pass.

- [x] Write report tests using only synthetic database rows. Assert that all report categories are present and sensitive values are not printed.
- [x] Run `PYTHONPATH=work-corpus/src pytest -q work-corpus/tests/test_reports.py` and the complete package suite; the final no-coverage suite is 146 passed.
- [x] Run `git diff --check` and a placeholder scan over the plan and docs.
- [x] Compare raw-file snapshots before and after the acceptance run. Paths, sizes, modification times, and hashes are identical: 1,414 files, 58,965,738,600 bytes, zero mismatches.
- [x] Record every unresolved item in `review_item` or the report. Parser, scope, task-date, sensitivity, unsupported-parser, blocked-engine, missing-converter, and missing-MCP states remain visible.
- [x] Confirm that the full local coverage pass has zero eligible Zoom media items without a terminal status.
- [x] Verify that the ADR, `CONTEXT.md`, README, progress log, and `TODO.md` match the executed behavior. Update only changed wording.
- [x] Commit the documentation handoff separately with `git commit -m "docs: document local work corpus implementation"`.

## Genuine blockers and resolved assumptions

### Resolved from the current inventory

- Notion is present and is separate from Capacities. The 134 ExportBlock rows are labeled Notion in the reviewed manifest.
- The reviewed OneNote parser fixture recorded 295 pages for 29 `.one` files.
  The current runtime has no converter, so the acceptance pass fails closed
  with 29 blocked files and 0 pages.
- The Zoom meeting boundary is the dated folder directly below `data/Zoom/`; nested `Audio Record` folders are not meetings.
- Existing transcripts are the first transcription source. The complete missing-transcript media queue is a required local operation.
- The raw data has no email corpus, and email remains out of scope.
- The repository's old Atlas bridge is not a usable corpus foundation and must not receive the data root.

### Operational gates, not design blockers

- A local transcription executable and model path must be available before the media coverage run. The design supports a configured local command and does not assume a particular engine. If the engine is unavailable, the run records `blocked` items and remains incomplete. It never switches to a cloud engine.
- The OneNote converter must be available on the machine at implementation time. The selected route and version must be recorded in adapter metadata.
- Work/personal/mixed classification and ambiguous entity merges require user review. This is expected review work, not a reason to send data to a service.
- No current Wispr Flow or Granola export is present in this snapshot. The local snapshot adapter can be tested with synthetic fixtures and activated when a user-authorized export exists.

## Final TODO

- [x] Re-review this amended plan against `docs/superpowers/specs/2026-09-04-local-work-corpus-design.md` and the Antigravity review.
- [x] Have Gemini 3.1 Pro adversarially review the amended plan without access to `data/` or raw exports.
- [x] Apply only valid simplification, boundary, provenance, and repository-fit findings from that review.
- [x] Verify the updated ADR, `CONTEXT.md`, progress log, and `TODO.md` after the review.
- [x] Implement Tasks 1–9 in order with a test gate and commit after each task.
- [x] Keep full source extraction and full local transcription coverage behind the run-level review gate. Defer embeddings and future Wispr/Granola intake.
