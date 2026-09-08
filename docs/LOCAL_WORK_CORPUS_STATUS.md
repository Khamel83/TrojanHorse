# Local Work Corpus Status

Status date: 2026-09-07
Latest report: `2026-09-07T20:38:38-07:00`

## Current completion boundary

The two approved milestones are complete through deterministic organization
and the unified-corpus first pass: first ingestion and search verification,
then source-backed links, explicit projects, task-proposal scanning, and
grouped policy handling. No grouped review decisions are pending. Optional
semantic refinement remains downstream work. See the [remaining-work
map](REMAINING_WORK.md), the [first-pass review sheet](../work-corpus/corpus/reports/first_pass_review.md),
and the [completion handoff](superpowers/plans/2026-09-06-corpus-completion-handoff.md).

The local evidence base is complete for the currently captured Granola REST,
Granola MCP shadow, Wispr Flow, Capacities, Notion, OneNote, and Zoom sources
at the capture/inventory boundary. That does not mean every physical file has a
normalized text record: 902 source versions are media, metadata,
unknown/intermediate artifacts, or excluded records. The 20 local `.eml` files
are inventoried but are not yet parsed by the active runtime. Mailbox access is
still outside the system.
The REST archive is the Granola completion gate: 559 unique API notes are
imported and searchable, with 559 summaries and 557 transcripts. The older MCP
UUID feed remains a measurable but incomplete shadow. It does not block the
archive.

The deterministic `organize` command was run twice with the same date. It
produced 9 explicit Project entities, 27 evidence-backed project source links,
0 people, 0 organizations, 1,910 scanned task proposals, and 0 current task
rows. Ambiguous records remain in the residual ledger rather than being
silently canonicalized. The default query scope is now `All`: every nonblank
parseable source is searchable, with original Work, Personal, Mixed, Unknown,
and sensitivity labels preserved as provenance. `Work` remains an optional
narrow filter.

## Current corpus

- 2,751 physical source files are inventoried, totaling 55.5 GB.
- 2,751 source versions are represented.
- 1,849 normalization records exist: 773 are current normalized outputs and
  1,076 are retained prior-good outputs. 902 source versions have no
  normalization record because they are media, metadata, unknown/intermediate
  artifacts, or excluded records.
- Normalization reports 0 errors and 0 unsupported files.
- The FTS index has 72,138 rows and the relationship index has 1,243 rows;
  both are fresh.
- Raw files remain outside Git and are not rewritten by the corpus runtime.

## Source status

| Source | Current result | Remaining interpretation gap |
| --- | --- | --- |
| Granola REST | 559 unique notes across 19 list pages; 559 summaries; 557 transcripts; 2 summary-only notes; all 559 imported/searchable | Complete for the current API listing. |
| Granola MCP shadow | 559 listed UUIDs imported/searchable; 186 detail captures, 181 detailed summaries, 177 transcripts | 378 detail and 382 transcript gaps remain in this redundant shadow feed. |
| Wispr Flow | 13 local records: 12 meeting records and 1 scratchpad; 12 summaries; 13 transcript/content records; all imported/searchable | 13/13 have local capture and retrieval dates; all 12 meetings have start, end, and provider-modified dates; the scratchpad has provider-modified metadata but no event date in its source object. |
| Capacities | 563 typed pointer records; 557 matched to 451 local payload records; 1,216 confirmed pointer-to-payload relationships | 6 pointers retain explicit unresolved metadata under the accepted first-pass policy. No signed URL was fetched. |
| Zoom | 231 tracked groups; 230 succeeded and 1 is partial; 0 eligible final media lacks a transcript or terminal status | The partial result is accepted and preserved; 52 meeting groups retain a non-destructive `needs_review` linkage status. 49 non-final `.zoom`/`.tmp` artifacts remain inventory-only and are not treated as meeting media. |
| OneNote | 29 of 29 `.one` files parsed; 295 of 295 reviewed pages extracted | No current mechanical gap. |
| Notion | 95 pages, 2 databases, 24 attachments, 0 unresolved relationships | No current mechanical gap reported. |

