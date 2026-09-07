# Local Work Corpus Status

Status date: 2026-09-06

## Reconciliation required before completion

The user approved two ordered milestones: finish ingestion and verify search,
then organize people, projects, relationships and supported tasks. See
[completion handoff](superpowers/plans/2026-09-06-corpus-completion-handoff.md).

The counts below are a historical operational snapshot, not current verified
coverage. Granola capture batches have been saved without a corresponding
inventory refresh: `mcp-import` reads registered source records, not the inbox
directory directly. Command success alone did not prove new batches were imported.
The manual progress counters also counted a retry as a new meeting. Reconcile
raw captures, source records, evidence and search by exact ID before reporting
remaining counts. Two unavailable IDs need exact-identity validation.

Remaining work includes this ingestion repair, all pending Granola transcripts
and retries, Capacities pointer matching, date gaps, interpretation queues,
entity/relationship/task population, final verification and documentation.
The clean-session checklist is `TODO.md`; the handoff carries acceptance gates.

This document is the current operational status. The original 2026-09-04
acceptance snapshot remains in the implementation plan as historical evidence;
its early `blocked` counts were resolved after the required local tools and
additional source exports were found.

## Current corpus

- 2,718 physical source files are inventoried, totaling 55.3 GB.
- 1,693 parseable source versions are normalized.
- Normalization reports 0 errors and 0 unsupported files.
- The FTS index has 71,259 rows and is fresh. The relationship index is fresh
  with 0 rows because entity relationship extraction is not yet populated.
- Raw files remain outside Git and are not rewritten by the corpus runtime.

## Source status

| Source | Current result | Remaining interpretation gap |
| --- | --- | --- |
| Zoom | 231 tracked groups; 230 succeeded, 1 partial, 114 artifact results; 0 blocked, pending, or missing terminal results | The one partial recording is genuinely quiet and has no reliable timestamp cues. |
| OneNote | All 29 `.one` files parsed; 295 pages extracted and normalized | None for currently available files. |
| Capacities | 1,722 local source files, including 451 payload files from the original export and two iCloud snapshots | 470 pointer records are not yet identity-linked one-to-one to local payload paths. Local payload bytes that were available are preserved and normalized; no signed URLs were fetched. |
| Notion | 95 pages, 2 databases, 24 attachments, 0 unresolved relationships | None reported by the current status run. |
| Wispr Flow | 13 local records captured | The local snapshot has no usable retrieval dates. |
| Granola | 559 listed meetings; 69 with detailed summaries and 19 with transcripts captured locally | 488 metadata-only records remain for incremental five-at-a-time retrieval. Two provider IDs are explicitly recorded as unavailable. |

## Granola continuation

The Codex app has a background heartbeat named **Continue Granola corpus
capture**. When active, it processes at most five pending meetings every five
minutes. Each pass:

1. Reads the local Granola progress cursor.
2. Fetches meeting details and transcripts.
3. Preserves the raw response in `data/mcp/granola/`.
4. Runs `mcp-import` and refreshes the report.
5. Advances the cursor only after the local capture succeeds.

Provider `not_found` results are retained as terminal unavailable records. A
provider cooldown or transient error causes a later retry; it does not discard
the cursor or source content. The heartbeat is paused during repository
finalization and must be resumed afterward.

## Review queues

The current report contains interpretive review queues for scope, dates, task
scope, and sensitivity. These queues do not mean source content was excluded.
All parseable source versions are normalized because the local configuration
explicitly enables complete ingestion. Review is for interpretation and
canonicalization, not for deciding whether to preserve available source data.

## Reproduction and verification

Run from the repository root:

```bash
PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m pytest -q work-corpus/tests
/Volumes/2TB_SSD/Tools/work-corpus-venv/bin/python -m work_corpus --root . report
```

The current verification suite passed with 152 tests. The human-readable report
is [status.html](../work-corpus/corpus/reports/status.html). Local MCP capture
state is intentionally ignored by Git and is recorded in
`work-corpus/state/mcp/`.

## Boundaries

- Raw source files and provider captures are preserved locally and are not
  pushed as repository content.
- The corpus does not write back to Granola, Wispr Flow, Capacities, OneNote,
  Zoom, or any other provider.
- No cloud transcription path is used. Local MacWhisper/MLX Whisper output is
  derived evidence only and remains tied to its source media provenance.
- No user action is required for the currently available Capacities files.
