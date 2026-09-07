# Remaining Work After Ingestion

Status date: 2026-09-07
Evidence basis: [`status.json`](../work-corpus/corpus/reports/status.json),
generated at `2026-09-07T11:50:41-07:00`, plus the organization and
reconciliation ledgers in `work-corpus/state/`.

## The current boundary

The source-backed evidence base, deterministic organization pass, and safe
first-pass triage are complete for the currently captured local sources. The
semantic exception phase is not complete. It now needs only grouped decisions
for a small number of payload, scope, sensitivity, identity, and media items.

These terms are intentionally separate:

- **Ingested** means the source is preserved, inventoried, represented in the
  local database, and searchable.
- **Organized** means deterministic rules produced source-backed links,
  explicit entities, task proposals, and review items.
- **Reviewed** means a human accepted or rejected an interpretation. The
  organizer does not claim this state for ambiguous records.
- **First-pass triage** means the existing default rules handled a policy-stable
  queue without changing raw files, source classifications, or canonical facts.
  It does not mean a human approved an interpretation.

## What is complete

### Local corpus and search

- 2,751 physical files are inventoried: 2,731 substantive files and 20 Finder
  metadata files, totaling 55.5 GB.
- 1,849 source versions are represented: 773 normalized in the current parser
  pass and 1,076 retained prior-good outputs.
- Normalization reports zero errors and zero unsupported files.
- The full-text index has 72,138 rows and the relationship index has 1,243
  rows; both are fresh at the acceptance checkpoint.
- Raw source material remains preserved. The runtime does not rewrite or delete
  provider data. The raw immutability ledger remains passed with 1,414 files,
  matching byte totals, and matching stream hashes.

The 15 discovery records are intentionally excluded from extraction. They are
inventory evidence, not missing source content.

### Provider capture and coverage

| Source | Verified local result | Remaining boundary |
| --- | --- | --- |
| Granola REST | 559 unique API notes across 19 pages; 559 summaries; 557 transcripts; 2 summary-only notes; all 559 imported and searchable | Complete for the current API listing. No historical API pull is required to close this gate. |
| Granola MCP shadow | 559 UUID-listed IDs imported/searchable; 186 detail captures, 181 detailed summaries, 177 transcripts | Incomplete but redundant. Its 378 detail and 382 transcript gaps do not reduce REST archive coverage. |
| Wispr Flow | 13 unique local records: 12 meeting records and 1 scratchpad; 12 summaries; 13 transcript/content records; all imported/searchable | 13/13 have local capture and retrieval dates; all 12 meetings have start, end, and provider-modified dates; the scratchpad has provider-modified metadata but no event date in its source object. |
| Capacities | 563 typed pointer records; 557 matched to 451 local payload records; 1,216 confirmed pointer-to-payload relationships | Six pointers still lack file-size metadata and remain explicit review items. No signed URL was fetched. |
| Zoom | 231 tracked groups; 230 successful and 1 quality-limited partial; zero eligible media without a transcript or terminal status | The one partial result and 52 meeting-link reviews remain human review. |
| OneNote | 29 of 29 files parsed; 295 of 295 reviewed pages extracted | No current mechanical gap. |

The earlier malformed MCP review row is reconciled: the preserved source
version was restored during inventory and the clean repeat-import evidence
resolved that row. The stale 95 unanchored sensitivity rows created during the
same repair were also superseded by evidence-anchored review rows. The current
pending sensitivity queue is 1,396, matching the current deterministic
candidate count.

### Deterministic organization

The local `organize` pass was run twice with the same run date. Both runs
produced the same derived counts and the second run created no duplicate
entities, relationships, or review items.

- 9 explicit non-generic Capacities `Project` entities and 9 aliases were
  created through the existing entities APIs.
- 27 source-backed project links were recorded. No people or organizations
  were auto-created because the available alias dictionary did not establish a
  safe canonical identity.
- 48 ambiguous entity candidates remain review items.
- 1,910 evidence records were scanned for explicit task proposals. There are
  0 task rows and 0 current task rows. Historical or undated commitments were
  not promoted into a current backlog.
- The safe first pass resolved 4,411 policy-stable review rows and selected 622
  provisional duplicate/version display records while retaining every source
  record. The residual ledger now contains 68 pending items. It records source
  IDs, evidence locators when available, a bounded reason, the work attempted,
  and the smallest grouped decision needed. It does not copy raw sensitive
  text or provider URLs.
- The old 13 Wispr unknown-retrieval rows were superseded after the importer was
  corrected to map Wispr `meetings[].start`, `end`, and `modified_at`, plus the
  capture envelope's `captured_at`. They are not current review work.

## What remains

These are interpretation queues, not missing raw data:

| Grouped response code | Pending | Default first-pass action |
| --- | ---: | --- |
| `CAPACITIES_PAYLOAD` | 6 | Leave unresolved unless the local payload is identified. |
| `ENTITY_CANDIDATE` | 48 | Leave candidates unclassified. |
| `SCOPE_UNCONFIRMED` | 4 | Keep outside the default Work view. |
| `WORK_RESTRICTED` | 9 | Keep outside the Work view. |
| `ZOOM_PARTIAL` | 1 | Keep the partial result marked partial. |

The 68 rows are grouped in
[`first_pass_review.md`](../work-corpus/corpus/reports/first_pass_review.md).
The CSV contains bounded source metadata for the grouped exceptions; it does
not require item-by-item review. Duplicate/version choices are recorded in
[`first_pass_display_candidates.csv`](../work-corpus/corpus/reports/first_pass_display_candidates.csv)
and all original source records remain available.

## Ordered next work

The remaining work is now a short grouped response, in this order:

1. Resolve or leave the six Capacities payload gaps.
2. Confirm whether the nine Work-restricted sources may enter the intended
   downstream view; the default is to keep them out.
3. Leave the 48 entity candidates unclassified unless a source-backed identity
   is clear.
4. Leave the four unconfirmed-scope sources out and decide whether to accept
   the one partial Zoom result.

No duplicate/version, task-date, task-scope, meeting-link, or Wispr-date queue
requires item-by-item review for the current pass. If the user changes one of
the defaults, the agent can apply that grouped exception against the
source-backed ledger.

No additional historical Granola or Wispr full pull is required for the
currently captured sources. The older Granola MCP heartbeat is not needed to
close ingestion. Future Granola maintenance should use an API delta pull or a
separately reviewed webhook receiver; it should not reopen the completed
historical archive gate.

Email, Atlas integration, cloud raw-data processing, graph/vector
infrastructure, automatic historical task backfill, and provider write-back
remain outside this process.

## Reproduction

Run from the repository root:

```bash
PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m pytest -q work-corpus/tests
PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m work_corpus --root . organize --run-date 2026-09-07 --first-pass
PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m work_corpus --root . report
```

The organizer writes only rebuildable derived state:

- `work-corpus/state/organization_acceptance.json`
- `work-corpus/state/capacities_payload_reconciliation.json`
- `work-corpus/state/residual_ledger.json`
- `work-corpus/corpus/reports/residual_ledger.csv`
- `work-corpus/corpus/reports/status.json`
- `work-corpus/state/first_pass_acceptance.json`
- `work-corpus/corpus/reports/first_pass_review.md`
- `work-corpus/corpus/reports/first_pass_review.csv`
- `work-corpus/corpus/reports/first_pass_display_candidates.csv`

Raw files and provider captures remain outside Git and are not pushed as
repository content.