The Capacities pass treats macOS duplicate suffixes such as `image.md (1)` as
their effective source extension for parsing. This restored provenance for the
older snapshot pointers without changing raw files. The six remaining pointer
reviews are specifically missing file-size metadata.

## Granola retrieval and continuation

The completed one-time archive was fetched through Granola's read-only REST API
from homelab. The API key is stored in the encrypted homelab `maya` vault as
`GRANOLA_API_KEY`; it is not stored in this checkout. The capture is
`data/mcp/granola/granola-api-backfill-2026-09-07T06-34-00Z.json`.

The API path used 30-note list pages, opaque cursors, note retrieval with inline
transcripts, and the paginated transcript endpoint for oversized notes. It
preserved the raw response locally and imported all 559 REST IDs. The two notes
with empty transcript arrays remain explicit summary-only records.

The previous MCP heartbeat is not required for the completed REST archive. If
future steady-state delivery is needed, use an API delta pull with
`updated_after` or a separately reviewed webhook receiver where the account
plan and a public HTTPS receiver support them. No provider write-back was
created here.

The optional MCP shadow workflow processes up to ten pending meeting IDs on a
clean detail pass, serializes transcript requests, and uses five IDs after an
explicit rate-limit outcome. It preserves every response locally and keeps
retryable and terminal outcomes explicit. It is not a historical completion
gate.

## Organization and review queues

The acceptance state is
`work-corpus/state/organization_acceptance.json`. The residual ledger is
[`residual_ledger.csv`](../work-corpus/corpus/reports/residual_ledger.csv) and
its machine-readable form is
[`residual_ledger.json`](../work-corpus/state/residual_ledger.json).

The first pass resolved 4,479 review rows and selected 622 provisional
duplicate/version display records. The residual ledger contains 0 pending
entries. The 48 ambiguous titles are recorded in
[`first_pass_topic_labels.csv`](../work-corpus/corpus/reports/first_pass_topic_labels.csv)
as generic topic labels; no person, project, or organization was inferred.

The old 13 Wispr date rows are resolved as stale parser results. The corrected
import maps Wispr `meetings[].start` to the event date and the saved envelope's
`captured_at` to local capture/retrieval dates. It preserves `end` and
`modified_at` as separate derived metadata fields. It does not convert a
`modified_at` value into an event date.

These are accepted provenance and quality states, not missing raw data. The
organizer retains all eligible source records, does not force uncertain merges,
and keeps historical task statements out of the current-task view.

## Full-system audit boundary

The corpus pipeline is mechanically usable for the captured local archive, but
the repository as a whole is not yet a finished assistant or service. The
active CLI provides inventory, normalization, local transcription, exact FTS
search, deterministic organization, and reports. It does not yet provide a
local answer-synthesis service, project/task/career deliverables, a scheduled
Granola delta path, production monitoring, or a clean repository-wide install
and test entry point. The older root package and Atlas bridge remain historical
code and are not part of the active boundary. See the [full audit](TROJAN_HORSE_AUDIT.md)
for the ordered completion path and the owner decisions.

## Reproduction and verification

Run from the repository root:

```bash
PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m pytest -q work-corpus/tests
PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m work_corpus --root . organize --run-date 2026-09-07 --first-pass
PYTHONPATH=work-corpus/src /opt/homebrew/bin/python3 -m work_corpus --root . report
```

The current report is [`status.html`](../work-corpus/corpus/reports/status.html)
and the machine-readable report is
[`status.json`](../work-corpus/corpus/reports/status.json). The report records
the raw immutability result, provider coverage, FTS/relationship freshness,
and organization counts separately. Its raw-immutability result is explicitly
marked as historical because the saved comparison covers 1,414 files, while
the current inventory contains 2,751 files.

## Boundaries

- Raw source files and provider captures are preserved locally and are not
  pushed as repository content.
- The corpus does not write back to Granola, Wispr Flow, Capacities, OneNote,
  Zoom, or any other provider.
- No cloud transcription path is used. Local transcription output is derived
  evidence tied to source-media provenance.
- No automatic historical task backfill, email, Atlas integration, or external
  model call with raw corpus content is part of this milestone.
- The private `All` query includes retained scope/sensitivity records. A future
  external or narrower release view still requires its own explicit review.
