# Local Work Corpus

## Current product authority — 2026-10-05

TrojanHorse is Omar's work second brain: automatic intake of live meetings plus
pasted email/Slack, continuously maintained projects, people, own/delegated tasks
and completion confirmation, projected into Apple Reminders. Explicit owner
“done” is accepted immediately. A later explicit statement that the same work is
still outstanding returns it as Evidence needed; matching pasted confirmation
clears it. This does not assess quality. The first release has no dashboard or
separate web project/people views: Reminders plus a simple paste input.
Open tasks do not expire after fourteen days. Historical
proposals remain distinct from the new live-task event projection.
[WORK_SECOND_BRAIN.md](docs/WORK_SECOND_BRAIN.md) owns the current product contract.
Question-based memory is secondary; the provisional prior plan is superseded.

The complete professional package remains imported privately: 116 files, 108
normalized documents, 35 retrievable project definitions, 20 H001 candidate aliases
and a retained 230-row historical ledger. Prior evidence/derived files are preserved.
Receipts remain in `work-corpus/corpus/reports/professional-package-intake-20261005/`.
Package derivatives do not constitute new underlying historical events.

Read-only runtime inspection found 13 captured Wispr items, 1,118 Granola items,
44 project entities, zero person entities and zero historical task rows. Names in
source text are not a completed identity directory. Wispr snapshot import exists
but no automatic Wispr delta runner is established. The native Reminders lists
Maya — Mine and Maya — Delegated resolve in iCloud; all five existing reminders
are completed. Exact IDs/probe receipts are private. No list changes were performed.
Shell reachability does not prove unattended caller permission.

The infrastructure catalog has no declared TrojanHorse runtime host. No Cloudflare
Pages/Access app, private context service or Reminders bridge was deployed. The
new deterministic event reducer is an isolated first slice, not a running inbox.
Its 36 tests and 10 existing task tests pass; focused Ruff/diff checks pass.
The new outstanding/confirmed events support the confirmation cycle while
keeping original message time separate from the later confirmation time.
The API creates only namespaced work_* tables when explicitly initialized; no
live database migration or provider writes were performed.
The primary dirty checkout and live corpus remain preserved. Source changes are
in isolated `feature/work-second-brain`, local and unpushed.

## Language

**Raw evidence**: The original local file or provider response. The system never rewrites it.

**Captured**: A provider response is preserved locally. This alone does not establish import or search coverage.

**Imported**: Captured content is represented in the corpus with its source identity and provenance.

**Searchable**: Imported evidence is represented in the query index and can be retrieved through the applicable scope rules.

**Unified private corpus**: The default `All` query scope includes every
nonblank parseable source record. The original Work, Personal, Mixed, and
Unknown labels remain attached as provenance. `Work` is an explicit narrower
filter.

**Retryable outcome**: An incomplete retrieval or processing attempt that remains eligible for another attempt, such as a provider rate limit.

**Source root**: An explicit directory or archive identity for one source system.

**Source record**: One physical file or provider item in the manifest.

**Source version**: A content-hash version of a source record. A changed file receives a new version.

**Evidence record**: A derived, source-backed unit with a source version and locator.

**Meeting group**: One dated Zoom folder, including nested recording assets.

**Canonical entity**: One stable project, person, or organization record.

**Generic topic label**: A source title retained for grouping and search when
it does not establish a person, project, or organization identity.

**Alias**: A former name, spelling, abbreviation, or source-specific name linked to a canonical entity.

**Review item**: An uncertain parse, classification, merge, date, task, or relationship proposal.

**Historical current-task proposal**: The legacy extractor applies a fourteen-day event-date window. This is not the new live-task lifetime rule. A live task stays open until completed, cancelled or explicitly superseded.

**Coverage run**: A resumable local pass that accounts for every eligible final Zoom media item.

**Derived view**: A rebuildable presentation of source-backed records, not a new source of truth.

**Granola progress checkpoint**: Derived state that reconciles exact listed,
captured, detailed, transcript, retryable, terminal, imported, and searchable
meeting-ID sets. It is not a manual retrieval cursor.

