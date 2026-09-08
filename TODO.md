# Local Work Corpus TODO

Reviewed handoff for a clean Luna session. User approved both milestones in this
order. Antigravity Opus 4.6 Thinking approved the supplied plan; its required
index-API clarification is applied. The subsequent user-approved unified-corpus
policy pass is also complete: the default query includes all nonblank parseable
sources, original labels remain provenance, and no grouped review rows remain
pending. Checked items below record verified work.
The residual scope is summarized in [Remaining Work After Ingestion](docs/REMAINING_WORK.md).

Read [the plan](docs/superpowers/plans/2026-09-06-corpus-completion-handoff.md)
and [review](docs/superpowers/reviews/2026-09-06-corpus-completion-opus-review.md).
The adaptive throughput amendment is recorded in
[its implementation plan](docs/superpowers/plans/2026-09-06-granola-adaptive-batching.md).
The one-time Granola REST archive gate is now complete; the MCP UUID feed is
retained as a separate shadow diagnostic. Checked items below have current
evidence, and the original completed Tasks 0–9 and historical gates remain documented in
[the original plan](docs/superpowers/plans/2026-09-04-local-work-corpus-implementation.md).

## Milestone 1 — Finish ingestion and verify search

- [x] 1. Establish one writer: inspect and temporarily pause heartbeat
  `continue-granola-corpus-capture`, preserve its settings, inspect dirty state,
  and make a WAL-consistent SQLite backup before repair. Preserve raw files.
  Evidence: the existing automation was inspected; it was no longer present in
  the current automation registry during finalization. SQLite backup
  `work-corpus/state/backups/work_corpus-before-repair-20260907T044105Z.sqlite`
  passes `PRAGMA quick_check`; raw evidence remains in place.
- [x] 2. Reconcile every saved Granola batch against inventory, imported evidence
  and search. The read-only REST backfill registered one 559-note capture,
  imported all 559 API IDs, and indexed them. Two successful repeat imports
  returned identical `items=1324`, `updated_items=1324`, `source_files=41`,
  `malformed=0`, and `errors=0` results. See
  `work-corpus/state/granola_acceptance.json` for the source/evidence/query
  ledger.
- [x] 3. Rebuild progress from exact IDs and persisted outcomes. The checkpoint
  now separates MCP UUID capture/import/search sets from the REST API's 559
  unique `not_...` IDs, reports the two summary-only API notes, and retains
  retry/rate-limit accounting. The old 194/142/363 counters are not used.
- [x] 4. Use the read-only REST API for the one-time archive instead of waiting
  on the historical heartbeat. It fetched all 559 API-listed notes across 19
  pages; 559 summaries and 557 transcripts are preserved, imported, and
  searchable. The two API notes with empty transcript arrays remain preserved as
  explicit summary-only records. The tested MCP ten-ID/five-ID adaptive policy
  remains documented for an optional future shadow refresh; no recurring
  heartbeat was recreated for duplicate historical calls.
- [x] 5. Match available Capacities payloads to pointer identities; record specific
  unresolved targets. Repair Wispr date-field mapping and preserve only genuinely
  missing event dates.
  Verify existing OneNote coverage and retain quiet Zoom/artifact terminal outcomes.
  No new exports required; no signed-URL fetches or unnecessary retranscription.
  Evidence: 563 typed pointers, 557 matched pointers, 451 local payload targets,
  1,216 confirmed payload relationships, and 6 explicit `pointer_missing_file_size`
  reviews. Wispr has 13/13 local capture and retrieval dates, all 12 meeting
  start/end/provider-modified dates, and the scratchpad's provider-modified
  date; the scratchpad has no event date in its source object;
  OneNote is 29/29 files and 295/295 pages; Zoom has 230 succeeded and 1
  partial terminal result with 0 eligible media lacking terminal status.
- [x] 6. Close ingestion milestone with evidence: exact Granola REST identity
  coverage, representative unified-All and Work-scope query checks, preserved source hashes,
  retry/terminal accounting, and regression tests. The residual interpretation
  and organization work is documented in `docs/REMAINING_WORK.md`.

## Milestone 2 — Organize the evidence

Start after milestone 1 is verified; resume from persisted checkpoints.

- [x] 7. Apply existing rules to scope, sensitivity, duplicate/version, date and
  meeting-link queues, then apply the safe first-pass defaults. Preserve all
  eligible parseable content. Record reasons and evidence for resolved and
  unresolved items; never force uncertain merges.
  Evidence: the organizer saw 443 scope, 1,396 sensitivity, 312 duplicate,
  310 version, 1,561 task-date, 350 task-scope, 52 meeting-link, 0 current
  Wispr-date, and 1 Zoom-quality candidates. The first pass resolved 4,411
  policy-stable rows, selected 622 provisional display records, and left 68
  grouped exceptions: 6 payload, 48 entity, 4 scope, 9 sensitivity, and 1 Zoom
  quality. The approved first pass then resolved all 68 grouped rows, retained
  six payload gaps as unresolved metadata, recorded 48 generic topic labels,
  included the scope/sensitivity records in the unified private query, and
  accepted the one partial Zoom result. The old 13 Wispr-date rows were
  superseded after the field mapping repair; no ambiguous canonical identity
  was forced.
- [x] 8. Populate supported people, projects, organizations and aliases with source
  locators. Use existing entities APIs and minimal resumable orchestration.
  Evidence: 9 explicit Project entities, 9 aliases, and 27 evidence-backed
  project source links were created. No people or organizations were promoted
  without a safe canonical alias; 48 titles are recorded as generic topic labels
  in `first_pass_topic_labels.csv` rather than promoted to entities.
