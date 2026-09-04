# Local Work Corpus Design: Adversarial Review

Review model: Antigravity, Gemini 3.8 Flash, high effort
Review date: 2026-09-04
Review scope: design and inventory-summary documents only

The reviewer was instructed not to open `data/`, the bootstrap directory, or
any archive. No raw work evidence was provided to the reviewer.

## Plan Challenge

### Challenges

- High: Task lookback date anchor (Line 165) — missing constraint — The design assumes the 14-day recency window for current tasks is measured "from the source event date", which would treat any historical task in a 2022–2025 note as current if assigned within 14 days of its historical event date — Anchor the 14-day window strictly to the current date (`source_event_date >= current_date - 14 days`), as mandated by the fixed decision.
- High: Raw evidence search fallback (Lines 252, 257) — missing constraint — The query layer assumes it can fall back to searching raw or unreviewed records when canonical evidence yields no results, ignoring that unclassified raw records contain personal, medical, and trust notes alongside signed URLs — Constrain raw fallback queries strictly to records whose source manifest entry is already classified as `Work`, and strip signed URLs before returning snippets.
- Medium: Legacy Atlas synchronizer code (Line 122) — deletion — The design assumes implementation can build upon the "existing Python and SQLite direction" without addressing existing repository code, ignoring that the existing codebase contains an active text-to-Atlas bridge that monitors and moves files — Delete or quarantine the legacy Atlas bridge sync scripts and file watcher before implementing the local SQLite work corpus.
- Medium: Machine-discovery report inclusion (Lines 54–56, 296–297) — missing constraint — The design assumes every physical file under `data/` belongs in the general raw evidence layer and source manifest, ignoring that `data/note-inventory-20260903-142816/` contains 73,293 machine-scan candidate paths across the disk rather than corpus notes — Add an explicit exclusion rule preventing the note-inventory discovery tree from entering note/document extraction adapters or vector indexing.
- Medium: `career_claim` core entity (Line 96) — simplification — The architecture assumes career claims must be a first-class canonical entity during initial extraction, despite "Deliberately not built" excluding career generators and the inventory defining career evidence as a derived view over operating memory — Defer `career_claim` to a query-time view or tag over canonical documents, projects, and decisions until the core evidence layer stabilizes.
- Low: `evidence_record` schema entity (Line 86–101) — simplification — The canonical layer assumes a standalone `evidence_record` entity is required alongside `relationship` and direct source ID links on canonical records — Consolidate citation offsets and source links into the `relationship` table or canonical provenance fields.
- Low: Zoom `client_config.json` error handling (Line 72) — convention alignment — The extraction layer assumes non-media Zoom files are either captions or standard JSON, causing 22 false-positive parse errors on plist/XML-formatted Zoom client configs — Parse `client_config.*` with a tolerant plist/XML reader or classify it as non-failing configuration metadata.

### Verdict

REVISE — The design must anchor the 14-day task window to the current date, prevent raw fallback queries from bypassing the personal/mixed scope boundary, quarantine legacy Atlas sync code, and exclude machine-discovery logs from note extraction.

## Disposition

The design was revised to apply all material findings. `evidence_record` was
retained because it represents a source-backed assertion with a location and
is not interchangeable with a generic relationship. The revised design is
pending the user's review before an implementation plan is requested.
