# TrojanHorse full-scale audit

Audit date: 2026-09-09

Repository: `main`; audit performed against the working tree after the reviewed
completion design and the local answer boundary verification checkpoint
Scope: repository, active runtime, local SQLite state, generated acceptance
reports, provider-capture ledgers, tests, and operations configuration. Raw
source content and secrets were not copied into this document.

The report checkpoint used for the current counts was generated at
`2026-09-08T01:47:56-07:00`.

## Executive verdict

TrojanHorse now has a functioning local evidence archive for the captured
sources, a current preservation proof, deterministic organization, and
source-backed project/task/career views. The active `work-corpus/` package is
the only supported runtime; the old Atlas/RAG lane is explicitly quarantined.

The archive/search completion boundary is met. The one-time Granola REST
archive is complete for its current API listing, the 20 local `.eml` files are
normalized and searchable, and no grouped review queue remains open. The
older MCP UUID shadow is incomplete, but it is redundant and is not an archive
blocker.

The local answer milestone is now implemented as a CLI over the existing exact
search and source-backed views. The remaining work is deliberately small and
separate from ingestion:

1. manually inspect a representative answer-evaluation set before relying on
   synthesis for consequential decisions;
2. optionally add a web/API or polished UI layer, then refine generic labels,
   aliases, and retained Zoom linkage states.

This does not require the owner to inspect 1,500 task/date/decision rows one by
one. The approved first pass closed those queues without forcing uncertain
identities, privacy decisions, or current-task claims.

## Evidence basis

The audit reconciled the live `work-corpus/state/work_corpus.sqlite` database,
the generated report and ledgers under `work-corpus/corpus/reports/` and
`work-corpus/state/`, the active Python package, the repository packaging and
test configuration, the legacy package and bridge, and `homelab.yaml`.

The decisive checks were:

- SQLite `quick_check`: `ok`.
- SQLite foreign-key check: `0` violations.
- Active package suite: `283 passed` under both the default Python 3.13/SQLite
  runtime and the Homebrew Python 3.14/SQLite runtime.
- Fatal Ruff check, Python compilation, and `git diff --check`: passed.
- Editable install smoke in an isolated temporary virtual environment: passed,
  including `work-corpus --help` and an active boundary test. The host's
  externally-managed Homebrew Python correctly rejected a system install; no
  system environment was modified.
- A representative real query for “Weekly Strategy Meeting” returned results
  in both `All` and `Work` scopes without raw fallback.
- Current raw two-pass verification: `passed`, with all 2,758 files and
  59,546,347,641 bytes matching and zero added, removed, or changed paths.
- Current pipeline rows: `0` running and `1` pre-existing stale row recovered
  to `abandoned`.

## What is built

### Active local corpus runtime

The supported implementation is `work-corpus/`, installable from the
repository root as `trojanhorse-work-corpus`. Its CLI currently provides:

- inventory and source-root classification;
- source-version identity and append-only provenance, with content hashes where
  the source bytes were hashed;
- deterministic normalization for supported local text, HTML, PDF, Office,
  tables, JSON, transcripts, and OneNote through a local converter;
- local Zoom media scanning, existing-transcript reuse, and checkpointed local
  transcription;
- local Granola and Wispr Flow snapshot import;
- a read-only Granola REST archive client;
- exact FTS search with explicit `All` and `Work` scopes;
- deterministic project links, task-proposal scanning, review ledgers, and
  acceptance reports;
- source-backed project, task-candidate, and career-evidence views;
- a read-only `answer`, `answer-compare`, and `answer-eval` CLI over exact
  search, with source/version locators and explicit evidence-versus-synthesis
  fields;
- local `doctor` and two-pass `raw-verify` checks; and
- a tested, locked, overlap-watermarked Granola REST delta runner with
  five-minute macOS launchd and Linux systemd templates. The canonical Mac job
  skips the expensive local rebuild when a poll returns only overlap data.