- [x] 9. Populate supported relationships and explicit task proposals through
  existing APIs. Anchor current tasks to runtime's 14-day window or future events;
  keep old commitments historical. Unknown dates remain review items. Zero current
  tasks can be correct. Verify repeat execution does not duplicate derived records.
  Evidence: 1,910 evidence records were scanned; task rows and current task rows
  remain 0. Two same-date organizer runs retained 1,243 relationship rows and
  identical entity/review counts.
- [x] 10. Produce a concrete residual list: source IDs/locators, reason unresolved,
  work the agent attempted, and the smallest user decision needed. Do not present
  every queue entry as a mandatory manual task. Keep sensitive details local.
  Evidence: `work-corpus/state/residual_ledger.json` and
  `work-corpus/corpus/reports/residual_ledger.csv` contain 0 pending entries;
  the first-pass response sheet is an empty exception sheet. Bounded accepted
  topic labels are in `work-corpus/corpus/reports/first_pass_topic_labels.csv`.

## Final acceptance and handoff

- [x] 11. Refresh reports in dependency order and run appropriate tests. Verify
  source preservation, provenance, representative searches and derived links/tasks.
  Historical 152-test results are not validation of new changes. Evidence: the
  current report is generated after organization and first-pass triage, both
  indexes are fresh (72,138 FTS rows and 1,243 relationship rows), the
  historical raw-immutability comparison remains passed, representative
  Work-scope query checks remain recorded, the default All-scope and explicit
  Work-scope query checks remain recorded, and the active 181-test suite is
  run as part of final acceptance.
- [x] 12. Update README, glossary, status, spec and checklist with verified results.
  Commit scoped code/docs/tests and push under existing user authorization. Verify
  remote commit identity; leave raw data/runtime state outside Git.
  Evidence: README, CONTEXT.md, the design checkpoint, status, remaining-work
  map, and this checklist record the 2026-09-07 results. The completion commit
  contains only the scoped code/docs/tests; raw data and unrelated untracked
  files remain outside Git. Remote identity is verified after push.

## Full-scale repository audit — 2026-09-07

This audit separates the captured evidence archive from the unfinished product
and operations layers. It does not require the owner to inspect the 1,500-plus
review rows one by one; the approved first pass already handled those queues.
See [the full audit](docs/TROJAN_HORSE_AUDIT.md) for evidence, findings, and
the completion path.

- [x] Reconcile live SQLite counts with the generated report: 2,751 source
  records/source versions, 1,849 normalization records, 72,139 evidence rows,
  72,138 FTS rows, 1,243 relationships, and 0 pending review rows.
- [x] Separate the complete Granola REST archive from the incomplete but
  redundant MCP shadow: 559 REST notes imported/searchable, 559 summaries, 557
  transcripts, 2 summary-only notes.
- [x] Verify the captured-provider and local-transcription boundary: 13 Wispr
  records imported/searchable, 231 Zoom groups, 230 succeeded, 1 partial, and
  0 eligible final media without a transcript or terminal status.
- [x] Correct report terminology so source versions and normalization records
  are separate metrics; mark the saved raw-immutability proof as historical
  because it covers 1,414 files rather than the current 2,751-file inventory.
- [x] Record the repository-level status: active `work-corpus/` tests pass;
  the root legacy package/test runner, production configuration, scheduler,
  health checks, and answer-synthesis product are not complete.
- [ ] Make `work-corpus/` the single supported entry point and retire,
  quarantine, or explicitly rebuild the legacy `TrojanHorse/`, `th`, and Atlas
  bridge lane.
- [ ] Add reproducible installation, optional-parser dependencies, CI, a
  repository-wide test command, and a safe runtime/doctor check.
- [ ] Run a fresh raw-preservation verification over the current 2,751-file
  inventory and decide how to handle the 20 already-local `.eml` files and 49
  non-final Zoom `.zoom`/`.tmp` artifacts.
- [ ] Build the source-backed project, task, and career evidence views. The
  current scan covered 1,910 evidence records but produced 0 task rows; this
  is a missing downstream deliverable, not proof that raw evidence is absent.
- [ ] Add a scheduled Granola delta path and monitoring after choosing the
  operational host. The one-time REST archive is complete; a five-minute loop
  is not currently configured or required by the archive gate.
- [ ] Optionally refine generic topic labels, canonical people/organization
  aliases, and retained Zoom linkage states after the core views are usable.

### Owner input required to finish the product

1. Confirm that the active product is the private local `work-corpus/` path and
   that the old Atlas/RAG service is retired or quarantined.
2. Decide whether the 20 `.eml` files already inside the local corpus should be
   parsed locally and included in `All`, or intentionally remain inventory-only.
   This question is about existing files, not mailbox access.
3. Choose the first user-facing output to build: searchable evidence, a current
   task view, project history, career evidence, or a small local assistant over
   those views. No item-by-item queue review is required.
4. Choose manual maintenance versus scheduled Granola delta ingestion. If
   scheduled, the remaining input is the approved host/service location; the
   Granola secret is already held outside this checkout.

## Explicitly deferred features

Mailbox access, Atlas integration, cloud raw-data processing, graph/vector infrastructure,
structured decision feature development, automatic historical task backfill and
polished career-document generation remain outside this handoff. Career evidence
continues as a derived use of the same source-backed corpus.

## Start Luna with this

Execute TODO.md and its reviewed completion handoff in order. Finish ingestion and
verify search first, then organize entities, relationships and supported tasks.
Start by controlling the existing heartbeat and verifying saved captures actually
reach inventory, import and search. Complete locally actionable work, apply the
approved unified-corpus first pass, update docs, and verify the authorized push.
Read AGENTS.md and actual CLI/API signatures; preserve unrelated files and raw
evidence.
