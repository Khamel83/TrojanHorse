# Canonical Work-Corpus Completion Implementation Plan

> **Execution note:** Implement this plan task by task in the existing
> checkout. Keep `data/`, `01_INVENTORY/`, `Omar_Work_Corpus_Bootstrap_v1/`, the
> ZIP, and the untracked Gemini review file out of Git. Run the focused test
> after each task and the complete active suite before live corpus commands.

**Goal:** Make the local `work-corpus` package the supported product, index the
20 already-local email files, expose source-backed project/task/career ledgers,
and provide a safe, resumable Granola `updated_after` maintenance path.

**Design:** `docs/superpowers/specs/2026-09-07-canonical-work-corpus-completion.md`

**Test command:**

```bash
PYTHONPATH=work-corpus/src python3 -m pytest -q work-corpus/tests
```

## Task 1: Canonical package, doctor, stale runs, and raw verification

**Files:**

- Modify: `pyproject.toml`
- Modify: `work-corpus/pyproject.toml`
- Modify: `run_tests.sh`
- Modify: `work-corpus/src/work_corpus/cli.py`
- Modify: `work-corpus/src/work_corpus/doctor.py`
- Modify: `work-corpus/src/work_corpus/db.py`
- Add: `work-corpus/src/work_corpus/raw_verify.py`
- Add: `pytest.ini`
- Add: `.github/workflows/ci.yml`
- Add: `docs/OPERATIONS.md`
- Add: `docs/LEGACY_ATLAS.md`
- Test: `work-corpus/tests/test_boundary.py`
- Test: `work-corpus/tests/test_doctor.py`
- Test: `work-corpus/tests/test_raw_verify.py`

**Interfaces:**

- Root editable installation discovers packages from `work-corpus/src` and
  exposes `work-corpus`.
- `doctor(config, con)` returns a structured local report and writes only
  `state/doctor.json` and `state/doctor.txt`.
- `recover_stale_runs(con, stale_after_hours=24)` marks only old `running`
  rows as `abandoned` with a scrubbed reason.
- `verify_raw_immutability(config, con)` performs two full raw scans, compares
  path/size/hash maps, and writes `state/raw_immutability.json`.

**Steps:**

1. Add failing tests for root parser/testpath behavior, doctor database checks,
   stale-run recovery, and a synthetic two-pass raw comparison that detects a
   changed byte.
2. Run the focused tests and confirm they fail for the missing command/API.
3. Change root packaging and `pytest.ini` to target `work_corpus`, rewrite the
   stale test runner as a thin wrapper, add the fatal Ruff CI gate, and label
   `TrojanHorse/`, `bridge/`, and `systemd/` as quarantined historical code.
4. Implement doctor output, stale-run recovery, and the two-pass verifier. Use
   the existing inventory/hash functions; do not edit raw files.
5. Run focused tests, then the full active suite. Run `git diff --check`.

## Task 2: Local `.eml` extraction and date provenance

**Files:**

- Modify: `work-corpus/src/work_corpus/normalize.py`
- Modify: `work-corpus/src/work_corpus/db.py`
- Modify: `work-corpus/src/work_corpus/cli.py`
- Test: `work-corpus/tests/test_extraction.py`
- Test: `work-corpus/tests/test_db.py`

**Interfaces:**

- `_eml_parts(path, max_bytes)` parses RFC 822 bytes with the standard library
  and returns `headers`, `body`, and `attachments` parts.
- The extractor metadata includes `event_date`, `source_date_basis`, and
  `attachment_count`; attachment payload bytes never enter derived text.
- `normalize_all` accepts `kind=email` when the source is present, hashed, and
  parse-ready. Existing discovery, media, MCP, and unknown exclusions remain.
- A stable `date_observation` row uses basis `email_header_date`.

**Steps:**

1. Add a synthetic multipart `.eml` fixture in the test's temporary directory.
   Assert parser name, locators, body text, attachment metadata, no attachment
   bytes, URL/secret scrubbing, and the parsed email date.
2. Run the focused extraction tests and confirm the parser is unsupported.
3. Implement the parser, remove only `email` from the normalization exclusion,
   record the date observation, and pass the extracted event date into task
   proposal evaluation. Keep the raw source bytes untouched.
4. Run extraction/database tests, then the full active suite.
5. Run the ordered live commands:

   ```bash
   work-corpus --root . inventory --full-hash
   work-corpus --root . normalize
   ```

   Confirm all 20 local `.eml` source versions have normalized documents,
   evidence rows, and FTS rows. Do not stage `data/` or generated state.

## Task 3: Deterministic project, task, and career evidence views

**Files:**

- Add: `work-corpus/src/work_corpus/views.py`
- Modify: `work-corpus/src/work_corpus/cli.py`
- Modify: `work-corpus/src/work_corpus/organization.py`
- Test: `work-corpus/tests/test_views.py`
- Modify: `README.md`

**Interfaces:**

