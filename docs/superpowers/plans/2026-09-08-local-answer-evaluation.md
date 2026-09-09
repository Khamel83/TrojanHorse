# Local Answer Evaluation Implementation Plan

> **Execution note:** Execute this plan task by task in the isolated
> `codex/local-answer-evaluation` worktree. Keep the live corpus, generated
> SQLite/state files, evaluation cases, prompts, answers, excerpts, and
> gateway receipts out of Git. Use synthetic fixtures for the code gate. The
> existing Granola delta path is complete and must not be rebuilt or pulled
> historically.

**Goal:** Add the smallest useful local answer interface over the existing
exact-search and source-backed evidence views, with an explicit local-versus-
`g2k-sensitive` comparison path. Every answer must expose source/version
locators, distinguish source facts from model synthesis, abstain when evidence
is absent or conflicting, and avoid writing to the corpus during answering.

**Design:** `docs/superpowers/specs/2026-09-08-local-answer-evaluation-design.md`

**Test command:**

```bash
PYTHONPATH=work-corpus/src python3 -m pytest -q work-corpus/tests
```

## Task 1: Read-only search seam and evidence packet sanitization

**Files:**

- Modify: `work-corpus/src/work_corpus/db.py`
- Modify: `work-corpus/src/work_corpus/query.py`
- Add: `work-corpus/src/work_corpus/answering.py`
- Test: `work-corpus/tests/test_db.py`
- Test: `work-corpus/tests/test_query.py`
- Add: `work-corpus/tests/test_answering_packet.py`

**Interfaces:**

- `db.connect(path, read_only=False)` keeps existing callers unchanged. In
  read-only mode it requires the existing maintenance lock, opens the SQLite
  file with `mode=ro`, skips directory creation, migrations, and commits, and
  still exposes the normal row factory and foreign-key checks. Mutating CLI
  connections hold the matching exclusive lock.
- `query.search(..., rebuild_index=True)` preserves the current default and
  skips `rebuild_search_index` when `rebuild_index=False`.
- `prepare_evidence(search_result, *, remote_safe=False, max_hits=8,
  max_snippet_chars=1200, max_total_chars=12000)` returns a deterministic
  packet, an in-memory citation map, a SHA-256 packet digest, and a list of
  sanitizer findings. Remote-safe packets use `S1`-style IDs and omit raw
  source IDs, version IDs, absolute paths, database paths, URLs, tokens,
  e-mail addresses, and phone numbers while retaining labels, scope, dates,
  locators, and enough bounded text to answer the question.
- `AnswerEvidence` values retain the full local hit for citation inspection;
  packet text is treated as inert evidence and never executed.

**Steps:**

1. Add failing tests first. Assert read-only connections cannot create a
   missing database or mutate an existing database, `search(...,
   rebuild_index=False)` never invokes the rebuild function, and synthetic
   evidence produces stable local and remote packet digests.
2. Include e-mail, phone, URL, bearer/token, secret-like value, and absolute
   path fixtures. Assert the remote packet contains no matching sensitive
   values, preserves project/person words, bounds each snippet and total
   packet, and maps every citation ID back to a complete local source/version
   locator.
3. Run the focused tests and confirm the intended failures before writing
   implementation code.
4. Implement the read-only SQLite URI seam and the optional search rebuild
   flag. Reuse the existing `redact_snippet` and `scrub_derived_text`
   behavior, adding only balanced e-mail/phone/path redaction in the remote
   packet layer.
5. Run the focused packet/database/query tests, then `git diff --check`.

## Task 2: Completion backends and strict answer parsing

**Files:**

- Modify: `work-corpus/src/work_corpus/answering.py`
- Add: `work-corpus/tests/test_answering_backends.py`

**Interfaces:**

- `CompletionBackend` is a small protocol returning `Completion(text,
  metadata)`.
- `EvidenceOnlyBackend` never calls a model and formats source-backed facts
  with citations.
