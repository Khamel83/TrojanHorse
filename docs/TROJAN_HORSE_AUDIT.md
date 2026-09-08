# TrojanHorse full-scale audit

Audit date: 2026-09-07

Repository: `main` at `2fc4519bd01ce4f94fb6cf1450e2350a25feca64` at audit start
Scope: repository, active runtime, local SQLite state, generated acceptance
reports, provider-capture ledgers, tests, and operations configuration. Raw
source content and secrets were not copied into this document.

The report checkpoint used for the current counts was generated at
`2026-09-07T20:38:38-07:00`.

## Executive verdict

TrojanHorse has a functioning local evidence-archive foundation for the
currently captured sources. Inventory, provenance, normalization, local Zoom
transcription, exact full-text search, deterministic organization, and
acceptance reporting are implemented and have current local evidence.

TrojanHorse is not finished as an end-user assistant or continuously operated
service. The remaining work is not “read 1,500 review rows.” The approved first
pass already closed those queues without forcing uncertain identities or
privacy decisions. The remaining work is product and operations work:

1. establish one supported runtime and retire or quarantine the broken legacy
   Atlas/RAG lane;
2. make installation, tests, health checks, and scheduled maintenance
   reproducible;
3. decide how to handle the 20 already-local `.eml` files and verify the
   current raw tree;
4. build the project, task, career-evidence, and/or local assistant views that
   turn the archive into a usable product.

The one-time Granola REST archive is complete for its current API listing. The
older MCP UUID shadow is incomplete, but it is redundant and is not an archive
blocker.

## Evidence basis

The audit reconciled the live `work-corpus/state/work_corpus.sqlite` database,
the generated report and ledgers under `work-corpus/corpus/reports/` and
`work-corpus/state/`, the active Python package, the repository packaging and
test configuration, the legacy package and bridge, and `homelab.yaml`.

The decisive checks were:

- SQLite `quick_check`: `ok`.
- SQLite foreign-key check: `0` violations.
- Active package tests: `181 passed`.
- Active package compile check: passed.
- A representative real query for “Weekly Strategy Meeting” returned results
  in both `All` and `Work` scopes without raw fallback.
- Root `python3 -m pytest -q`: collection fails because the root package
  `trojanhorse` is not importable.
- Repository-wide Ruff check: not clean (`800` reported findings in the audit
  run).
- The current raw-immutability ledger is `passed`, but its comparison is from
  2026-09-04 and covers only 1,414 files. It is not a current 2,751-file proof.

## What is built

### Active local corpus runtime

The supported implementation is `work-corpus/`, installed editable in the
local `/Volumes/2TB_SSD/Tools/work-corpus-venv` environment. Its CLI currently
provides:

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
  acceptance reports.

The runtime does not provide a web/API answer-synthesis service, embeddings,
semantic ranking, or an interactive assistant. Its current query path is exact
search plus SQLite relationship traversal.

### Current corpus accounting

| Measure | Current evidence | Meaning |
| --- | ---: | --- |
| Physical source files | 2,751 | All are present in the live inventory; 2,731 are substantive and 20 are Finder metadata. |
| Source versions | 2,751 | One current source-version row per inventoried source record. |
| Current normalized outputs | 773 | Current parser outputs. |
| Normalization records | 1,849 | 773 current outputs plus 1,076 retained prior-good outputs. |
| Source versions without a normalization record | 902 | Media, metadata, unknown/intermediate artifacts, or intentionally excluded records. |
| Evidence records | 72,139 | Source-backed derived evidence units. |
| FTS rows | 72,138 | Fresh exact-search index. The one-row difference is not treated as an error. |
| Relationship rows | 1,243 | Fresh deterministic relationship index. |
| Pending `review_item` rows | 0 | No grouped review queue remains open. |
| Zoom linkage groups marked `needs_review` | 52 | Non-destructive meeting association uncertainty; not a raw-data deletion. |

Current source-system counts are: Capacities 1,722; Granola 39; inventory
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
- 1,910 evidence records were scanned for explicit task proposals.
- 0 task rows and 0 current task rows were created. This is consistent with
  the current date rules, but it means a usable task view is not yet a finished
  downstream product.
