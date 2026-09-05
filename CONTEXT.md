# Local Work Corpus Context

Status: Tasks 0–9 implemented and mechanically accepted on 2026-09-04.
The raw corpus is unchanged. OneNote conversion and successful local Zoom
transcription remain blocked by unavailable local tools.

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
- `data/notes/Backup/`: 29 OneNote section files. The reviewed parser fixture
  recorded 295 pages, but the current runtime acceptance found no converter and
  therefore blocked all 29 files before raw reads.
- Formal local records: PDFs, Office files, tables, and related work
  documents identified by the inventory.
- `data/note-inventory-20260903-142816/`: machine-discovery evidence only. It
  is counted for physical accounting but is never extracted or indexed.

The reviewed inventory accounts for 1,413 physical files. The acceptance run
found 1,414 present files, including 20 Finder metadata files, and
58,965,738,600 bytes. The substantive count is 1,394 files. The only extra
physical file is the unclassified `data/.DS_Store` that was present in the
live tree and is preserved.

## Current acceptance

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
[acceptance summary](work-corpus/corpus/reports/what_we_have_and_need.md).

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
  records its exact executable and model version. The current machine has no
  verified local engine, so 231 eligible items are visibly `blocked`.
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
specification, the ADR, and the README carry the current project context.