The runtime provides a local CLI answer layer but does not provide a web/API
answer-synthesis service, embeddings, semantic ranking, or an interactive UI.
Its retrieval path remains exact search plus SQLite relationship traversal and
deterministic evidence views.

### Current corpus accounting

| Measure | Current evidence | Meaning |
| --- | ---: | --- |
| Physical source files | 2,758 | All are present in the live inventory; 2,738 are substantive and 20 are Finder metadata. |
| Source versions | 2,758 | One current source-version row per inventoried source record. |
| Current normalized outputs | 793 | Current parser outputs, including all 20 local `.eml` files. |
| Normalization records | 1,869 | 793 current outputs plus 1,076 retained prior-good outputs. |
| Source versions without a normalization record | 889 | Media, metadata, unknown/intermediate artifacts, or intentionally excluded records. |
| Evidence records | 72,199 | Source-backed derived evidence units. |
| FTS rows | 72,198 | Fresh exact-search index. The one-row difference is not treated as an error. |
| Relationship rows | 1,243 | Fresh deterministic relationship index. |
| Pending `review_item` rows | 0 | No grouped review queue remains open. |
| Pipeline rows | 0 running; 1 abandoned | A pre-existing stale run was recovered without changing raw data. |
| Project/task/career view rows | 27 / 1,951 / 71,834 | Rebuildable source-backed ledgers; current task rows remain 0. |
| Zoom linkage groups marked `needs_review` | 52 | Non-destructive meeting association uncertainty; not a raw-data deletion. |

Current source-system counts are: Capacities 1,722; Granola 46; inventory
discovery 15; Notion 134; OneNote 29; unclassified residual 14; Wispr Flow 2;
and Zoom 796.

The inventory is broader than the normalized text layer. In particular, 52
current source records have no non-empty content hash: two large Capacities
archives, one discovery JSON file, and 49 non-final Zoom `.zoom`/`.tmp`
artifacts. They remain inventoried; they are not silently treated as
searchable evidence.

### Provider and media coverage

| Source | Verified result | Objective boundary |
| --- | --- | --- |
| Granola REST | 559 unique notes across 19 pages; 559 summaries; 557 transcripts; 2 summary-only; all 559 imported and searchable | Complete for the current REST listing. |
| Granola MCP shadow | 559 listed UUIDs; 186 content captures; 181 detailed summaries; 177 transcripts; all 559 imported/searchable | 378 detail and 382 transcript gaps remain, but this shadow is redundant with the REST archive. |
| Wispr Flow | 13 records: 12 meetings and 1 scratchpad; all imported/searchable | All 12 meetings have start, end, and provider-modified dates. The scratchpad has capture/provider metadata but no event date in its source object. |
| Capacities | 563 typed pointers; 557 matched; 451 local payload targets; 1,216 confirmed relationships | Six pointer records retain explicit missing-file-size metadata. No signed URL was fetched. |
| Zoom | 231 tracked groups; 230 succeeded; 1 partial; 0 eligible final media without a transcript or terminal status | 52 linkage states remain `needs_review`; 49 non-final `.zoom`/`.tmp` artifacts remain inventory-only. |
| OneNote | 29/29 files; 295/295 extracted pages | Local converter path works in the current machine-specific setup. |
| Notion | 95 pages, 2 databases, 24 attachments | No current mechanical gap reported. |

### Organization and review

The deterministic organization pass was run twice with the same run date and
did not create duplicate derived entities, links, or review rows on the second
run.

- 9 explicit project entities and 9 aliases were created.
- 27 evidence-backed project links were created.
- 0 people and 0 organizations were promoted because no safe canonical alias
  was available.
- 48 ambiguous titles were recorded as generic topic labels. No identity was
  inferred from a title alone.
- 1,930 evidence records were scanned for explicit task proposals.
- 0 task rows and 0 current task rows were created under the existing date and
  scope rules. The task view retains 1,951 current, historical, and
  scope-review candidates, so the zero current-task result is visible rather
  than a dropped-data condition.
