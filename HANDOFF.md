# Handoff — repository rationalization audit (2026-10-10)

## Done

Documentation-only reconciliation for issue
[#17](https://github.com/Khamel83/TrojanHorse/issues/17), tracked by the
coordinator [#16](https://github.com/Khamel83/TrojanHorse/issues/16) (stays
parked/tracking-only).

- Read the captured native intake packet in full:
  `docs/reconciliation/intake-2026-10-10.json` (manifest) and
  `docs/reconciliation/intake-2026-10-10-part-1.json` (17/17 records: 2 open,
  15 closed; `omitted: []`). Part-1 sha256
  `01aecc997b94812d25f3c82ca40eeb3350415343429ced749c61ac45fcc813b8` matches the
  manifest; the JSON was not modified. Captured base:
  `66820d3357ecd6a05a57fd214b17a2bfca99d1d7`.
- Classified every visible outstanding TODO and native record (completed /
  remaining / duplicate-superseded / owner-decision / unknown) with stable
  source links.
- Produced the single canonical ordered plan:
  [`docs/REPO_PLAN.md`](docs/REPO_PLAN.md) (created because TODO.md,
  REMAINING_WORK.md and the executed superpowers plans are not suitable repo-level
  plans). It carries the only ready-jobs marker: one uncovered ready job
  (test coverage in lower-covered modules, `existing_issue: null`). All
  owner-gated/conditional/manual items are excluded with their blockers.
- Full coverage, classification and corrections:
  [`docs/history/2026-10-10-repository-rationalization.md`](docs/history/2026-10-10-repository-rationalization.md).
- Corrections applied: `CONTEXT.md` and `TODO.md` no longer call the delivered
  answer CLI the "remaining product layer"; `HANDOFF.md` now holds this
  checkpoint, with the prior 2026-10-05 handoff preserved byte-identical at
  [`docs/history/2026-10-05-managed-rule-repair-handoff.md`](docs/history/2026-10-05-managed-rule-repair-handoff.md).

Changed paths: `TODO.md`, `CONTEXT.md`, `HANDOFF.md`, `docs/REPO_PLAN.md`,
`docs/history/2026-10-10-repository-rationalization.md`,
`docs/history/2026-10-05-managed-rule-repair-handoff.md`, plus the captured
packet under `docs/reconciliation/` unchanged.

## Input coverage and missing inputs

- Read: manifest + the single part (full bodies for both open issues, the open
  issue comment, closed records since 2026-07-12).
- Missing/unreadable: none omitted by the packet. The `g2k-workspace` helper was
  unavailable this session (`ModuleNotFoundError: No module named 'g2k'`), so no
  live GitHub readback; the packet is dated evidence.
- Not verifiable here: native merge identities, live issue/PR state, the Mac
  launchd job, the local SQLite corpus and generated reports.

## Runtime acceptance

Not applicable and not established: this change is documentation only. No code,
runtime, provider, credential or deployment operation was performed. Native
dispositions and the readiness of any job are pending trusted exact-head review
and the orchestrator's merge.

## In flight

The reviewed documentation PR is not yet merged. The ready-jobs batch may only
be admitted by G2K after trusted exact-head review and merge.

## Next step

1. Trusted review PASS on the exact head, then merge the documentation PR.
2. Close #17 as complete-on-merge; keep #16 parked/tracking-only.
3. Let G2K admit the one ready uncovered job through its ready-jobs contract.

## Recheck commands

```bash
sha256sum docs/reconciliation/intake-2026-10-10-part-1.json
grep -rl 'g2k:ready-jobs' --include='*.md' .
git status --porcelain
PYTHONPATH=work-corpus/src python3 -m pytest -q work-corpus/tests
```
