# Local Work Corpus TODO

Status: Tasks 0–9 implementation and mechanical acceptance completed on
2026-09-04. The raw corpus is unchanged. Successful OneNote conversion and
successful local Zoom transcription remain blocked by unavailable local tools.

Authoritative plan: [docs/superpowers/plans/2026-09-04-local-work-corpus-implementation.md](docs/superpowers/plans/2026-09-04-local-work-corpus-implementation.md)

## Definition of complete ingestion

The implementation is complete when the corpus has local coverage of every
source that the local adapters can read.

- Every physical file has a manifest record and a processing status.
- Every readable source has a derived evidence record with provenance.
- Existing Zoom transcripts are linked before new transcription.
- Every eligible final Zoom MP4 or M4A without a usable transcript runs through
  the local transcription queue.
- The queue processes one media item at a time and saves a checkpoint after
  each item.
- Each final media item has a terminal status. A failed, partial, blocked, or
  artifact result remains visible in the report.
- Raw files remain unchanged.

This milestone does not require a graph, embeddings, perfect entity matching,
or complete task interpretation. Those are later derived views.

## Completed foundation

- [x] Inventory the raw `data/` tree without changing it.
- [x] Separate Capacities, Notion, OneNote, Zoom, formal records, and discovery evidence.
- [x] Verify the reviewed OneNote parser fixture against all 29 files and the
  295-page expectation; the current runtime pass fails closed because its
  converter is unavailable.
- [x] Define the local-only, single-user, no-email, no-Atlas boundary.
- [x] Complete Antigravity/Gemini 3.8 Flash adversarial design review.
- [x] Complete Gemini 3.1 Pro adversarial implementation-plan review.
- [x] Document the domain context and boundary ADR.

## Implementation sequence

- [x] Task 0 — Promote the reviewed `work-corpus/` scaffold. Exclude email code, Outlook scripts, `.pyc` files, and raw data. (commit `fb67385`; focused/full package tests pass; exact help gate verified with a temporary local `python3` shim)
- [x] Task 1 — Lock the local boundary and package entry point. (commits `a6fe51f`, `df5b3c5`, `4edaa06`; focused 10/10 and full 12/12 package tests pass; review approved with minor help-text wording note)
- [x] Task 2 — Build the complete immutable manifest and explicit source registry. (commits `a115057` through `add7e97`; 56 package tests pass; source/version, scope, Zoom, migration, symlink, residual, and derived-path gates verified)
- [x] Task 3 — Replace the bootstrap schema with the provenance model. (commits `37e50d6`, `bf3b7a6`, `800ad7c`, `6773540`; schema, FTS, deterministic APIs, safe legacy migration, report integration, and current-task boundary verified; final review approved)
- [x] Task 4 — Implement safe extraction adapters for text, Office files, Notion, Capacities, OneNote, and formal records. (commits `c3fd492`, `b267b9e`; parser/version, provenance, redaction, archive, and fail-closed gates pass; OneNote runtime converter remains unavailable)
- [x] Task 5 — Correct Zoom meeting grouping and build the complete local transcription queue. (commits `6551d5f` through `dda1e78`; 231 eligible media items reached terminal `blocked`, 114 artifacts remain visible, and 4 existing media-bearing transcript groups were linked first)
- [x] Task 6 — Add canonical project, person, and organization names, aliases, scope review, and current-task rules. (commits `88f58f0`, `57afff1`, `e534838`; synthetic entity/task gates pass and the real current-task view contains 0 candidates)
- [x] Task 7 — Implement Work-only local query, evidence labels, redaction, FTS, and relationships. (commits `b0d2c01`, `402f49c`; seven real query categories returned Work-scoped source-backed results and the rebuilt FTS/relationship indexes are fresh)
- [x] Task 8 — Add local Wispr Flow and Granola snapshot intake with idempotent checkpoints. (commits `be3dab5`, `3ddabd6`; 7 focused tests pass; no live MCP connection or snapshot was used)
- [x] Task 9 — Run the full local coverage pass, complete reports, verify raw immutability, and update operational docs. (commits `4fc65bc`, `ff7699a`; report and acceptance artifacts record all counts, statuses, blockers, and zero unprocessed eligible media)

## Required gates

- [x] No Atlas bridge or launch service watches `data/` (verified before source reads).
- [x] Raw paths, sizes, modification times, and hashes remain unchanged after the acceptance run; 1,414 files, 58,965,738,600 bytes, zero mismatches.
- [x] The default query never returns Personal, Mixed, or Unknown records (synthetic and real query suite gates pass).
- [x] Current tasks use only explicit commitments with an event/meeting date in the previous 14 calendar days at run time or in the future (synthetic boundary gates pass; real view has 0 candidates).
- [x] Existing transcripts are linked before any local transcription (4 media-bearing groups linked before queue execution).
- [x] Every eligible final Zoom media item has an existing transcript or a terminal local transcription status (231 terminal `blocked`; 0 without terminal status). This is accounting completeness, not successful transcription.
- [x] The local transcription runner uses one media item at a time and resumes from persisted checkpoints (synthetic coverage gates pass).
- [x] No eligible media item remains silently unprocessed when the coverage pass ends.
- [ ] The configured local Whisper or equivalent engine records its executable and model version. BLOCKED: no verified local engine is installed, so no media was successfully transcribed.
- [ ] The local OneNote converter is available and fails closed when absent. FAIL-CLOSED RESULT: 29 files blocked, 0 pages extracted, converter unavailable; reviewed expectation is 295 pages.
- [x] Parser failures, missing attachments, uncertain merges, conflicts, and scope decisions remain visible in review records and reports.
- [x] No email access, cloud transcription, external raw-data model call, raw-file movement, or raw-file deletion is introduced.

## Intentionally deferred

- Email integration.
- Atlas integration.
- Automatic historical task backfill.
- A separate graph database.
- An embedding index or vector store.
- Structured decision extraction before the source coverage pass is complete.
- A first-class career-claim table or polished career document generator.