- `OllamaBackend(model, base_url, timeout_seconds, request_fn=None)` posts to
  the loopback Ollama `/api/chat` endpoint with `stream=false`, JSON output,
  temperature zero, and a bounded prompt. It rejects non-loopback URLs and
  reports timeout, transport, malformed, and model errors without including
  prompts or excerpts in exceptions.
- `GatewaySensitiveBackend(helper_path, timeout_seconds, runner=None)` invokes
  the sourced `g2k-sensitive` helper with `--no-session --no-tools
  --no-extensions --mode json`, parses the assistant `message_end` from
  NDJSON, and records route metadata without claiming the underlying provider.
- `parse_completion(text, allowed_citations, has_source_facts, has_conflict)`
  accepts only the JSON object `{answer, citations, stance}`, rejects unknown
  or duplicate citation IDs and empty answers, requires citations when facts
  exist, and requires `mixed` or `insufficient` stance for conflict. Model
  output is never treated as evidence.

**Steps:**

1. Add failing synthetic tests for a valid cited JSON response, unknown and
   duplicate citation IDs, missing citations, malformed JSON, conflict
   acknowledgment, local model failure, gateway nonzero/timeout output, and
   loopback URL validation. Assert no prompt text appears in raised errors.
2. Run the focused backend tests and confirm they fail because the adapters
   and parser are absent.
3. Implement the protocol, evidence-only formatter, strict parser, Ollama
   request, and gateway subprocess adapter with injectable transports for
   hermetic tests. Bound timeouts and response size; do not add a network
   dependency.
4. Run focused tests and refactor only after green. Record a synthetic Ollama
   and synthetic gateway receipt test that proves both adapters return the
   same parsed answer shape.

## Task 3: Answer orchestration and CLI entry points

**Files:**

- Modify: `work-corpus/src/work_corpus/answering.py`
- Modify: `work-corpus/src/work_corpus/cli.py`
- Add: `work-corpus/tests/test_answering.py`
- Add: `work-corpus/tests/test_cli_answer.py`

**Interfaces:**

- `answer(con, question, *, backend="evidence", scope=DEFAULT_SCOPE,
  limit=8, completion_backend=None, allow_sensitive_remote=False)` performs
  read-only search, builds the local or remote-safe packet as required,
  invokes the selected backend only when evidence permits, and returns a
  JSON-serializable result with `status`, `answer_kind`, `answer`, `citations`,
  `source_facts`, `inferences`, `conflicts`, `missing`, `packet_sha256`,
  backend/route metadata, and warnings.
- No-result questions return `status=no_evidence` and do not call a model.
  Conflicting or insufficient evidence returns `status=insufficient_evidence`
  unless the completion declares a `mixed` or `insufficient` stance; that
  declaration remains unverified until source inspection. Backend failure
  returns `status=model_error` with an evidence-only fallback and no untrusted
  model text.
- CLI commands:

  ```text
  work-corpus --root ROOT answer QUESTION [--backend evidence|ollama|g2k-sensitive]
  work-corpus --root ROOT answer-compare QUESTION --allow-sensitive-remote
  ```

  Both commands open the configured database read-only, never call bootstrap
  or the maintenance pipeline, and emit JSON to stdout. `g2k-sensitive` is
  rejected unless the explicit flag is present. Ollama model, loopback URL,
  timeout, scope, and limit are bounded command options.

**Steps:**

1. Add failing API/CLI tests for successful retrieval and citation locators,
   no-result behavior, conflict/insufficient evidence, invalid input, model
   failure fallback, sensitive-route opt-in, and unchanged database bytes and
   row counts.
2. Run the focused tests and confirm the intended failures.
3. Implement orchestration around one search result and one immutable packet.
   Keep evidence-only output separate from model synthesis and preserve the
   complete local citation map in the returned result. Add parser branches
   without changing existing maintenance command behavior.
4. Exercise the CLI against a temporary synthetic database and assert the
   exact JSON contract, then run the focused tests and the full active suite.

