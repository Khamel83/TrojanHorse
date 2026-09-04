# Local Work Corpus Context

Status: Design and implementation plan approved. Implementation has not
started.

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
| Derived view | A rebuildable presentation of source-backed records, not a new source of truth. |

## Source map

- `data/Zoom/`: 276 dated meeting folders. Existing captions and transcripts
  are preferred. Final media without a usable transcript may enter a later
  local transcription queue.
- `data/notes/Notes/`: Capacities Markdown and category export.
- `data/notes/40b7a161-92e3-450d-8dab-c2bb4a080adf_ExportBlock-7045c812-ccf8-4b28-b774-5502ee6696b2/`:
  Notion ExportBlock with LifeOS databases and local attachments.
- `data/notes/Backup/`: 29 OneNote section files. A local parser test
  extracted 295 pages; integration and semantic review remain planned work.
- Formal local records: PDFs, Office files, tables, and related work
  documents identified by the inventory.
- `data/note-inventory-20260903-142816/`: machine-discovery evidence only. It
  is counted for physical accounting but is never extracted or indexed.

The reviewed inventory accounts for 1,413 physical files, including 19 Finder
metadata files, and about 54.9 GB. The substantive count is 1,394 files.

## Rules

- Default queries include only `Work` records.
- `Personal`, `Mixed`, and `Unknown` records remain inventoried but stay out
  of the default query until a review resolves their scope.
- Confidential personnel and performance material is work-scoped for this
  single user and keeps a sensitivity label.
- Exact aliases and regex rules run before local model proposals. The most
  common valid spelling is selected. Ambiguous or risky merges require review.
- Old records remain historical. They do not create a current task backlog.
- Export, file-modification, and transcription dates do not make old evidence
  current.
- Raw or unreviewed fallback search is limited to already work-classified
  records. Returned snippets redact URL-like and secret-like values.
- Normalized text, SQLite state, FTS, relationships, and optional embeddings
  live outside `data/`.
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
