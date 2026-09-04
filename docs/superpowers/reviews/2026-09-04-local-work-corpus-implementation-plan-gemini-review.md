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
