# Remaining Work After Ingestion

Status date: 2026-09-07
Evidence basis: `work-corpus/corpus/reports/status.json`, generated at
2026-09-07T00:28:01-07:00.

## The current boundary

TrojanHorse now has a source-backed, searchable evidence base. The mechanical
ingestion gate is closed for the currently available local sources and the
current Granola API listing. The next phase has not yet organized that evidence
into canonical people, projects, organizations, relationships, or task views.

This distinction matters:

- **Ingested** means the source is preserved, inventoried, represented in the
  local database, and searchable.
- **Organized** means the evidence has been reviewed, linked, canonicalized,
  and converted into derived entities, relationships, or task proposals with
  source locators.

The corpus is currently strong on the first meaning and largely unfinished on
the second.

## What is complete

### Local corpus and search

- 2,751 physical files are inventoried: 2,731 substantive files and 20 Finder
  metadata files.
- 1,693 source versions are represented: 712 current normalized outputs and
  981 retained prior-good outputs.
- Normalization reports zero errors and zero unsupported files.
- The full-text index has 71,983 rows and is fresh.
- Raw source material remains preserved. The runtime does not rewrite or delete
  provider data.

The 15 discovery records are intentionally excluded from extraction. They are
inventory evidence, not missing source content.

### Provider capture

| Source | Verified local result | Boundary |
| --- | --- | --- |
| Granola REST | 559 API notes across 19 pages; 559 summaries; 557 transcripts; 2 summary-only notes; all 559 imported and searchable | Complete for the current API listing. Granola's API does not expose notes that are still processing or lack generated summary/transcript data. |
| Granola MCP shadow | 559 UUID-listed IDs imported/searchable; 186 detail captures, 181 detailed summaries, 177 transcripts | Incomplete but redundant. 378 detail and 382 transcript gaps remain in this shadow feed; it does not block the REST archive. |
| Wispr Flow | 13 unique local records: 12 meeting records and 1 scratchpad note; 12 summaries; 13 transcript/content records; all 13 imported/searchable | Complete for the local full capture. Its capture metadata reported all available pages with `has_more=false`; the local snapshot has no usable retrieval dates. |
| Zoom | 231 tracked groups; 230 successful and 1 quality-limited partial; zero eligible media without a usable transcript or terminal status | Mechanical transcription coverage is closed. One partial result still needs quality review. |
| OneNote | 29 of 29 files parsed; 295 of 295 reviewed pages extracted | No current mechanical gap. |

## What is not complete

### 1. Source interpretation and reconciliation

- 470 Capacities pointer-only payloads still need one-to-one identity matching
  to local payload paths. No signed URLs were fetched.
- Wispr Flow date evidence remains unknown. Granola has only 74 records with
  known retrieval dates; this affects freshness and task-date interpretation,
  not preservation.
- One Zoom group has a quality-limited partial transcript/result.
- The report still lists one `mcp_malformed_item` review row. Final repeat
  imports reported `malformed=0`, so this row needs explicit reconciliation
  before final acceptance.

### 2. Review and canonicalization

These are review queues, not missing raw data:

- 793 scope-review items, including 52 meeting groups needing review.
- 1,396 source records flagged for personal or restricted-content review.
- 312 exact duplicate groups.
- 310 likely version families.
- 552 task-date review items.
- 350 task-scope review items.

No uncertain duplicate, version, scope, sensitivity, or date decision should
be forced. The source and the reason for each decision must remain traceable.

### 3. Derived organization has not run

The current report shows zero populated derived organization records:

- Entities: 0.
- Aliases: 0.
- Relationships: 0.
- Task candidates: 0 current and 0 historical/review.

Zero tasks is not proof that the corpus contains no work. It currently means
the supported entity, relationship, and task extraction phase has not been
executed. The next work is to derive these views from the searchable evidence,
with provenance and explicit review states.

## Ordered next work

This is the execution order for the remaining work. `TODO.md` remains the
checkbox checklist; this document is the persistent explanation of its open
scope.

1. Finish source interpretation: resolve the Capacities pointer queue, review
   scope and sensitivity, preserve Wispr unknown dates, inspect the Zoom
   partial, and reconcile the stale malformed-row review item.
2. Review duplicate and version families without deleting or merging uncertain
   source records.
3. Populate people, projects, organizations, and aliases through the existing
   entities APIs, each with source locators and ambiguity states.
4. Populate supported relationships and task proposals. Keep current tasks
   separate from historical commitments; unknown dates remain review items.
5. Produce the residual ledger: source ID/locator, unresolved reason, work
   attempted, and the smallest human decision needed.
6. Run final acceptance: rebuild reports, verify representative Work-scope
   searches, repeat derived writes for idempotency, and confirm raw/provenance
   preservation.

## What is deliberately not next

No additional historical Granola or Wispr Flow full pull is required for the
current captured sources. The older Granola MCP heartbeat is not needed to
close ingestion. Future Granola maintenance should use an API delta pull or a
separately reviewed webhook receiver; it should not reopen the completed
historical archive gate.

Email, Atlas integration, cloud raw-data processing, graph/vector
infrastructure, automatic historical task backfill, and provider write-back
remain outside this process.

## Definition of the next completion

The next milestone is complete only when the derived views have source-backed
locators, review/ambiguous states are explicit, uncertain merges are preserved
as unresolved, task dates follow the documented current-versus-historical rule,
and repeat execution does not duplicate derived records. A green ingestion
report alone is not enough.
