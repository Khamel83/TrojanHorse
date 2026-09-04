# Local Work Corpus TODO

Status: final implementation plan reviewed; implementation not started.

Authoritative plan: [docs/superpowers/plans/2026-09-04-local-work-corpus-implementation.md](docs/superpowers/plans/2026-09-04-local-work-corpus-implementation.md)

## Completed foundation

- [x] Inventory the raw `data/` tree without changing it.
- [x] Separate Capacities, Notion, OneNote, Zoom, formal records, and discovery evidence.
- [x] Test the local OneNote conversion route against all 29 files and 295 pages.
- [x] Define the local-only, single-user, no-email, no-Atlas boundary.
- [x] Complete Antigravity/Gemini 3.8 Flash adversarial design review.
- [x] Complete Gemini 3.1 Pro adversarial implementation-plan review.
- [x] Document the domain context and boundary ADR.

## Implementation sequence

- [ ] Task 0 — Promote the reviewed `work-corpus/` scaffold. Exclude email code, Outlook scripts, `.pyc` files, and raw data.
- [ ] Task 1 — Lock the local boundary and package entry point.
- [ ] Task 2 — Build the complete immutable manifest and explicit source registry.
- [ ] Task 3 — Replace the bootstrap schema with the provenance model.
- [ ] Task 4 — Implement safe extraction adapters for text, Office files, Notion, Capacities, OneNote, and formal records.
- [ ] Task 5 — Correct Zoom meeting grouping and build the approved local transcription queue.
- [ ] Task 6 — Add canonical project, person, and organization names, aliases, scope review, and current-task rules.
- [ ] Task 7 — Implement Work-only local query, evidence labels, redaction, FTS, relationships, and optional rebuildable embeddings.
- [ ] Task 8 — Add local Wispr Flow and Granola snapshot intake with idempotent checkpoints.
- [ ] Task 9 — Run the safe batch, complete reports, verify raw immutability, and update operational docs.

## Required gates

- [ ] No Atlas bridge or launch service watches `data/`.
- [ ] Raw paths, sizes, modification times, and hashes remain unchanged after every run.
- [ ] The default query never returns Personal, Mixed, or Unknown records.
- [ ] Current tasks use only explicit commitments with an event/meeting date in the previous 14 calendar days at run time or in the future.
- [ ] Existing transcripts are linked before any local transcription.
- [ ] The local OneNote converter is available and fails closed when absent.
- [ ] Parser failures, missing attachments, uncertain merges, conflicts, and scope decisions remain visible in review records.
- [ ] No email access, cloud transcription, external raw-data model call, raw-file movement, or raw-file deletion is introduced.

## Intentionally deferred

- Email integration.
- Atlas integration.
- Automatic historical task backfill.
- A separate graph database.
- A first-class career-claim table or polished career document generator.