- 4,479 review rows were resolved by the approved first pass; 622 provisional
  display candidates were selected; the residual ledger has 0 pending entries.

No item-by-item owner review is required for the current acceptance state.
Generic topic labels, acceptance of the one partial Zoom result, and the
unified `All` policy are already recorded decisions.

## What is not finished

### P0 — make the repository safe and reproducible

1. **One canonical entry point.** The active product is `work-corpus/`, but the
   root `pyproject.toml` still declares a lowercase `trojanhorse` package that
   is not present. `TrojanHorse/__init__.py` imports missing modules including
   `processor.py`, `rag.py`, `meeting_synthesizer.py`, and `index_db.py`.
   The root tests therefore fail at collection. The old `th` commands,
   `run_tests.sh`, workday scripts, and Atlas bridge must be retired,
   quarantined, or deliberately rebuilt.
2. **Reproducible install and verification.** A fresh checkout does not expose
   `work-corpus` on the default shell path, and its `pyproject.toml` does not
   install optional PDF/Office parsers or a test runner. Add one supported
   setup, a lock or pinned dependency policy, active tests in CI, and a safe
   `doctor`/health command.
3. **Current raw proof.** The existing raw-immutability pass is valid for the
   1,414-file historical snapshot only. Run a fresh preservation check against
   the current 2,751-file tree. Do not claim current raw immutability until
   that check exists.
4. **Captured local format gap.** Twenty `.eml` files inside the captured
   Capacities trees are inventoried and hashed, but the active normalizer
   hard-excludes `kind=email`. Mailbox access is not required; the open work is
   local parsing or an explicit archive-only decision. The 49 non-final Zoom
   artifacts need the same explicit policy, but they must not be fed to the
   final-media transcription path automatically.
5. **Run bookkeeping.** One historical `query` pipeline row remains marked
   `running`. Add stale-run recovery or a doctor check before using pipeline
   history as an operational health signal.

### P1 — turn the archive into the intended product

1. Build source-backed project history, current task candidates, and career
   evidence views. The archive exists; these user-facing derived outputs do
   not.
2. Validate the task extractor against a bounded set of source-backed examples
   so that `0` task rows is a deliberate result rather than an unmeasured
   conservative parser.
3. Add local answer synthesis over the evidence and derived views if the goal
   is an assistant rather than a search/reporting tool. Keep raw corpus content
   local and preserve source locators in every answer.
4. Add the maintenance workflow for new provider data: Granola delta capture,
   local inventory/import/normalize/report, checkpointing, and failure alerts.
   The one-time archive does not need another full historical pull.

### P2 — optional refinement

- Refine generic topic labels and add people/organization aliases.
- Resolve the 52 retained Zoom linkage states where the value justifies it.
- Add embeddings or semantic ranking only after exact search and relationship
  traversal show a measured need.
- Improve Ruff/type coverage and increase test coverage in the lower-covered
  modules (`normalize`, `granola_api`, `transcription`, and `doctor`).
- Remove empty legacy SQLite tables only as a separate migration decision; they
  are not currently a runtime blocker.
- Complete the MCP shadow only if it serves a use case not covered by REST.

## What “finished” means

There are two defensible finish lines:

### Archive/search finish line

This is substantially met for the captured sources: raw files are present,
provider captures are local, Granola REST records are imported/searchable,
eligible Zoom media has terminal transcription outcomes, normalization and FTS
are fresh, and deterministic organization has completed without pending review
items. The caveats are the historical raw-preservation proof and the 20 local
`.eml` files not yet in normalized search.

### Usable private assistant finish line

This requires four bounded work packages:

1. **Boundary and packaging:** make `work-corpus/` canonical, quarantine the
   legacy lane, add reproducible setup/CI/doctor, and fix stale operational
   metadata.
2. **Completeness closure:** verify the current raw tree and either parse the
   local `.eml` files or record an explicit archive-only reason; classify the
   non-final Zoom artifacts without sending them to the wrong processor.
