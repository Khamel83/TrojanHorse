# Local Work Corpus

A private source-evidence corpus supporting operating memory and career evidence.
Behavior is specified in the design document; execution is tracked in TODO.md.
Historical context is preserved in docs/superpowers/plans/2026-09-06-context-history.md.

## Language

**Raw evidence**: The original local file or provider response. The system never rewrites it.

**Captured**: A provider response is preserved locally. This alone does not establish import or search coverage.

**Imported**: Captured content is represented in the corpus with its source identity and provenance.

**Searchable**: Imported evidence is represented in the query index and can be retrieved through the applicable scope rules.

**Retryable outcome**: An incomplete retrieval or processing attempt that remains eligible for another attempt, such as a provider rate limit.

**Source root**: An explicit directory or archive identity for one source system.

**Source record**: One physical file or provider item in the manifest.

**Source version**: A content-hash version of a source record. A changed file receives a new version.

**Evidence record**: A derived, source-backed unit with a source version and locator.

**Meeting group**: One dated Zoom folder, including nested recording assets.

**Canonical entity**: One stable project, person, or organization record.

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
