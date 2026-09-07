# Granola Adaptive Batching Implementation Plan

Status: the MCP adaptive implementation is complete and retained for optional
shadow refreshes. For the one-time historical archive, the user-authorized
Granola REST API backfill superseded this heartbeat: 559 unique API notes were
fetched, imported, and indexed on 2026-09-07. See
`docs/LOCAL_WORK_CORPUS_STATUS.md` and `work-corpus/state/mcp/granola_detail_progress.json`
for the separate REST and MCP coverage layers.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Increase local Granola capture throughput from five to the connector's ten-meeting detail limit while preserving serialized transcript retrieval, exact retries, and safe rate-limit recovery.

**Architecture:** The derived checkpoint exposes up to ten exact pending IDs. The heartbeat makes one `granola_get_meetings` request for those IDs and one transcript request per ID, preserving each response in an append-only capture. An explicit rate-limit outcome reduces the next batch to five; a clean pass returns to ten. Inventory, import, progress, and report remain an ordered single-writer pipeline.

**Tech Stack:** Python 3, SQLite/WAL, existing `work_corpus.granola_progress` and `query.rebuild_search_index` APIs, Codex heartbeat automation, pytest.

## Global Constraints

- Raw provider captures remain immutable and outside Git; only new append-only captures may be added.
- The workflow does not write to Granola, call Atlas, send email, fetch signed URLs, or use cloud transcription.
- Exact listed IDs are the completion authority; unlisted provider responses remain excluded from completion.
- `granola_get_meetings` accepts at most 10 IDs; `granola_get_meeting_transcript` remains one-ID-per-call.
- A retryable or rate-limited response preserves successful records and never advances past the unresolved exact ID.
- Milestone 2 entity, relationship, and task work remains blocked until the
  REST archive acceptance gate is complete; the optional MCP shadow checkpoint
  is not that gate.

---

### Task 1: Make the progress checkpoint connector-aware

**Files:**
- Modify: `work-corpus/src/work_corpus/granola_progress.py`
- Test: `work-corpus/tests/test_granola_progress.py`

**Interfaces:**
- Consumes: latest Granola inventory, `granola-content-*.json` captures, and SQLite imported/searchable IDs.
- Produces: `next_batch_size`, `next_batch_ids`, and rate-limit metadata in `granola_detail_progress.json`.

- [ ] **Step 1: Write the failing tests**

Add a test with twelve listed IDs and no content capture. Assert exactly ten next IDs and `next_batch_size == 10`. Add a capture whose request status is `rate_limited`; assert five next IDs and the exact rate-limited ID.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run `PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m pytest -q work-corpus/tests/test_granola_progress.py`. Expected: the new assertions fail because the current implementation always caps at five and has no rate-limit adaptation.

- [ ] **Step 3: Implement the smallest progress-policy change**

Add `MAX_BATCH_SIZE = 10` and `RATE_LIMIT_BATCH_SIZE = 5`. Extend request-status parsing for explicit values such as `429`, `rate_limited`, `rate_limit`, and `too_many_requests`. Derive the next size from the newest capture, persist `rate_limited_ids` and `next_batch_size`, and slice `priority_ids` with that size. Keep ordinary pending failures in the existing exact-ID retry sets.

- [ ] **Step 4: Run focused tests to verify they pass**

Run the same pytest command. Expected: all Granola progress tests pass.

- [ ] **Step 5: Run the full corpus test suite**

Run `PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m pytest -q work-corpus/tests`. Expected: all tests pass, apart from the repository's existing unrelated coverage-target warning.

### Task 2: Document and deploy the faster heartbeat contract

**Files:**
- Modify: `README.md`
- Modify: `CONTEXT.md`
- Modify: `docs/LOCAL_WORK_CORPUS_STATUS.md`
- Modify: `docs/superpowers/specs/2026-09-04-local-work-corpus-design.md`
- Modify: `TODO.md`
- Modify: `docs/superpowers/reviews/2026-09-06-corpus-completion-opus-review.md`