- 4,479 review rows were resolved by the approved first pass; 622 provisional
  display candidates were selected; the residual ledger has 0 pending entries.

No item-by-item owner review is required for the current acceptance state.
Generic topic labels, acceptance of the one partial Zoom result, and the
unified `All` policy are already recorded decisions.

### Local answer layer and privacy verification

The new answer path is read-only. It opens the corpus with the immutable SQLite
URI, rejects rollback/WAL sidecars, requires and shares the active Granola
maintenance lock, starts a read transaction, skips bootstrap and pipeline
recording, and calls exact search without an FTS rebuild. Evidence-only answers
expose source IDs, source versions, and locators. Optional local synthesis uses
loopback Ollama; the checked-in default is the installed `llama3.2:1b` model.

The comparison path uses one search result and three lanes: local original,
local sanitized, and `g2k-sensitive`. The original packet is never sent to the
gateway. A bounded live check produced a 4,256-byte sanitized packet with three
citations and no selected source IDs, version IDs, paths, URLs, e-mail
addresses, or phone numbers. The database file size, mtime, evidence count,
FTS count, and pipeline count were unchanged before and after the CLI call.

The live local and sensitive routes were exercised with the same bounded
question. Strict parsing accepted only the required JSON contract; uncited,
fenced, oversized, timed-out, or otherwise invalid completions became a
`model_error` evidence fallback. The evaluator leaves `accuracy_claim` unset
and names source inspection as the review authority. These runtime checks show
the boundary and failure behavior; they do not establish that a model answer is
accurate.

## What is not finished

### P0 — closed

1. **Activate the maintenance timer.** Complete. The canonical Mac user
   LaunchAgent `com.khamel83.work-corpus-granola-delta` is installed at
   `~/Library/LaunchAgents/com.khamel83.work-corpus-granola-delta.plist`, runs
   at load and every 300 seconds, retrieves the secret through the homelab SSH
   broker, and keeps the full corpus on the Mac. A supervised run fetched one
   note, completed all six stages, advanced the checkpoint, and exited 0.
   The Linux systemd files remain optional templates for a host containing the
   corpus.

### P1 — manual answer evaluation and optional presentation layer

1. **Inspect a broader representative answer set.** Check each returned
   source/version locator against the local source and record unsupported claims,
   missing citations, date errors, and conflict handling. Metrics and model
   agreement do not establish accuracy.
2. **Add a web/API or polished UI only if needed.** The source-backed views,
   exact search, and read-only CLI are already usable inputs. Keep raw text
   local and retain the same sanitized gateway boundary.

### P2 — optional refinement

- Refine generic topic labels and add people/organization aliases.
- Resolve the 52 retained Zoom linkage states where the value justifies it.
- Add embeddings or semantic ranking only after exact search and relationship
  traversal show a measured need.
- Increase coverage in lower-covered modules (`normalize`, `granola_api`,
  `transcription`, and `doctor`) as normal maintenance.
- Remove empty legacy SQLite tables only as a separate migration decision; they
  are not currently a runtime blocker.
- Complete the MCP shadow only if it serves a use case not covered by REST.

## What “finished” means

There are two defensible finish lines:

### Archive/search finish line

This is met for the captured sources: raw files are present, provider captures
are local, Granola REST records are imported/searchable, eligible Zoom media
has terminal transcription outcomes, all 20 local `.eml` files are normalized
and searchable, normalization and FTS are fresh, current raw preservation has
a two-pass proof, and deterministic organization has completed without pending
review items. The MCP UUID feed remains a redundant shadow with explicit gaps.

### Usable private assistant finish line

The local CLI assistant finish line is met: it retrieves evidence, preserves
source locators, separates source facts from synthesis, abstains or falls back
when evidence/model output is insufficient, and has an explicit sanitized
comparison route. A web/API or polished UI remains optional. Manual source
inspection is still required before consequential use.

## Owner input required

