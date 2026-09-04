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
- Normalized text, FTS, reports, and optional embeddings are rebuildable
  outputs outside `data/`.
- The default query scope is `Work`. `Personal`, `Mixed`, and `Unknown` stay
  out of that query.
- Confidential personnel material is allowed in the private work scope and
  retains a sensitivity label.
- Email is completely outside the system.
- Atlas and the legacy bridge are outside the architecture and must not watch,
  move, or synchronize the corpus.
- Existing transcripts are used before local transcription. Media processing
  requires an approved local queue and a local engine.
- Current tasks require explicit commitments and an event or meeting date in
  the previous 14 calendar days at run time or in the future. Historical
  records remain historical.
- Canonical names use exact aliases and regex rules before local model
  proposals. Ambiguous or risky changes require review.

## Consequences

The first useful query path is exact search plus SQLite relationship traversal.
Embeddings are optional and can be rebuilt. Every answer can point to a source
path and locator. Parsing failures and uncertainty remain visible in review
queues.

The first full extraction needs a conservative scope review. Some Zoom media
needs local transcription. Some Capacities attachment payloads are absent.
OneNote conversion depends on a configured local parser. These are visible
processing gates, not reasons to use a cloud service.

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
- A first-class career-claim table: deferred; career evidence is a derived
  view over the canonical evidence.
