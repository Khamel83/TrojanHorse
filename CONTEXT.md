# Local Work Corpus

A private source-evidence corpus supporting operating memory and career evidence.
Behavior is specified in the design document; execution is tracked in TODO.md.
Historical context is preserved in docs/superpowers/plans/2026-09-06-context-history.md.

The current operational checkpoint is recorded in
`docs/LOCAL_WORK_CORPUS_STATUS.md` and `docs/REMAINING_WORK.md`. Ingestion,
deterministic organization, and the approved unified-corpus first pass are
complete for the captured local sources. Optional semantic refinement remains
a separate downstream step.

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

**Current task**: An explicit commitment from a future event or an event/meeting dated within the previous 14 calendar days at run time.

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
