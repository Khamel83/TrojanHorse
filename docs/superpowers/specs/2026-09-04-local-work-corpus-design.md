# Local Work Corpus Design

Status: Draft for adversarial review

## Goal

Build a local, single-user work assistant that answers questions from historical work evidence and current or future Wispr Flow and Granola records.

The system must preserve source evidence, organize it by project, person, date, and event, and return answers with source links and evidence status.

## User decisions

- TrojanHorse is independent from Atlas.
- Atlas is not part of the architecture, storage, query path, or implementation plan.
- Email is outside the system.
- The system is local and single-user.
- The default query scope is work material.
- Personal and mixed personal-work records remain in the raw inventory but stay outside the work query.
- All work material is available to the user, including confidential personnel records.
- Clear names, aliases, merges, and links may apply automatically.
- Uncertain changes go to a review queue.
- A renamed project remains one project with aliases and name history.
- People and organizations use canonical records with aliases and history.
- Historical records do not create a current task backlog.
- Clear tasks may come from future records and from the previous 14 days.
- Older task candidates remain historical evidence unless the user requests a backfill.

## Definitions

- **Raw evidence:** The original files and source responses. Raw evidence is never rewritten by the system.
- **Source record:** A record that identifies one raw file, source response, or export item.
- **Evidence record:** A derived record that points to a source location and states what the source supports.
- **Canonical entity:** One stable record for a project, person, or organization.
- **Alias:** An alternate spelling, abbreviation, former name, or source-specific name for a canonical entity.
- **Review item:** A proposed interpretation that requires a decision before it changes canonical data.
- **Current task:** A clear assignment, promise, deliverable, or follow-up from a future source or a source dated within the previous 14 days.

## System boundary

The system reads local historical files and user-authorized local Wispr Flow and Granola outputs.

The system does not send raw work evidence to a web service, Atlas, an external model, or an external transcription service.

The system does not read, import, send, modify, archive, label, or delete email.

The system does not modify raw files or write back to Wispr Flow or Granola.

## Architecture

The system has four layers.

### 1. Raw evidence layer

The existing `data/` tree is the raw evidence layer.

The system records every physical file in a source manifest. The manifest stores a stable source ID, relative path, source system, file type, size, hash when safe, dates, scope, sensitivity, and processing status.

The system keeps raw files in place. Derived output uses separate paths.

### 2. Extraction layer

Source adapters convert readable source material into derived records.

Each derived record stores its source ID and its location within the source.

The extraction layer keeps the original source format visible. A page, slide, sheet, transcript segment, or audio timestamp must remain locatable.

The first source adapters are:

| Source | Current evidence | Extraction behavior |
|---|---|---|
| Zoom | 276 dated meeting folders; MP4, M4A, VTT, TXT, `.zoom`, and `.tmp` files | Treat the dated folder as the meeting. Link existing captions first. Transcribe approved final media locally when no usable transcript exists. Hold `.tmp` and unvalidated `.zoom` parts. |
| Capacities | 421 Markdown records, 3 category CSV files, and a matching ZIP | Parse Markdown and CSV records. Preserve pointer-only attachment records. Do not fetch signed URLs. |
| Notion | `LifeOS` ExportBlock with HTML, database CSV files, transcripts, and attachments | Parse HTML and CSV database exports. Link local attachments. Preserve page and database identity. |
| OneNote | 29 `.one` section files | Use the tested local parser route. Write Markdown or HTML as derived output. Keep the `.one` files as source evidence. |
| Formal records | PDF, DOCX, PPTX, XLSX, and CSV files | Extract text, pages, slides, tables, and sheet information. Preserve document locations. |
| Wispr Flow | No export in the current snapshot | Accept future user-authorized local records as incremental source records. |
| Granola | No export in the current snapshot | Accept future user-authorized local records or MCP responses as incremental source records. |

The Notion ExportBlock and Capacities export are separate source systems. The source registry must identify them by explicit root path, not by filename heuristics.

### 3. Canonical evidence layer

The canonical layer stores source-backed entities and relationships.

Core records are:

- `source_record`
- `document`
- `meeting`
- `project`
- `person`
- `organization`
- `decision`
- `task`
- `career_claim`
- `evidence_record`
- `review_item`
- `relationship`

Every canonical record has a stable ID and links to one or more source records.

The canonical layer distinguishes:

- Event date from export date.
- Source fact from model inference.
- Current status from historical status.
- User ownership from team participation.
- A duplicate from a related version.
- A conflict from a missing value.

### 4. Query layer

The query layer uses three local retrieval methods:

1. Exact search for names, dates, identifiers, and terms.
2. Local embeddings for meaning-based search.
3. Relationship traversal for projects, people, organizations, meetings, decisions, and tasks.

The canonical evidence layer is the source of truth. Search indexes and embeddings are rebuildable outputs.

The first implementation should use the existing Python and SQLite direction. A separate graph database is not required. Relationships can be stored in SQLite and exposed as a graph view.

## Canonical naming

The system uses one canonical record for each project, person, and organization.

Each record stores:

- Canonical display name.
- Known aliases.
- Source-specific names.
- Former names.
- Effective dates when known.
- Evidence for each name relationship.
- Confidence and review status.

The naming pipeline applies rules in this order:

1. Exact alias matches.
2. Regex and spelling normalization.
3. Source-specific identifiers.
4. Model grouping of similar names.
5. Selection of the most common valid spelling.
6. Review of ambiguous matches.

