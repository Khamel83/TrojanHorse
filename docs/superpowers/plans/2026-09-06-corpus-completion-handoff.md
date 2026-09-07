# Corpus completion handoff for Luna

Status: User confirmed both milestones in order; Antigravity Opus 4.6 Thinking
approved the supplied plan with an index-API annotation, now applied. See
`../reviews/2026-09-06-corpus-completion-opus-review.md`. Documentation and
planning are now supplemented by the verified execution record below.

## Post-handoff policy amendment — 2026-09-07

The user approved a final bulk policy pass after the ordered implementation.
It supersedes the earlier Work-only default and the instruction to leave the
grouped queue pending: the default query is now unified `All`, `Work` remains
an optional filter, all nonblank parseable source records remain searchable,
and original scope/sensitivity labels remain provenance. The 68 grouped
exception rows are resolved without deleting raw data or inventing canonical
identities. Ambiguous titles are generic topic labels; the six unavailable
Capacities payloads remain explicit unresolved metadata; and the one Zoom
partial is accepted as partial.

## User-approved throughput amendment

On 2026-09-06 the user approved a faster Granola pull after the connected tool
contract was verified. `granola_get_meetings` accepts up to ten meeting IDs,
while `granola_get_meeting_transcript` accepts one ID per call. Execution
therefore supersedes the earlier five-ID clean-pass wording with up to ten
detail/transcript IDs per pass, serialized transcript requests, and a five-ID
recovery pass after an explicit rate-limit outcome. The ingestion-before-
organization order and exact-ID completion rule are unchanged.

On 2026-09-07 the user supplied a Granola API key and authorized its storage in
the existing encrypted homelab `maya` vault as `GRANOLA_API_KEY`. The official
REST API was verified with HTTP 200, then used for the one-time archive: 559
unique notes across 19 list pages, 559 summaries, and 557 transcript arrays.
All 559 REST IDs are imported and searchable in TrojanHorse. REST IDs use the
provider's `not_...` format, while the MCP connector exposes a separate UUID
set, so `granola_progress.rest_api` reports this archive independently. The
MCP shadow gaps no longer block ingestion completion. No webhook endpoint or
other provider write was created.

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

### 2026-09-07 execution correction

The saved Wispr capture was not dateless. Its 12 meeting records contain
`start`, `end`, and `modified_at`; its one note contains `modified_at`; and the
capture envelope contains `captured_at`. The initial generic importer missed
`start` and did not propagate the envelope timestamp to item metadata. The
corrected importer now records 13/13 local capture dates, 12/13 meeting event
dates, all 12 meeting end dates, 13/13 provider-modified dates, and 13/13
retrieval dates. The one note remains without an event date because its source
object does not provide one. The 13 review rows created by the old mapping were
superseded, and the derived date metadata and parser provenance were refreshed.

## Ordered implementation and acceptance

1. Establish one writer. Inspect and pause the existing Granola heartbeat while
   repairing ingestion. Record its ID and settings and resume it after validation.
   Read AGENTS.md, CONTEXT.md, TODO.md, this plan, the design and status docs.
   Preserve unrelated changes and raw data. Snapshot SQLite with its backup API
   before migration or bulk repair; keep state consistent with any WAL.
2. Reconcile all existing Granola captures, inventory records, database evidence
   and search entries. Use the read-only REST backfill as the primary one-time
   archive path; register the resulting capture with the existing inventory
   workflow, then import and rebuild the existing indexes. Keep the MCP UUID
   checkpoint as a separate shadow-feed diagnostic. Prefer existing CLI
   operations; confirm command help before running. Prove the REST capture has
   559 unique API IDs, source version, content and query evidence. Reimport
   twice to prove idempotency and that richer summaries/transcripts survive
   thinner responses. Add focused regression coverage for the missing-capture
   boundary if code changes are needed.
3. Replace manually incremented progress with derived sets: listed IDs, detailed
   IDs, transcript IDs, retryable IDs, terminal unavailable IDs. Distinguish local
   capture success from database import and query verification. Audit raw error
   responses and capture requests; an ID absent from the inventory cannot count
   toward completing an inventory item. Revalidate actual inventory IDs as needed.
   Summary-only meetings must still be eligible for transcript retrieval. Preserve
   raw error responses and explicit empty/no-transcript outcomes; parser failures
   and rate limits remain retryable. Never silently drop an item because its ID
   appeared in a prior partial capture. Test retry and completion arithmetic.
4. The REST archive supersedes the historical MCP heartbeat for the one-time
   ingestion gate. Keep the tested MCP ten/five adaptive policy documented for
   optional future shadow refreshes, but do not recreate a five-minute heartbeat
   solely to duplicate the completed REST archive. Future steady-state refreshes
   should use an API `updated_after` delta or supported Granola webhooks after a
   separate receiver review.
5. Reconcile remaining source gaps using available local evidence. Match the 470
   Capacities pointers against local payloads with evidence-backed identities;
   preserve ambiguity and missing targets as explicit outcomes. Do not fetch signed
   URLs or require another export. Inspect Wispr's 13 records for event dates;
   map the provider fields actually present and record only genuinely missing
   dates. Retain the quiet Zoom partial and artifacts as terminal evidence;
   confirm all 29 OneNote files/295 pages remain represented.
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