No operational input remains for the approved archive and maintenance path. The
product policy decisions are already recorded:
`work-corpus/` is canonical, local `.eml` files are included in `All`, generic
topic labels are acceptable, the one partial Zoom result is accepted, and no
item-by-item review is required. The assistant/API/UI layer can be prioritized
later without reopening ingestion.

## Cadence note

The five-minute interval is an operations choice, not a provider requirement.
Granola documents an `updated_after` filter, opaque cursor pagination, and a
maximum list page size of 30 in its [List Notes API documentation](https://docs.granola.ai/api-reference/list-notes).
Its [API introduction](https://docs.granola.ai/introduction) documents a
5-request-per-second sustained limit, a 25-request burst per five seconds, and
rate-limit responses. The checked-in runner uses the delta filter, keeps pages
at 30, paces requests, honors retry timing, and overlaps the watermark by five
minutes. That makes five minutes a reasonable freshness target for this local
archive, while a slower interval can reduce local work and a webhook would be
a separate provider/account deployment decision. The initial full pull is
already complete; future runs should be deltas, not another historical pull.

## Security and deployment boundary

- Raw data, generated SQLite state, reports, and provider captures are local
  ignored artifacts and are not part of the remote repository.
- The Granola API key is not in this checkout; the documented runtime retrieves
  `GRANOLA_API_KEY` from the encrypted homelab vault.
- The active Granola client is read-only. No provider write-back, Atlas call,
  mailbox access, or cloud transcription is part of the active path. Loopback
  Ollama is opt-in. The explicit `g2k-sensitive` route receives only the
  bounded sanitized packet; the raw local packet and full citation map stay on
  the Mac.
- `homelab.yaml` records the canonical runtime as `macmini` managed by the
  user LaunchAgent, while monitoring remains `standby` and health checks remain
  `[]` because no homelab monitor is configured for this local-only job.
- `docs/OPERATIONS.md` documents the active launchd job and the optional Linux
  templates. The homelab is a secret broker only; no full raw-corpus clone was
  created there.
- The remote repository is therefore source code and policy, not a cloneable
  copy of the private corpus. A fresh clone needs the local data and machine
  configuration before it can reproduce the current report.

## Standards and specification review

### Standards

- The active package follows the local-only/raw-preservation boundary in its
  implemented paths and has a meaningful test suite.
- The active repository entry point, test configuration, runbook, CI, and
  legacy boundary now describe one supported architecture. The old package and
  bridge remain present only as quarantined historical material.
- Fatal Ruff rules are an acceptance gate. Broader style/type coverage and
  production monitoring remain normal follow-up work.

### Specification

- The ingestion and deterministic organization milestones in the reviewed
  local-corpus specification are met for captured sources, including the REST
  archive, local transcription terminal accounting, FTS, relationships, and
  first-pass policy.
- The specification's old count wording was inaccurate; the canonical metric is
  now source versions versus normalization records.
- The 20 local `.eml` files are now parsed locally, with body/header/attachment
  metadata locators and separate email-header date observations. Mailbox access
  remains outside scope.
- Project, task-candidate, and career-evidence ledgers are implemented as
  rebuildable source-backed views. The broader goal of a local work assistant
  remains incomplete only because answer synthesis/API/UI has not been built.

## Canonical documents

- [TODO checklist](../TODO.md)
- [Current corpus status](LOCAL_WORK_CORPUS_STATUS.md)
- [Remaining work](REMAINING_WORK.md)
- [Boundary ADR](adr/0001-local-work-corpus-boundary.md)
- [Completion specification](superpowers/specs/2026-09-07-canonical-work-corpus-completion.md)
- [Completion implementation plan](superpowers/plans/2026-09-07-canonical-work-corpus-completion.md)
- [Operations runbook](OPERATIONS.md)
- [Legacy boundary](LEGACY_ATLAS.md)
- [Reviewed design](superpowers/specs/2026-09-04-local-work-corpus-design.md)
- [Local generated report](../work-corpus/corpus/reports/what_we_have_and_need.md)
- [Machine report](../work-corpus/corpus/reports/status.json)