The system preserves every original mention. A frequent typo does not become canonical when a valid name is available.

The system must keep two people separate when names collide. It uses role, organization, dates, meeting participants, and source context to disambiguate them.

## Date and task behavior

Every source can have several dates. The system stores each date with its basis.

Possible date bases include:

- Event date.
- Meeting date.
- Page creation date.
- Page update date.
- File modification date.
- Export date.
- Transcription date.

The current task view uses a 14-day lookback from the source event date.

The system creates or updates a task only when the source contains an explicit assignment, promise, deliverable, or follow-up.

The system does not create current tasks from old notes. It may keep those statements as historical commitments or evidence.

Wispr Flow and Granola can create current task candidates from new records. Clear candidates may apply automatically. Uncertain candidates become review items.

## Transcription behavior

The system prefers existing local VTT and TXT transcripts over new transcription.

When no usable transcript exists, the system may process approved final MP4 or M4A media with a local transcription tool.

Each derived transcript stores:

- Source meeting ID.
- Source media ID.
- Local tool and model version.
- Run date.
- Language.
- Timestamp coverage.
- Speaker label status.
- Quality status.

Raw audio and video remain unchanged. A failed or partial transcription remains visible as a failed or partial result.

The system must not treat a transcript as a confirmed fact when the transcript has poor quality, missing speakers, or unresolved meeting matching.

## Scope and sensitivity

The raw inventory may contain work, personal, and mixed records.

The work corpus includes work records, including high-sensitivity personnel and performance records.

Personal and mixed records remain inventoried but do not enter the default work query.

Each derived record has a scope classification:

- Work.
- Personal.
- Mixed.
- Unknown.

Unknown and mixed records stay outside the default work query until classification resolves them.

Private signed URLs are treated as sensitive metadata. The system does not fetch or copy them into derived records.

## Review queues

The system uses review items for unresolved interpretation.

Review queues cover:

- Source parsing failures.
- Missing attachment payloads.
- Transcript quality.
- Meeting matching.
- Project and person identity matching.
- Duplicate and version relationships.
- Conflicting facts.
- Date interpretation.
- Work, personal, and mixed scope.

Each review item records the source IDs, proposed result, reason, confidence, and resolution.

Review is not required for every clear normalization. Review is required when an automatic change could merge different entities, expose personal material, create an unclear current task, or change a source-backed claim.

## Query behavior

The system should answer questions such as:

- What did I work on during a period?
- What changed in a project?
- Which meetings and documents support this claim?
- Who worked on a project with me?
- What decisions were made?
- What commitments are current?
- What is waiting or blocked?
- What evidence supports an accomplishment?
- What is uncertain or contradictory?

The answer process is:

1. Interpret the question.
2. Apply work scope and date filters.
3. Search canonical evidence.
4. Search extracted or raw records when the canonical layer has no answer.
5. Label raw or unreviewed evidence clearly.
6. Separate facts, inferences, conflicts, and missing evidence.
7. Return source paths and locations.

The query layer may use raw or unreviewed records for discovery. It must not silently use them to change canonical names, current tasks, or career claims.

## Wispr Flow and Granola

Wispr Flow and Granola are the present and future input streams.

Each input keeps:

- Provider name.
- Provider record ID when available.
- Capture or event date.
- Retrieval date.
- Cursor or checkpoint when available.
- Original response.
- Normalized evidence records.

The intake process is incremental and repeatable. A repeated response must not create duplicate source records.

The query layer reports feed freshness. It does not claim that a live source is current when the last successful retrieval is unknown.

## Failure behavior

The system must never hide a source because parsing failed.

It records failed work with:

- Source ID.
- Failure stage.
- Error class.
- Safe diagnostic message.
- Retry status.
- Manual conversion option when available.

The system must preserve partial output and never replace a good prior result with an empty failed result.

## Completion criteria

The design is complete when the system can demonstrate:

- One source manifest covers every physical file.
- Explicit roots distinguish Zoom, Capacities, Notion, OneNote, formal records, and discovery evidence.
- Raw files remain unchanged after repeated runs.
- All 29 OneNote files can be extracted through the selected local converter.
- All readable Notion and Capacities records have derived source records.
- Zoom folders produce one meeting group per dated folder.
- Existing transcripts link before new transcription runs.
- Missing Zoom transcripts have a local queue with status.
- Projects, people, and organizations have canonical records and aliases.
- Former project names remain linked to one project.
- Dates retain their source basis.
- Historical records do not create current tasks.
- Future and 14-day explicit commitments can create current task records.
- Personal and mixed records stay outside the default work query.
- Duplicate and conflict relationships remain visible.
- Exact search, local embeddings, and relationship search return source-backed candidates.
- Query answers cite source paths and distinguish fact from inference.
- Wispr Flow and Granola inputs can enter the corpus without duplicate records.
- A rebuild can recreate derived records and indexes from raw evidence.

## Deliberately not built

- Atlas integration.
- Email integration.
- Public web research over the corpus.
- Cloud transcription.
- External model calls with raw work evidence.
- Multi-user access control.
- Automatic backfill of historical tasks.
- Automatic deletion or movement of raw evidence.
- A separate graph database before the SQLite relationship view proves insufficient.
- A polished career document generator before the evidence layer is stable.