**Interfaces:**
- Consumes: the ten-ID progress checkpoint and automation `continue-granola-corpus-capture`.
- Produces: an operational record that details may use ten IDs, transcripts remain serialized, and five is the recovery size after rate limiting.

- [ ] **Step 1: Update design and glossary**

Replace stale five-record wording with “up to ten detail IDs per pass; one transcript request per ID; five-ID recovery after rate limiting.” Define the checkpoint as derived state, not a manual cursor.

- [ ] **Step 2: Update operational documents**

Record current counts as timestamped checkpoint evidence. State that only the local TrojanHorse corpus remains in scope; other providers are not written or archived destructively.

- [ ] **Step 3: Update the heartbeat prompt**

Pause the automation, preserve its ID/settings, then resume it with: use exact `next_batch_ids`; make one detail call with up to ten IDs; request transcripts one at a time; preserve every response before import; on rate limiting, stop further provider calls, record `status=rate_limited` for exact failed IDs, use five IDs next pass, and return to ten after a clean pass; run inventory, mcp-import, granola-progress, and report in order.

- [ ] **Step 4: Validate the resumed automation**

Run one bounded wait observation after resuming. Confirm the next capture has no more than ten requested detail IDs and transcript requests remain individual.

### Task 3: Refresh acceptance evidence and handoff state

**Files:**
- Update generated state: `work-corpus/state/mcp/granola_detail_progress.json`, `work-corpus/state/granola_acceptance.json`, `work-corpus/state/adapter_acceptance.json`, `work-corpus/state/query_suite.json`
- Update generated reports: `work-corpus/corpus/reports/status.json`, `work-corpus/corpus/reports/status.html`, `work-corpus/corpus/reports/what_we_have_and_need.md`

**Interfaces:**
- Consumes: current raw captures, SQLite source/evidence/FTS rows, public query API, and local adapter state.
- Produces: separate proof for raw capture, registration, import, search, repeat-import idempotency, adapter residuals, and representative queries.

- [ ] **Step 1: Run the ordered local pipeline while paused**

Run `inventory`, `mcp-import` twice, `granola-progress`, and `report` with the installed interpreter. Confirm both import runs have equal item/update/error results.

- [ ] **Step 2: Run representative public queries**

Exercise work-history, project, decision, people, current-task, conflict, and evidence-location questions through `work_corpus.query.search(..., raw_fallback=False)`. Record counts and scope labels without copying private raw text into tracked files.

- [ ] **Step 3: Verify residual boundaries**

Confirm all capture paths are registered, captured listed IDs are imported/searchable, unlisted IDs remain excluded, rate-limit/retry IDs are visible, and the checkpoint stays incomplete until all listed detail/transcript requirements are met.

- [ ] **Step 4: Leave the heartbeat active**

Resume the automation with the ten/five policy. Do not begin Milestone 2 while the checkpoint reports pending detail or transcript IDs.

### Task 4: Final verification and repository handoff

**Files:**
- Modify: `TODO.md` and the scoped code, tests, specifications, and reports above

**Interfaces:**
- Consumes: passing tests, current generated evidence, and remote Git identity.
- Produces: a scoped commit, verified remote parity, and an honest residual handoff.

- [ ] **Step 1: Run final checks**

Run `PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m pytest -q work-corpus/tests`, `git diff --check`, and `git status --short`.

- [ ] **Step 2: Stage only scoped files**

Do not stage `data/`, runtime state, the SQLite database, backups, or unrelated existing files. Inspect the staged name list and staged diff check.

- [ ] **Step 3: Commit and verify remote parity**

Commit the scoped changes, push the non-force update to `origin/main` under the existing user authorization, and verify `git rev-parse HEAD` equals `git ls-remote origin refs/heads/main`. Report that the heartbeat remains the only continuing work until exact ingestion completion.