## Task 4: Same-question evaluation and comparison metrics

**Files:**

- Modify: `work-corpus/src/work_corpus/answering.py`
- Modify: `work-corpus/src/work_corpus/cli.py`
- Add: `work-corpus/tests/test_answer_eval.py`
- Modify: `README.md`

**Interfaces:**

- `compare_answers(con, question, *, local_backend, remote_backend,
  scope=DEFAULT_SCOPE, limit=8, allow_sensitive_remote=True)` runs the same
  search and remote-safe packet through local original, local sanitized, and
  gateway-sensitive lanes. It returns lane results, packet digest equality,
  sanitizer findings, and a source-grounded comparison; it never sends the
  original packet remotely.
- `evaluate_cases(con, cases_path, *, backends, allow_sensitive_remote=True)`
  reads ignored local JSONL cases with `id`, `question`,
  `expected_source_ids`, `expected_status`, and optional `expected_terms`.
  It reports citation precision/recall, invalid citations, expected-status
  and abstention correctness, conflict acknowledgment, term coverage as a
  review aid, sanitizer findings, elapsed time, and route/model metadata.
- CLI command:

  ```text
  work-corpus --root ROOT answer-eval --cases PATH [--allow-sensitive-remote]
  ```

  Evaluation output is stdout by default; an explicitly supplied output path
  must be outside Git-tracked source and is never committed.

**Steps:**

1. Add failing evaluator tests with synthetic cases covering a supported fact,
   no result, conflict, missing expected citation, and malformed model output.
   Assert metrics are computed from source IDs and that original packet text
   is never handed to the remote backend.
2. Run focused evaluator tests and confirm the intended failures.
3. Implement the comparison and scoring functions with deterministic JSON
   ordering and no automatic accuracy claim. Document that source inspection
   remains the acceptance authority.
4. Add concise README usage for evidence-only answers, local Ollama, the
   explicit sensitive comparison, and the ignored JSONL case shape.
5. Run focused and full tests, Ruff, compilation, and `git diff --check`.

## Task 5: Local/runtime verification, docs, review, and integration

**Files:**

- Modify: `TODO.md`
- Modify: `docs/REMAINING_WORK.md`
- Modify: `docs/LOCAL_WORK_CORPUS_STATUS.md`
- Modify: `docs/OPERATIONS.md`
- Modify: `docs/TROJAN_HORSE_AUDIT.md`

**Steps:**

1. Run the complete active suite, configured Ruff checks, Python compilation,
   and `git diff --check`. Inspect the diff for corpus paths, prompts,
   answers, excerpts, credentials, and accidental ingestion changes.
2. Run a synthetic end-to-end CLI answer and comparison. Then run a bounded
   live local Ollama canary with the selected small model, recording latency,
   context size, and whether strict JSON parsing succeeds. Treat this as a
   runtime observation, not an accuracy proof.
3. Run the same bounded sanitized synthetic canary through the real
   `g2k-sensitive` route. Record only route-level receipt metadata and the
   local packet digest; do not claim provider identity or remote retention.
4. Against the existing corpus, run only read-only bounded questions through
   the new interface. Inspect representative local source files using the
   returned source/version locators and compare local and remote outputs for
   omissions, date errors, unsupported claims, and conflict handling. Keep
   prompts, answers, excerpts, cases, and receipts in ignored local state.
5. Verify the Granola delta LaunchAgent remains loaded and has a healthy last
   exit without triggering a pull or rebuild. Do not run raw preservation
   verification unless a fresh receipt is specifically needed.
6. Update status/TODO/operations docs with exact commands, observed counts,
   model/route limitations, and the remaining manual evaluation boundary.
7. Request an independent read-only code review against `origin/main` and
   resolve findings. Use the verification-before-completion checklist, commit
   scoped changes, merge the feature branch into `main` while preserving
   unrelated dirty/untracked material, push the authorized remote update, and
   verify local and remote SHAs separately.
