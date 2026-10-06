# Professional package intake handoff — 2026-10-05

## Done and verified

Fetched `origin/main` at `d041b1bd91931e8d3cd0980e2de3d0baabc2cf2f` and created
isolated branch `evidence/professional-package-intake-20261005`. The primary
checkout's pre-existing dirty work was preserved. This branch changes the source
root configuration and documentation; it does not change parser or query code.

Found the supplied folder at
`/Users/macmini/Library/Mobile Documents/com~apple~CloudDocs/Omar_Complete_Package_2026-10-05_H002`.
Copied all 116 files into the canonical TrojanHorse data directory and independently
verified all hashes against the original and package manifest. H001/H002 frozen
exports are byte-identical to the existing exports, not new historical events.

Canonical local runtime: 116 new source/version records, 108 normalized documents,
282 additional evidence records, 35 project entities. All 35 card definitions are
retrievable and 20 H001 candidate aliases resolve through the supplied crosswalk.
The combined historical ledger remains 230 rows. Five ZIPs remain inventory-only;
CSS and two Python files are retained without text extraction or execution.
Previous evidence IDs and 3,188 derived-file hashes are unchanged. Tasks remain zero.

Private durable receipts and the pre-import SQLite backup:
`/Volumes/2TB_SSD/GitHub/TrojanHorse/work-corpus/corpus/reports/professional-package-intake-20261005/`.
Use `IMPORT_RECEIPT.json`, `INTAKE_MANIFEST.json` and `FINAL_VERIFICATION.json`.
The canonical ignored local config and tracked default source root both identify
`professional_package`. Captured package publication/Drive/scheduler claims were
not independently verified or activated. No external publication or communication
occurred. This branch is local and unpushed; local corpus intake is already effective.

## Current work second-brain direction

Owner clarification supersedes the prior professional-memory-first gate. The
product continuously consumes Wispr meetings and pasted email/Slack, maintains
people/projects and own/delegated tasks, and reconciles completion into Reminders.
Explicit owner “done” is accepted immediately; open tasks never silently age out.
The owner subsequently narrowed the first release: Reminders plus paste input,
no dashboard/project web views. A later clear outstanding-work contradiction
returns the same completed task as Evidence needed. Matching confirmation clears
it. Completion confirmation never assesses quality.
Read `docs/WORK_SECOND_BRAIN.md` for the contract and ordered acceptance sequence.

Current source branch: `feature/work-second-brain`, isolated from the dirty primary
checkout, starts from fetched main and includes the prior package-intake commit.
No push, production deployment or native list mutation occurred.

Read-only native probe/list discovery resolved Maya — Mine and Maya — Delegated
in iCloud: five reminders, all completed. IDs and caller receipts are private under
this worktree's ignored `private-review/`. No open backlog was inferred. The existing
Wispr capture importer is reusable, but no scheduled Wispr runner is established;
zero person entities means the colleague directory still needs identity resolution.
The infrastructure catalog declares no TrojanHorse runtime host or Cloudflare app.

Verified first implementation: `work-corpus/src/work_corpus/work_state.py` retains
provenance-bearing events and projects own/delegated task state. Owner completion
and reopening are explicit; stale replay cannot resurrect finished work, retries
deduplicate, open work does not expire, ambiguous terminal events remain review.
36 new plus 10 existing task tests pass; focused Ruff and diff checks pass.
The new outstanding/confirmed events implement done -> evidence needed -> done,
including an older email supplied as new confirmation. The source date is retained
separately; old-source replay and mere repeated assignments cannot reopen work. This
is an API requiring trusted validated input, not text extraction or a running inbox.
It was not initialized against the live database.

Native discovery receipts are durably copied into the canonical ignored report
`work-corpus/corpus/reports/work-brain-definition-20261005/`.

Next verification: wire a durable paste source and live Wispr intake into
structured, source-cited events and exercise the assignment/checkbox/contradiction/
pasted-confirmation cycle on one task. Reminders is the only required task UI.
Do not rerun historical extraction. After local workflow validation, bind and
verify the installed Mac Reminders caller and migrate exact Maya list ownership
without losing history or running competing writers. Prepare the Pages/Access
paste-only release as a concrete reviewable change before any production approval
gate. No dashboard is required. No native list mutations occurred in this update.

The prior unrelated managed-rule repair gates remain archived in
`docs/handoffs/2026-10-05-managed-rule-repair-before-package-intake.md`.
