# Local Work Corpus Implementation Plan: Gemini Review

Review model: Antigravity, Gemini 3.1 Pro, high effort
Review date: 2026-09-04
Review scope: implementation plan, design, inventory summaries, and package path inspection

The reviewer was instructed not to open `data/`, raw exports, media,
transcripts, attachments, discovery archives, or ZIP contents. No raw work
evidence was provided.

## Plan Challenge

### Challenges

- High: `work-corpus/` base paths (Task 1) — wrong repository path / impossible command — The plan instructs modifying `work-corpus/config.json` and running `work-corpus/tests/test_boundary.py`, but `work-corpus/` does not exist at the repository root and the plan forbids copying the bootstrap package blindly, meaning these commands will fail — Add an explicit step to selectively copy the required directory skeleton and starting files from `Omar_Work_Corpus_Bootstrap_v1/work-corpus/` to the repository root before attempting to modify or test them.

### Verdict

REVISE — The plan must include an explicit step to copy the required starting files from the bootstrap package to the root `work-corpus/` directory so the requested file modifications and tests can succeed.

## Disposition

Accepted. The plan now begins with a scaffold-promotion task that copies only
the package, configuration, and utility starting files required by the local
runtime. It excludes email modules, email schemas, Outlook scripts, and raw
 data. No other scope was added.

## Follow-up review

The plan was revised again so Task 0 creates a minimal local CLI instead of
copying the bootstrap CLI, which would import the excluded email module. The
plan also states that all test commands use `PYTHONPATH=work-corpus/src`.
Gemini 3.1 Pro should perform one final confirmation after this revision.

## Follow-up review 2

Gemini 3.1 Pro identified four additional issues:

- High: Task 0 test promotion — reuse — Reuse the bootstrap's non-email VTT
  fixture and safe utility tests instead of discarding all passing coverage.
- Medium: `config.local.example.json` — reuse — Promote the reviewed bootstrap
  example in Task 0 rather than recreating it.
- Medium: Pytest commands — convention alignment — Put
  `PYTHONPATH=work-corpus/src` in each test command, not only in the preamble.
- Medium: OneNote integration dependencies — missing constraint — Define the
  local `pyOneNote`/converter prerequisite and fail closed when it is absent;
  do not download it during a corpus run.

The plan was revised to reuse the safe fixture and tests, promote the config
example, prefix every explicit pytest command, and define the OneNote local
converter boundary. A final confirmation is still required.

## Follow-up review 3

Gemini 3.1 Pro identified four additional issues:

- High: Task 8 MCP items — schema contradiction — the plan needed an explicit
  `mcp_item` table or a clear mapping to existing source/evidence tables.
- High: Tasks 6 and 7 safe-batch execution — sequence contradiction — real
  data must be deferred to the Task 9 acceptance sequence; those tasks should
  use synthetic fixtures only.
- Medium: Task 0 file operations — ambiguity — files copied from the bootstrap
  must be marked as promoted rather than created.
- Low: Entity alias template — path consistency — keep the example at
  `work-corpus/entity_aliases.example.json`, matching the package-level config
  layout.

The plan was revised to add `mcp_item`, move real safe-batch work to Task 9,
mark promoted files explicitly, and move the alias template. A final
confirmation is required after this revision.

## Follow-up review 4

Gemini 3.1 Pro identified two final consistency issues:

- High: `mcp_item` schema — align the exact fields in Task 3 with the fields
  described in Task 8, including the original response hash and checkpoint.
- Low: file layout — remove the extra `schema.sql`, `adapters.py`, and
  `redaction.py` files and keep those responsibilities in the already mapped
  `db.py`, `normalize.py`, and `util.py` modules.

The plan was revised to align the `mcp_item` columns and remove those extra
files. A final confirmation is required after this revision.
