# ADR 0001: Local Work Corpus Boundary

- Status: Accepted
- Date: 2026-09-04
- Scope: private, single-user work corpus

## Context

The repository contains an older Atlas bridge and a new local data archive.
The archive contains work notes, meetings, formal records, attachments,
OneNote sections, and Zoom media. It also contains personal and mixed records.
The project needs one trustworthy corpus with source-backed answers, while the
raw archive must remain unchanged.

The user wants this project to remain separate from Atlas and email. The
corpus must support historical work evidence, current commitments, canonical
project and person names, and future local Wispr Flow and Granola inputs.

## Decision

Build a local-only, single-user work corpus in the promoted `work-corpus/`
package.

- `data/` is immutable raw evidence.
- SQLite stores the manifest, source versions, provenance, evidence, entities,
  relationships, review items, task records, and ingestion checkpoints.
- Normalized text, FTS, reports, and relationships are rebuildable outputs
  outside `data/`.
- The default query scope is `Work`. `Personal`, `Mixed`, and `Unknown` stay
  out of that query.
- Confidential personnel material is allowed in the private work scope and
  retains a sensitivity label.
- Email is completely outside the system.
- Atlas and the legacy bridge are outside the architecture and must not watch,
  move, or synchronize the corpus.
- Existing transcripts are used before local transcription. Every final Zoom
  MP4 or M4A without a usable transcript enters the local queue.
- Media processing requires one run-level approval and a local engine. The
  runner processes one item at a time and saves a checkpoint after each item.
- The coverage run records a terminal status for every eligible media item.
  Failed, partial, blocked, and artifact items remain visible.
- Current tasks require explicit commitments and an event or meeting date in
  the previous 14 calendar days at run time or in the future. Historical
  records remain historical.
- Canonical names use exact aliases and regex rules before local model
  proposals. Ambiguous or risky changes require review.

## Implementation evidence

The 2026-09-04 acceptance run preserved the boundary: the raw corpus had
1,414 files and 58,965,738,600 bytes before and after the run, with zero
path, size, modification-time, or content-hash mismatches. The local runtime
recorded 231 eligible Zoom media items as terminal `blocked` because no
verified local transcription engine was available, and it recorded all 29
OneNote files as `blocked` because no local converter was available. No cloud,
email, Atlas, or live MCP path was used.

## Consequences

The first useful query path is exact search plus SQLite relationship traversal.
Embeddings are optional and can be rebuilt. Every answer can point to a source
path and locator. Parsing failures and uncertainty remain visible in review
queues.

The first run uses a conservative preflight scope review. It then performs
full local extraction and full eligible Zoom transcription coverage. Some Zoom
media can fail or remain an artifact. Some Capacities attachment payloads are
absent. OneNote conversion depends on a configured local parser. These are
visible processing states, not reasons to use a cloud service.

The old root package and Atlas bridge remain historical code until a separate
cleanup decision. The new runtime does not import them.

## Rejected alternatives

- Atlas as the storage or query layer: rejected because this project is
  separate and local-only.
- Email access: rejected for the current scope.
- Cloud transcription or external model calls with raw evidence: rejected for
  privacy and local-boundary reasons.
- Moving or rewriting raw files: rejected because source evidence must remain
  immutable.
- A separate graph database: deferred until SQLite relationship queries prove
  insufficient.
- An embedding index during initial corpus assembly: deferred until exact
  search and SQLite relationships prove insufficient.
- A first-class career-claim table: deferred; career evidence is a derived
  view over the canonical evidence.
