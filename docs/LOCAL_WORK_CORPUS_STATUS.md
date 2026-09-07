# Local Work Corpus Status

Status date: 2026-09-07

## Current completion boundary

The user approved two ordered milestones: finish ingestion and verify search,
then organize people, projects, relationships and supported tasks. See
[completion handoff](superpowers/plans/2026-09-06-corpus-completion-handoff.md).

The saved Granola captures now reconcile through inventory, source versions,
evidence, and searchable IDs. The one-time REST archive is complete for the
current API listing: 559 unique API notes are imported and searchable, with
559 summaries and 557 transcripts. The older MCP connector checkpoint remains
incomplete for its separate UUID identity set, but it is now a redundant shadow
feed and does not block the archive or the next milestone. The connected detail
endpoint allows up to ten IDs per clean pass; transcript requests remain one ID
at a time. An explicit rate limit causes a five-ID recovery pass.

The latest checkpoint is derived from raw captures, source records, evidence,
and search by exact ID. The original 2026-09-04 acceptance snapshot remains
historical evidence; the clean-session checklist is `TODO.md`. See the
[remaining-work map](REMAINING_WORK.md) for the exact boundary between
completed ingestion and unfinished organization.


## Current corpus

- 2,751 physical source files are inventoried, totaling 55.5 GB.
- 1,693 source versions are represented: 712 active normalized outputs and 981
  retained prior-good outputs.
- Normalization reports 0 errors and 0 unsupported files.
- The FTS index has 71,983 rows and is fresh. The relationship index is fresh
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
| Granola | REST archive: 559 unique notes across 19 list pages; 559 summaries, 557 transcripts; all 559 REST IDs imported and searchable. MCP shadow: 559 listed UUIDs; 186 detail captures, 181 detailed summaries, 177 transcripts; all 559 shadow IDs imported/searchable. | The REST API and MCP connector use different provider ID shapes (`not_...` versus UUID). The MCP shadow has 378 detail and 382 transcript gaps, plus one unlisted requested ID; those gaps do not reduce the complete REST archive. |

## Granola retrieval and continuation

The completed one-time archive was fetched through Granola's read-only REST API
from homelab. The API key is stored in the encrypted homelab `maya` vault as
`GRANOLA_API_KEY`; it is not stored in this checkout. The capture is
`data/mcp/granola/granola-api-backfill-2026-09-07T06-34-00Z.json`.

The API path used 30-note list pages, opaque cursors, note retrieval with
inline transcripts, and the paginated transcript endpoint for oversized notes.
It paced requests below the documented sustained limit and retried transient
failures. The resulting raw capture has 559 notes, 19 list pages, 559
summaries, and 557 transcript arrays. The local report records REST coverage
under `granola_progress.rest_api`.

The previous Codex heartbeat was not present in the current automation registry
when finalization was checked, so it was not recreated for a redundant
historical MCP drain. If future steady-state delivery is needed, use an API
delta pull with `updated_after` or Granola webhooks where the account plan and a
public HTTPS receiver support them; neither provider write was created here.

The MCP shadow workflow, when deliberately run, processes up to ten pending
meetings on a clean pass, with five IDs after an explicit rate limit. Each pass:

1. Reads the derived local Granola progress checkpoint.
2. Fetches details for up to ten IDs and transcripts one ID at a time.
3. Preserves the raw response in `data/mcp/granola/`.
4. Runs `mcp-import` and refreshes the report.
5. Keeps exact retry IDs and reduces the next pass after a rate limit; it does
   not use a manual cursor.

Provider `not_found` results are retained as terminal unavailable records. A
provider cooldown or transient error causes a later retry; it does not discard
the cursor or source content. The MCP shadow workflow is not required for the
completed REST archive.

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

The current verification suite passes 166 tests. The human-readable report is
[status.html](../work-corpus/corpus/reports/status.html). Local MCP and REST
capture state is intentionally ignored by Git and is recorded in
`work-corpus/state/mcp/`.

## Boundaries

- Raw source files and provider captures are preserved locally and are not
  pushed as repository content.
- The corpus does not write back to Granola, Wispr Flow, Capacities, OneNote,
  Zoom, or any other provider.
- No cloud transcription path is used. Local MacWhisper/MLX Whisper output is
  derived evidence only and remains tied to its source media provenance.
- No user action is required for the currently available Capacities files.
