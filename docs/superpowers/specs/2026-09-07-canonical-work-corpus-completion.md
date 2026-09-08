# Canonical Work-Corpus Completion Design

Status: approved for implementation on 2026-09-07

## Problem

The local evidence archive is searchable, but the repository still has two
conflicting product stories. The active `work-corpus/` package is the local
evidence runtime. The root `trojanhorse` package, `th` command, and Atlas bridge
are historical and currently fail to install or test. The active runtime also
has three missing product edges: local `.eml` records are inventoried but not
searchable, organization results are not presented as usable evidence views,
and future Granola updates require a manual full workflow.

## Decisions

1. `work-corpus/` is the only supported runtime and package entry point.
   Legacy Atlas/RAG code remains in the repository as explicitly quarantined
   historical material. It is not imported, installed, tested, or scheduled.
2. The 20 `.eml` files already inside the local Capacities trees are parsed by
   the Python standard library and included in the default `All` query. This is
   local file parsing, not mailbox access.
3. Project, task, and career output is deterministic and source-backed before
   any assistant synthesis is attempted. Every output row contains source and
   evidence identifiers plus a locator or an explicit missing value.
4. Granola maintenance uses the REST API `updated_after` filter. A delta run
   captures changed notes, preserves the raw response, and advances a local
   watermark only after inventory, import, normalization, organization, views,
   and reporting complete successfully.
5. The default scheduler interval is five minutes. This is a freshness choice,
   not a provider requirement. The client paces requests below Granola's
   documented sustained limit and respects `Retry-After` on rate limits.
6. The raw corpus remains immutable. New provider captures are append-only
   files under `data/`; all indexes, ledgers, views, and checkpoints remain
   derived state outside the raw tree.

## Scope

### In scope

- root packaging and test configuration that install and exercise
  `work-corpus`;
- a safe local `doctor` check and stale-run recovery;
- current two-pass raw-preservation verification;
- a standard-library `.eml` extractor with header, body, attachment metadata,
  and email-date provenance;
- deterministic project, task, and career evidence ledgers;
- a tested Granola `updated_after` client path, append-only delta runner,
  checkpoint, single-writer lock, and systemd timer template;
- documentation and acceptance evidence for the above.

### Out of scope

- mailbox discovery, IMAP, Outlook cache access, or mailbox write access;
- Atlas, the old bridge, external RAG, embeddings, vector infrastructure, or a
  web/API assistant;
- cloud transcription or sending raw corpus text to an external model;
- automatic historical task promotion or automatic résumé wording;
- enabling a scheduler on an unknown host. The checked-in unit is an
  installation template; activation remains an operator step once the host and
  checkout path are known.

## Interfaces

### Canonical runtime

- `pip install -e '.[dev,documents]'` from the repository root installs the
  `work_corpus` package and the `work-corpus` console command.
- `python -m pytest` from the repository root runs only
  `work-corpus/tests`.
- `work-corpus doctor` performs local path, optional-parser, SQLite-integrity,
  stale-run, and legacy-lane checks without network calls.
- `run_tests.sh` is a thin compatibility wrapper around the canonical test
  command.

### `.eml` extraction

- `extract_source(..., extension='.eml')` uses a standard-library RFC 822
  parser.
- Derived parts are `headers`, `body`, and `attachments`.
- Attachment bytes are never copied into derived text. Only filename, content
  type, and byte size are retained.
- The parsed `Date` header is recorded as a date observation with basis
  `email_header_date`; the filename/path hint remains a separate source fact.
- All derived text passes through the existing URL and secret scrubber.

### Evidence views

`work-corpus views` rebuilds these files below `work-corpus/corpus/reports/`:

- `project_evidence.csv`, `.json`, `.md` — one row per explicit project to
  evidence relationship;
- `task_candidates.csv`, `.json`, `.md` — current task rows plus every
  nonblank task proposal retained in the review ledger, labeled as current,
  historical, or scope-review;
- `career_evidence_ledger.csv`, `.json`, `.md` — every evidence unit from a
  source marked career value `medium` or `high`, with project links when
  present and `external_use=review_required` until separately validated;
- `views_acceptance.json` — counts, source scope, generation time, and the
  exact output paths.

The views contain no generated accomplishment claims. They are the bounded
input for a later local assistant or human review.

### Granola delta

- `GranolaApiClient.list_notes(updated_after=...)` sends the documented
  `updated_after` query parameter and retains opaque cursor pagination.
- `run_backfill(..., updated_after=...)` is reused for both an archive and a
  delta capture. The capture envelope records `mode` and the requested
  watermark.
- `python -m work_corpus.granola_delta --root <checkout>` reads
  `GRANOLA_API_KEY` from the environment, or a scheduler wrapper obtains that
  environment value from the existing secrets broker. The API key is never a
  command argument or repository file.
- The runner uses the latest successful provider `updated_at` minus a
  configurable five-minute overlap. The overlap prevents a strict “after”
  boundary or clock skew from dropping a note. Stable provider IDs make the
  repeated overlap idempotent.
- If no delta checkpoint exists, the runner seeds its watermark from the
  newest local REST archive. It never silently falls back to a full archive.
- A failed local stage leaves the raw delta capture in place and does not
  advance the checkpoint. The next run retries from the prior watermark.
- `work-corpus/ops/systemd/work-corpus-granola-delta.timer` defaults to five
  minutes. `RandomizedDelaySec` may spread simultaneous jobs, and the runner's
  local lock prevents overlapping writers.

## Acceptance criteria

1. A clean checkout installs the active package and `python -m pytest` runs the
   active suite without importing the legacy package.
2. The doctor reports the active package and SQLite checks, identifies legacy
   Atlas code as quarantined, and marks stale runs recoverable without a raw
   write.
3. A synthetic `.eml` test produces scrubbed, locatable header/body/attachment
   evidence and records the email header date. The live 20-file count becomes
   searchable after the ordered inventory/normalize run.
4. The views have stable schemas, are idempotent, contain no blank source
   records, and preserve the current zero-task-row fact while exposing the
   historical task proposals rather than dropping them.
5. Granola tests prove the `updated_after` parameter, cursor pagination, raw
   capture envelope, overlap watermark, failure checkpoint behavior, and
   idempotent re-import. No live Granola call is required for the code gate.
6. A fresh two-pass raw verification records the current file count and byte
   count and detects any hash/size/path change between passes.
7. Documentation distinguishes implemented code, generated local evidence,
   and the one remaining operator action: enabling the scheduler on a known
   host.

## Execution order

1. Canonical packaging, test gate, doctor, stale-run recovery, and raw verifier.
2. `.eml` parser, date provenance, tests, then the live local normalization.
3. Evidence views, tests, then the live view build.
4. Granola delta client/runner/scheduler, tests, and documentation.
5. Ordered live acceptance, repository audit updates, commit, and remote
   verification without staging raw or unrelated untracked files.