- `build_views(config, con)` writes the three ledgers and
  `state/views_acceptance.json` under derived paths.
- Project rows come from confirmed project-to-evidence relationships.
- Task rows combine `task` records with nonblank `task_date_review` and
  `task_scope_review` proposals, preserving `current`, `historical`, and
  `scope_review` statuses and their resolution text.
- Career rows join evidence to source records with `career_value` `medium` or
  `high`, attach any project names, and set `claim_status=evidence_only` and
  `external_use=review_required`.
- All rows include source ID, source version ID, evidence ID, source path, and
  locator. Blank source paths or evidence IDs are not emitted.

**Steps:**

1. Add synthetic database tests for project relationships, current and
   historical task proposals, and career-valued evidence. Assert stable CSV
   headers, deterministic ordering, idempotent bytes, and no raw secret/URL
   leakage.
2. Run the focused view tests and confirm the module/command is missing.
3. Implement the smallest SQL-backed view builder with CSV, JSON, Markdown,
   and acceptance-state outputs. Do not add a new canonical table or use an
   external model.
4. Add the `views` CLI command and invoke it in the maintenance pipeline after
   `organize`.
5. Run focused and full tests. Run `work-corpus --root . views` and verify the
   live output counts, including the existing zero current task-row fact.

## Task 4: Granola REST delta runner and scheduler template

**Files:**

- Modify: `work-corpus/src/work_corpus/granola_api.py`
- Add: `work-corpus/src/work_corpus/granola_delta.py`
- Add: `work-corpus/scripts/run_granola_delta.py`
- Add: `work-corpus/scripts/run_granola_delta.sh`
- Add: `work-corpus/ops/systemd/work-corpus-granola-delta.service`
- Add: `work-corpus/ops/systemd/work-corpus-granola-delta.timer`
- Modify: `work-corpus/src/work_corpus/granola_progress.py`
- Modify: `work-corpus/src/work_corpus/cli.py`
- Test: `work-corpus/tests/test_granola_api_backfill.py`
- Add: `work-corpus/tests/test_granola_delta.py`

**Interfaces:**

- `GranolaApiClient.list_notes(updated_after=None)` includes the documented
  filter while preserving cursor pagination and the 30-note page cap.
- `run_backfill(..., updated_after=None)` produces archive or delta captures;
  `_capture.mode` is `archive` or `delta` and records the filter.
- `run_delta(config, client, ...)` obtains a watermark from the latest local
  REST archive or prior checkpoint, subtracts the overlap, captures changed
  notes, writes a mode-0600 raw JSON file atomically, then runs local stages in
  order and advances the derived checkpoint only after success.
- The runner takes a Unix advisory lock under `state/mcp/` and never accepts an
  API key as a command-line argument. The shell wrapper obtains
  `GRANOLA_API_KEY` from `secrets`.

**Steps:**

1. Add failing tests for the `updated_after` query parameter, delta envelope,
   watermark overlap, empty delta, failure without checkpoint advancement,
   lock behavior, and stable ID re-import.
2. Run focused Granola tests and confirm the new assertions fail.
3. Implement the client parameter and delta envelope. Keep list pages at 30,
   pace below the documented sustained limit, honor `Retry-After`, and reuse
   the existing note/transcript retrieval path.
4. Implement the local runner and exact stage order. On failure, retain the
   raw capture but leave the previous watermark intact.
5. Update REST progress discovery to include delta captures, add CLI help, and
   add the five-minute systemd template with a one-writer service.
6. Run focused and full tests. Do not invoke the live provider during this
   code gate.

## Task 5: Live acceptance and documentation closeout

**Files:**

- Modify: `docs/TROJAN_HORSE_AUDIT.md`
- Modify: `docs/REMAINING_WORK.md`
- Modify: `docs/LOCAL_WORK_CORPUS_STATUS.md`
- Modify: `docs/superpowers/specs/2026-09-07-canonical-work-corpus-completion.md`
- Modify: `TODO.md`
- Modify: `CONTEXT.md`
- Modify: `progress.md`
- Modify: `README.md`

**Steps:**

1. Run the active test suite, fatal Ruff/compile checks, root install smoke
   test, doctor, and two-pass raw verification.
2. Run the local ordered pipeline after `.eml` support:
   `inventory --full-hash`, `normalize`, `organize --first-pass`, `views`,
   `report`, and the representative `All`/`Work` queries.
3. Verify SQLite `quick_check`, foreign-key integrity, source-preservation
   counts, 20 searchable `.eml` records, view row counts, and no pending stale
   run created by the acceptance process.
4. Update all status documents with observed values and distinguish implemented
   code from the remaining operator step of enabling the scheduler on a known
   host.
5. Run `git diff --check`, inspect `git diff --stat`, stage only tracked scoped
   code/docs/tests/config files, commit, and push under the existing
   authorization. Verify local/remote commit identity and leave raw/untracked
   corpus files untouched.