3. **Product views:** implement and test project, task, career-evidence, and
   answer-synthesis outputs over source-backed evidence.
4. **Maintenance:** implement a scheduled or manually invoked Granola delta
   workflow with observable receipts and a safe local rerun path.

This is several focused implementation passes, not a single remaining
checkbox. It does not require manually reading the existing review queues.

## Owner input required

The following are the only decisions that materially affect the next build:

1. **Canonical product:** confirm that the private local `work-corpus/` runtime
   is the product and the old Atlas/RAG service is retired or quarantined.
2. **Local `.eml` treatment:** should the 20 already-local files be parsed
   locally and included in `All`, or intentionally remain inventory-only? This
   does not authorize mailbox access.
3. **First deliverable:** which comes first—project history, a current task
   view, career evidence, or a small local assistant over all three? The
   recommended sequence is evidence-backed views first, assistant synthesis
   second.
4. **Maintenance mode:** manual runs or scheduled Granola delta ingestion? If
   scheduled, the remaining owner input is the approved host/service location;
   the Granola secret is already held outside this checkout.

The previously supplied decisions are already sufficient for the rest: generic
topic labels are acceptable, the unified `All` corpus is the default, the one
partial Zoom result is accepted, and no item-by-item review is required.

## Cadence note

The five-minute question is an operations choice, not a completion gate. The
one-time REST archive used paginated listing and per-note retrieval with pacing
and retry handling. The repository does not currently run a recurring delta
job. A future cadence should be chosen from the provider's supported delta or
webhook behavior, rate limits, desired freshness, and local resource cost. A
single initial full pull is already complete; the remaining implementation is
the durable delta/monitoring path, not another historical archive pull.

## Security and deployment boundary

- Raw data, generated SQLite state, reports, and provider captures are local
  ignored artifacts and are not part of the remote repository.
- The Granola API key is not in this checkout; the documented runtime retrieves
  `GRANOLA_API_KEY` from the encrypted homelab vault.
- The active Granola client is read-only. No provider write-back, Atlas call,
  mailbox access, cloud transcription, or external raw-corpus model call is
  part of the active path.
- `homelab.yaml` still says lifecycle `development`, monitoring `standby`,
  production host `unknown`, and health checks `[]`. `docs/OPERATIONS.md` is
  referenced but does not exist. There is no evidence of a deployed production
  service or scheduled maintenance.
- The remote repository is therefore source code and policy, not a cloneable
  copy of the private corpus. A fresh clone needs the local data and machine
  configuration before it can reproduce the current report.

## Standards and specification review

### Standards

- The active package follows the local-only/raw-preservation boundary in its
  implemented paths and has a meaningful test suite.
- The repository-wide engineering surface is not clean: the root packaging,
  scripts, runbook, CI, and homelab operations metadata still describe an older
  system. This is the highest standards issue because it permits an operator to
  run the wrong architecture.
- Lint is not an acceptance gate today, and the active runtime's lower-covered
  modules need more tests before it should be called production-ready.

### Specification

- The ingestion and deterministic organization milestones in the reviewed
  local-corpus specification are met for captured sources, including the REST
  archive, local transcription terminal accounting, FTS, relationships, and
  first-pass policy.
- The specification's old count wording was inaccurate; the canonical metric is
  now source versions versus normalization records.
- The 20 local `.eml` files expose a boundary mismatch between “mailbox access
  is outside scope” and “all captured local evidence should be searchable.”
  That needs one explicit owner decision or a local parser implementation.
- The broader goal of a local work assistant remains incomplete because there
  is no answer-synthesis layer and no finished project/task/career output.

## Canonical documents

- [TODO checklist](../TODO.md)
- [Current corpus status](LOCAL_WORK_CORPUS_STATUS.md)
- [Remaining work](REMAINING_WORK.md)
- [Boundary ADR](adr/0001-local-work-corpus-boundary.md)
- [Reviewed design](superpowers/specs/2026-09-04-local-work-corpus-design.md)
- [Local generated report](../work-corpus/corpus/reports/what_we_have_and_need.md)
- [Machine report](../work-corpus/corpus/reports/status.json)
