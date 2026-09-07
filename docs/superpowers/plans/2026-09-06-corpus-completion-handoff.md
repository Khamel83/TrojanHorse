# Corpus completion handoff for Luna

Status: User confirmed both milestones in order; Antigravity Opus 4.6 Thinking
approved the supplied plan with an index-API annotation, now applied. See
`../reviews/2026-09-06-corpus-completion-opus-review.md`. Documentation and
planning only; execute the reviewed checklist in a clean Luna session.

## Evidence and corrections

Prior completion claims need reconciliation. `mcp_ingest.py:ingest_mcp_sources`
reads `_source_rows(con)`, so merely saving a new JSON capture and running
`mcp-import` does not establish its inventory, evidence, or search visibility.
Recent imports repeatedly reported eight source files despite 31 batch captures.
The report still lists six Granola source files and an unchanged FTS count.
Verify this broken boundary first. Captures remain locally preserved.

Progress JSON claims 194 detailed meetings, 142 transcripts, 363 pending; these
are unverified counters. Batch 0031 contained one retry and four new IDs, but
the counter advanced by five. Two stored unavailable IDs also differ from
inventory IDs in earlier runs. Recompute by exact IDs; never repair IDs by guess.

## Ordered implementation and acceptance

1. Establish one writer. Inspect and pause the existing Granola heartbeat while
   repairing ingestion. Record its ID and settings and resume it after validation.
   Read AGENTS.md, CONTEXT.md, TODO.md, this plan, the design and status docs.
   Preserve unrelated changes and raw data. Snapshot SQLite with its backup API
   before migration or bulk repair; keep state consistent with any WAL.
2. Reconcile all existing Granola captures, inventory records, database evidence
   and search entries. Register missing captures using the existing inventory
   workflow, then import and rebuild the existing indexes. Prefer existing CLI
   operations; confirm command help before running. Prove one previously missing
   capture is represented by exact provider ID, source version, content and query
   evidence. Repeat for all preserved batches. Reimport twice to prove idempotency
   and that richer summaries/transcripts survive thinner responses. Add focused
   regression coverage for the missing-capture boundary if code changes are needed.
3. Replace manually incremented progress with derived sets: listed IDs, detailed
   IDs, transcript IDs, retryable IDs, terminal unavailable IDs. Distinguish local
   capture success from database import and query verification. Audit raw error
   responses and capture requests; an ID absent from the inventory cannot count
   toward completing an inventory item. Revalidate actual inventory IDs as needed.
   Summary-only meetings must still be eligible for transcript retrieval. Preserve
   raw error responses and explicit empty/no-transcript outcomes; parser failures
   and rate limits remain retryable. Never silently drop an item because its ID
   appeared in a prior partial capture. Test retry and completion arithmetic.
4. Update the existing heartbeat to register captures before import and prioritize
   retries, with at most five meeting IDs per run. Respect provider cooldowns;
   reduce request bursts/back off after rate limits. Resume the single heartbeat.
   Completion requires every listed ID and requested transcript to be captured,
   imported and indexed or explicitly terminal with a supported reason. Do not
   stop solely because metadata_only_pending is zero. Stop the automation on
   verified completion and notify only for completion or actionable failures.
5. Reconcile remaining source gaps using available local evidence. Match the 470
   Capacities pointers against local payloads with evidence-backed identities;
   preserve ambiguity and missing targets as explicit outcomes. Do not fetch signed
   URLs or require another export. Inspect Wispr's 13 records for event dates;
   record unknown dates honestly. Retain the quiet Zoom partial and artifacts as
   terminal evidence; confirm all 29 OneNote files/295 pages remain represented.
6. Process existing interpretation queues with existing rules and APIs: scope,
   sensitivity, duplicate/version families, task dates and ambiguous meeting links.
   Populate supported entity aliases, relationships and explicit task candidates
   from available evidence. Use source locators and deterministic rules first;
   ambiguous proposals remain visible. All eligible parseable content stays
   preserved/normalized; default search remains Work-only. Historical commitments
   stay historical; the current-task window is relative to runtime date, never
   import/export date. Zero current tasks can be correct. Do not force all queues
   to zero or invent canonical links. Report what automation resolved and what
   specifically needs human interpretation, with concrete choices and evidence.
7. Refresh inventory, normalization, MCP evidence, indexes and reports in dependency
   order. Verify counts by distinct identities, provenance, representative queries,
   raw preservation and appropriate focused/full tests. Previous 152 passing tests
   are historical, not proof of this repair. Update README, CONTEXT, TODO, status,
   design amendments and review dispositions with actual results. Commit only
   scoped code/docs/tests, then push under existing user authorization and verify
   remote commit identity. Raw captures and private runtime state remain local.

## Scope and stop conditions

Use the existing Python/SQLite corpus. No email/provider writes, Atlas, cloud raw
evidence processing, new graph/vector infrastructure or polished career generator.
Operating memory and career evidence remain derived views over source provenance;
structured decision/career feature development stays explicitly deferred.
Unresolved identity/date/sensitivity questions are reported precisely and do not
block independent ingestion. Missing local evidence receives a reason and the
smallest concrete user action if needed. Do not rerun successful transcription
solely to replace historical blocked wording.

## Verified entry points

From `/Volumes/2TB_SSD/GitHub/TrojanHorse`, use the installed interpreter
`/Volumes/2TB_SSD/Tools/work-corpus-venv/bin/python` with
`-m work_corpus --root .`. Existing subcommands include `inventory`,
`mcp-import`, `normalize`, `report` and `query`. The safe dependency order is
inventory, MCP import, normalization, index verification, report. Inspect help
before execution. There is no standalone index-rebuild CLI command.
`query.py:rebuild_search_index` is the existing Python entry point; `search`
also rebuilds it. Inspect its behavior before treating it as a read-only probe.
`entities.py` contains `seed_alias_dictionary` and `resolve_mentions`;
`tasks.py:extract_task_proposals` takes evidence identity, event-date basis and
runtime date explicitly. Add only the small resumable orchestration needed to
apply these APIs to actual evidence; do not assume a corpus-wide enrichment CLI
already exists. Inspect tests and signatures before invoking them.

## Copyable start instruction

Execute TODO.md in order using this reviewed handoff. Begin with one-writer control
and the capture-to-inventory-to-import verification. Read actual CLI help and tests;
do not trust prior cumulative counters. Complete all locally actionable work,
record specific residuals, update documentation, and verify the authorized push.
