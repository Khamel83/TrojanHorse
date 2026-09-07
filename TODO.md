# Local Work Corpus TODO

Reviewed handoff for a clean Luna session. User approved both milestones in this
order. Antigravity Opus 4.6 Thinking approved the supplied plan; its required
index-API clarification is applied. No implementation below is claimed complete.

Read [the plan](docs/superpowers/plans/2026-09-06-corpus-completion-handoff.md)
and [review](docs/superpowers/reviews/2026-09-06-corpus-completion-opus-review.md).
The original completed Tasks 0–9 and historical gates remain documented in
[the original plan](docs/superpowers/plans/2026-09-04-local-work-corpus-implementation.md).

## Milestone 1 — Finish ingestion and verify search

- [ ] 1. Establish one writer: inspect and temporarily pause heartbeat
  `continue-granola-corpus-capture`, preserve its settings, inspect dirty state,
  and make a WAL-consistent SQLite backup before repair. Preserve raw files.
- [ ] 2. Reconcile every saved Granola batch against inventory, imported evidence
  and search. Register missing captures, import, normalize as needed, and rebuild
  with existing Python index APIs. Prove the exact IDs, provenance and content of
  previously missed batches reach the applicable query view. Verify repeat imports
  are idempotent and preserve richer content. See plan step 2 for acceptance.
- [ ] 3. Rebuild progress from exact IDs and persisted outcomes. Correct retry
  double-counting, audit unavailable IDs, retain transient failures for retry and
  track summary-only transcript gaps. Report captured/imported/searchable counts
  separately. Do not trust the old 194/142/363 counters.
- [ ] 4. Repair the existing heartbeat workflow and resume it with at most five
  IDs per run, retries first, provider backoff and inventory before import.
  Finish all listed meetings and requested transcripts or record supported terminal
  outcomes. Delete the automation only on verified completion. A zero metadata
  counter alone is insufficient. No user intervention for routine retries.
- [ ] 5. Match available Capacities payloads to pointer identities; record specific
  unresolved targets. Inspect Wispr date evidence and preserve unknown dates.
  Verify existing OneNote coverage and retain quiet Zoom/artifact terminal outcomes.
  No new exports required; no signed-URL fetches or unnecessary retranscription.
- [ ] 6. Close ingestion milestone with evidence: coverage by exact identity,
  representative query checks including scope exclusions, preserved source hashes,
  retry/terminal accounting, and appropriate regression tests. Report residuals.

## Milestone 2 — Organize the evidence

Start after milestone 1 is verified; resume from persisted checkpoints.

- [ ] 7. Apply existing rules to scope, sensitivity, duplicate/version, date and
  meeting-link queues. Preserve all eligible parseable content. Record reasons and
  evidence for resolved and unresolved items; never force uncertain merges.
- [ ] 8. Populate supported people, projects, organizations and aliases with source
  locators. Use existing entities APIs and minimal resumable orchestration.
- [ ] 9. Populate supported relationships and explicit task proposals through
  existing APIs. Anchor current tasks to runtime's 14-day window or future events;
  keep old commitments historical. Unknown dates remain review items. Zero current
  tasks can be correct. Verify repeat execution does not duplicate derived records.
- [ ] 10. Produce a concrete residual list: source IDs/locators, reason unresolved,
  work the agent attempted, and the smallest user decision needed. Do not present
  every queue entry as a mandatory manual task. Keep sensitive details local.

## Final acceptance and handoff

- [ ] 11. Refresh reports in dependency order and run appropriate tests. Verify
  source preservation, provenance, representative searches and derived links/tasks.
  Historical 152-test results are not validation of new changes.
- [ ] 12. Update README, glossary, status, spec and checklist with verified results.
  Commit scoped code/docs/tests and push under existing user authorization. Verify
  remote commit identity; leave raw data/runtime state outside Git.

## Explicitly deferred features

Email, Atlas integration, cloud raw-data processing, graph/vector infrastructure,
structured decision feature development, automatic historical task backfill and
polished career-document generation remain outside this handoff. Career evidence
continues as a derived use of the same source-backed corpus.

## Start Luna with this

Execute TODO.md and its reviewed completion handoff in order. Finish ingestion and
verify search first, then organize entities, relationships and supported tasks.
Start by controlling the existing heartbeat and verifying saved captures actually
reach inventory, import and search. Complete locally actionable work, document
specific residuals, update docs and verify the authorized push. Read AGENTS.md and
actual CLI/API signatures; preserve unrelated files and raw evidence.
