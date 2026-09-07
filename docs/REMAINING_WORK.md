# Remaining Work After Ingestion

Status date: 2026-09-07
Evidence basis: [`status.json`](../work-corpus/corpus/reports/status.json),
generated at `2026-09-07T11:50:41-07:00`, plus the organization and
reconciliation ledgers in `work-corpus/state/`.

## The current boundary

The source-backed evidence base and its deterministic organization pass are
complete for the currently captured local sources. The semantic review phase
is not complete. It still needs human decisions for scope, sensitivity,
identity, duplicates, versions, dates, and a small number of media or payload
links.

These terms are intentionally separate:

- **Ingested** means the source is preserved, inventoried, represented in the
  local database, and searchable.
- **Organized** means deterministic rules produced source-backed links,
  explicit entities, task proposals, and review items.
- **Reviewed** means a human accepted or rejected an interpretation. The
  organizer does not claim this state for ambiguous records.

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
| Wispr Flow | 13 unique local records: 12 meeting records and 1 scratchpad; 12 summaries; 13 transcript/content records; all imported/searchable | The local capture has no usable retrieval dates, so freshness remains unknown. |
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
- The residual ledger contains 4,492 pending items. It records source IDs,
  evidence locators when available, a bounded reason, the work attempted, and
  the smallest human decision needed. It does not copy raw sensitive text or
  provider URLs.

## What remains

These are interpretation queues, not missing raw data:

| Review type | Pending | Smallest next decision |
| --- | ---: | --- |
| Capacities payload match | 6 | Supply or identify the local payload, or explicitly approve a reviewed fetch/export. |
| Scope | 443 | Confirm Work, Personal, Mixed, or Unknown. |
| Sensitivity | 1,396 | Confirm whether each flagged source may enter the intended downstream view. |
| Exact duplicate group | 312 | Choose a canonical display record, if any; retain provenance copies. |
| Version family | 310 | Identify current versus historical versions without deleting source records. |
| Entity candidate | 48 | Confirm entity type and canonical name, or leave unresolved. |
| Meeting link | 52 | Confirm the correct Zoom transcript/media association. |
| Zoom quality | 1 | Accept the partial transcript or authorize a new local quality pass. |
| Wispr date | 13 | Supply provider-backed retrieval timing or accept unknown freshness. |
| Task date | 1,561 | Confirm an event date or leave the proposal historical/unresolved. |
| Task scope | 350 | Confirm Work scope before surfacing a task. |

The scope report groups 443 scope items with 350 task-scope items as 793
scope-related review items; meeting-link reviews are reported separately.

## Ordered next work

The remaining work is now selective human review, in this order:

1. Resolve the six Capacities pointers with missing file-size metadata if the
   corresponding local payload can be identified without guessing.
2. Review the residual ledger selectively for the intended downstream view:
   scope and sensitivity first, then duplicate/version decisions.
3. Review the 48 entity candidates and add people or organizations only when a
   source-backed canonical identity is clear.
4. Review the Zoom partial and meeting links, and resolve Wispr freshness only
   when provider-backed dates are available.
5. Promote only explicitly dated, Work-scoped task proposals that satisfy the
   runtime's future-or-previous-14-days rule. Keep older commitments as
   historical evidence.

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
PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m work_corpus --root . organize --run-date 2026-09-07
PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m work_corpus --root . report
```

The organizer writes only rebuildable derived state:

- `work-corpus/state/organization_acceptance.json`
- `work-corpus/state/capacities_payload_reconciliation.json`
- `work-corpus/state/residual_ledger.json`
- `work-corpus/corpus/reports/residual_ledger.csv`
- `work-corpus/corpus/reports/status.json`

Raw files and provider captures remain outside Git and are not pushed as
repository content.
