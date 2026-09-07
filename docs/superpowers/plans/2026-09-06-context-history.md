Historical context snapshot retained during glossary cleanup. Runtime claims below require reconciliation; see the completion handoff.

# Local Work Corpus Context

Status: Current operational state recorded on 2026-09-06. All currently
parseable sources are normalized. OneNote conversion and local Zoom coverage
are operational. Granola detail/transcript capture continues in bounded
five-record background batches.

The detailed live counts and remaining gaps are maintained in
[LOCAL_WORK_CORPUS_STATUS.md](docs/LOCAL_WORK_CORPUS_STATUS.md). The older
2026-09-04 acceptance numbers below are historical and must not be read as the
current runtime state.

This project is a private, local, single-user work-evidence corpus. It is
separate from Atlas. It does not read or write email.

## Purpose

The corpus has one factual source of truth and two derived views:

1. **Operating memory:** projects, meetings, decisions, commitments, current
   tasks, blockers, and follow-through.
2. **Career evidence:** source-backed accomplishments, ownership, outcomes,
   metrics, and safe wording derived from the same evidence.

The views share source IDs and provenance. They are not separate databases.

## Domain terms

| Term | Meaning |
|---|---|
| Raw evidence | The original local file or provider response. The system never rewrites it. |
| Captured | A provider response is preserved locally. This alone does not establish import or search coverage. |
| Imported | Captured content is represented in the corpus with its source identity and provenance. |
| Searchable | Imported evidence is represented in the query index and can be retrieved through the applicable scope rules. |
| Retryable outcome | An incomplete retrieval or processing attempt that remains eligible for another attempt, such as a provider rate limit. |
| Terminal unavailable | A specific source or requested content item cannot be obtained, with an evidenced reason recorded against its exact identity. |
| Source root | An explicit directory or archive identity for one source system. |
| Source record | One physical file or provider item in the manifest. |
| Source version | A content-hash version of a source record. A changed file receives a new version. |
| Evidence record | A derived, source-backed unit with a source version and locator. |
| Meeting group | One dated Zoom folder, including nested recording assets. |
| Canonical entity | One stable project, person, or organization record. |
| Alias | A former name, spelling, abbreviation, or source-specific name linked to a canonical entity. |
| Review item | An uncertain parse, classification, merge, date, task, or relationship proposal. |
| Current task | An explicit commitment from a future event or an event/meeting dated within the previous 14 calendar days at run time. |
| Coverage run | A resumable local pass that accounts for every eligible final Zoom media item. |
| Derived view | A rebuildable presentation of source-backed records, not a new source of truth. |

## Source map

- `data/Zoom/`: the reviewed inventory expected 276 dated meeting folders; the
  acceptance scan observed 275 dated source-bearing folders. Existing captions
  and transcripts are preferred. Every final media file without a usable
  transcript enters the required local coverage run. Raw artifacts remain
  visible with their status.
- `data/notes/Notes/`: Capacities Markdown and category export.
- `data/notes/40b7a161-92e3-450d-8dab-c2bb4a080adf_ExportBlock-7045c812-ccf8-4b28-b774-5502ee6696b2/`:
  Notion ExportBlock with LifeOS databases and local attachments.
- `data/notes/Backup/`: 29 OneNote section files. The local converter now
  extracts and normalizes all 295 observed pages while preserving the `.one`
  files as raw evidence.
- `data/notes/Capacities iCloud 2025-09-20/` and
  `data/notes/Capacities iCloud 2025-08-06/`: additional local Capacities
  snapshots containing payload-bearing files. They are preserved as source
  snapshots and are included in the current inventory.
- Formal local records: PDFs, Office files, tables, and related work
  documents identified by the inventory.
- `data/note-inventory-20260903-142816/`: machine-discovery evidence only. It
  is counted for physical accounting but is never extracted or indexed.

The reviewed inventory accounts for 1,413 physical files. The acceptance run
found 1,414 present files, including 20 Finder metadata files, and
58,965,738,600 bytes. The substantive count is 1,394 files. The only extra
physical file is the unclassified `data/.DS_Store` that was present in the
live tree and is preserved.

## Historical acceptance snapshot

- 315 source versions normalized; 418 remain in scope review; 1 optional
  parser case is unsupported; 0 parsing errors were recorded.
- Zoom has 4 existing media-bearing transcript groups and 68 transcript-only
  groups. The complete queue accounts for 231 eligible final media items with
  terminal `blocked` status because no verified local engine is installed.
  Zero eligible media items remain without a terminal status.
- The OneNote acceptance pass saw all 29 `.one` files but extracted 0 pages
  because the local converter is unavailable. The reviewed test expectation is
  295 pages; no raw OneNote file was read or changed by the blocked pass.
- No live Wispr Flow or Granola snapshot was present, and no network or cloud
  transcription path was used.
- FTS and relationship indexes are recorded fresh. The raw immutability check
  passed with 1,414 files, 58,965,738,600 bytes, and zero mismatches.

See the generated [status report](work-corpus/corpus/reports/status.html) and
the [current operational status](docs/LOCAL_WORK_CORPUS_STATUS.md).

## Rules

- Default queries include only `Work` records.
- `Personal`, `Mixed`, and `Unknown` records remain inventoried but stay out
  of the default query until a review resolves their scope.
- Confidential personnel and performance material is work-scoped for this
  single user and keeps a sensitivity label.
- Exact aliases and regex rules run before optional local model proposals. The
  most common valid spelling is selected. Ambiguous or risky merges require
  review.
- Old records remain historical. They do not create a current task backlog.
- Export, file-modification, and transcription dates do not make old evidence
  current.
- Raw or unreviewed fallback search is limited to already work-classified
  records. Returned snippets redact URL-like and secret-like values.
- Normalized text, SQLite state, FTS, and relationships live outside `data/`.
- Embeddings are deferred until exact search and relationship queries prove
  insufficient.
- The coverage run processes one eligible media item at a time. It saves a
  checkpoint after each item and resumes after interruption.
- When a verified local Whisper or equivalent engine is configured, the run
  records its exact executable and model version. The current machine uses
  local MacWhisper/MLX Whisper paths; 230 eligible groups succeeded and one
  remains partial because the recording is genuinely quiet.
- Every final Zoom media item has an existing transcript or a terminal local
  status. Failed, partial, blocked, and artifact items remain visible.
- Existing raw files stay in place. The system never moves, deletes, or
  rewrites them.

## Authority order

1. The files under `data/` are the source evidence.
2. `01_INVENTORY/` records the reviewed physical inventory and access status.
3. `docs/superpowers/specs/2026-09-04-local-work-corpus-design.md` is the
   architecture and behavior specification.
4. `docs/superpowers/plans/2026-09-04-local-work-corpus-implementation.md`
   is the reviewed implementation sequence.
5. `docs/adr/0001-local-work-corpus-boundary.md` records the durable boundary
   decision.
6. `TODO.md` is the current execution checklist and must not claim a task is
   complete before its verification gate passes.

There is no current `content.md` in this repository. `CONTEXT.md`, the design
specification, the ADR, the README, and
`docs/LOCAL_WORK_CORPUS_STATUS.md` carry the current project context.