**Granola capture batch**: One append-only local capture pass. A clean pass can
request up to ten detail IDs because that is the connected endpoint limit.
Transcript retrieval remains one ID per request. An explicit rate-limit outcome
uses a five-ID recovery batch on the next pass.

**Granola REST archive**: A read-only backfill from Granola's public API. It
pages up to thirty notes at a time, fetches each note and transcript, and
preserves the API `not_...` identity in a local raw capture. REST coverage is
reported separately from MCP UUID coverage because the two interfaces expose
different provider identifiers.

**Granola delta run**: A read-only maintenance pass using the REST
`updated_after` filter. It captures changed notes locally, reruns the local
stages, and advances an overlap watermark only after those stages succeed.

**Email-header date**: A date parsed from an `.eml` `Date` header. It is a
source-backed observation and is kept separate from a filename or inventory
path date.

Mailbox discovery and mailbox access remain outside scope. An `.eml` file that
already exists under the immutable local `data/` tree is not mailbox access;
the active runtime parses it as a captured source record.

**Organization pass**: A local deterministic pass that reconciles available
payloads, applies existing scope/sensitivity/date rules, creates only explicit
source-backed entities and relationships, records task proposals, and writes a
residual review ledger. It does not make human privacy, identity, merge, or
current-task decisions.

**First-pass triage**: A follow-on local pass that applies the existing safe
defaults to policy-stable review queues and writes one grouped exception sheet.
The current approved policy includes all nonblank parseable records in the
unified private corpus, retains original scope and sensitivity labels as
provenance, selects provisional display records, and records ambiguous titles
as generic topic labels. It does not delete sources or invent canonical
identities.

**Wispr capture date**: The date on the saved local capture envelope. It is
separate from a Wispr meeting event date. The importer maps `meetings[].start`
to the event date and the envelope `captured_at` to local capture and retrieval
dates. It preserves `end` and `modified_at` as separate derived metadata fields
and does not treat `modified_at` as an event date.

**Residual ledger**: A rebuildable list of pending review items. Each entry
identifies the source and locator when available, states the bounded reason,
records the work attempted, and names the smallest human decision needed. It
does not replace raw evidence or copy raw sensitive text.

**Project source link**: A confirmed relationship from an explicit non-generic
Capacities `Project` record to a source-backed evidence record. A filename or
free-text mention alone does not create this link.
<!-- janitor:begin:recent -->
## Recent

As of source commit `0fdece42c4f3440cdcc13b55c0e03887617d27bf`, the Local Work
Corpus stands as recorded in the remote TODO: ingestion, exact search,
deterministic organization, and the canonical Mac Granola delta maintenance
path were complete at delivered commit
`b8f08ad92ab8b95de7e2a5cc48947b5857a53237`; the acceptance checkpoint reported
that `origin/main` matched that commit, a receipt from that point rather than a
freshly measured identity for `0fdece4`.

Milestone 3 — Local answer synthesis and evaluation is delivered in the
pushed `main` history. The implementation commit is
`4e9da4a3864ce158171e0f7330dbde69d6a7ad97`; the final documentation and remote
SHA are verified by the completion handoff. The recent commit summaries record
past activity hardening the local answer evaluation boundary: evaluation
metrics, rejected-citation-ID preservation, read-only answer orchestration,
completion backends, backend trust boundaries, WAL-sidecar fail-closed
behavior, prompt/SQLite-view compatibility, and packet/path redaction,
culminating in docs receipts for the final runtime validation and the answer
milestone/boundary verification. The post-merge bounded maintenance poll exited
0 with no raw capture append and no local stage rebuild; the final main-check
reran the active suite (`283 passed`), Ruff, compilation, plist lint, and diff
checks, then answered one bounded existing-corpus question with three
source/version citations while the database snapshot stayed unchanged. These
are receipts, not freshly measured totals.

Open Milestone 3 work remains a downstream product edge, not an ingestion
gate: manually inspect a broader representative evaluation set before relying
on synthesis for consequential decisions; optionally refine the 48 generic
topic labels, canonical people/organization aliases, and 52 retained Zoom
linkage states after the core views are used; and consider semantic ranking
only as a later optional refinement under the same local-data boundary.
<!-- janitor:end:recent -->
