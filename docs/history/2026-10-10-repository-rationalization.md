# Repository rationalization audit — 2026-10-10

Dated evidence for the single documentation reconciliation authorized by
[#17](https://github.com/Khamel83/TrojanHorse/issues/17), tracked by the
coordinator [#16](https://github.com/Khamel83/TrojanHorse/issues/16). Ordered
plan: [docs/REPO_PLAN.md](../REPO_PLAN.md) (the one canonical plan). This file
holds the classification detail and the coverage report; it is historical
evidence, not a live status.

Captured base: `66820d3357ecd6a05a57fd214b17a2bfca99d1d7` (`origin/main` at
capture). No source revision after that base was consulted except files in this
worktree.

## 1. Captured inputs and coverage

| Input | Result |
| --- | --- |
| `docs/reconciliation/intake-2026-10-10.json` (manifest) | Read. `retained_records: 17`, `open_records: 2`, `omitted: []`, one record part. |
| `docs/reconciliation/intake-2026-10-10-part-1.json` (17 records) | Read in full. sha256 `01aecc997b94812d25f3c82ca40eeb3350415343429ced749c61ac45fcc813b8` matches the manifest entry. |
| Manifest ids | 1–17 all present in the part (`ids` list matches `native_ids`). |
| Coverage declared by the manifest | Full open issue/PR bodies and open issue comments; closed body excerpts since 2026-07-12. Other review/deployment evidence may be missing. |
| Unreadable/omitted | None omitted. The `g2k-workspace` helper was unavailable in this session (`ModuleNotFoundError: No module named 'g2k'`), so no live GitHub readback; the packet is dated evidence, not live status. |
| Not present in this worktree | Local SQLite corpus/state, generated reports under `work-corpus/corpus/`, the Mac launchd job, vault secrets, and native merge commits. |

The packet files were not modified: part-1 sha256 still matches the manifest.

## 2. Native record classification

| # | Kind | State in packet | Classification | Evidence / disposition |
| --- | --- | --- | --- | --- |
| 17 | issue | open | audit task | This reconciliation. Completes with this documentation PR; source-only. |
| 16 | issue | open | coordinator (`g2k:parked`) | Stays parked/tracking-only; keep open. |
| 15 | PR | closed | completed (merged 2026-10-08) | Janitor `AGENTS.md`/`INFRA.md` projection; retained. |
| 14 | PR | closed | completed (merged 2026-10-07T18:05:24Z) | Same projection family; superseded #13. |
| 13 | PR | closed, no `merged_at` | duplicate/superseded | Identical title and body sha256 `19f38f8b2ba6d609c7c9797ff952b927d375954c4f727b394bec237348b08134` to #14; closed 18:03:36Z, #14 merged 18:05:24Z. |
| 12 | PR | closed | completed (merged 2026-10-06) | Janitor projection. |
| 11 | PR | closed | completed (merged 2026-10-05) | Janitor projection. |
| 10 | PR | closed | completed (merged 2026-10-05) | Janitor `CONTEXT.md`/`TODO.md` reconcile; source SHA `0fdece42…`. |
| 9 | PR | closed | completed (merged 2026-10-05) | Projects the approved standing PASS merge policy. |
| 8 | PR | closed | completed (merged 2026-10-01) | Janitor `CONTEXT.md`/`TODO.md` reconcile; source SHA `98e067e0…`. |
| 7 | PR | closed | completed (merged 2026-09-30) | Janitor `AGENTS.md` sync. |
| 6 | PR | closed | completed (merged 2026-09-30) | Janitor `AGENTS.md` sync. |
| 5 | PR | closed | completed (merged 2026-09-29) | Janitor `AGENTS.md` sync. |
| 4 | PR | closed | completed (merged 2026-09-18) | Janitor reconcile; body said "must not merge", yet `merged_at` is set (superseded policy). Retained. |
| 3 | PR | closed | completed (merged 2026-09-13) | Janitor reconcile. |
| 2 | issue | closed 2026-09-23 | closed, not adopted | Star Opportunity proposal (blader/humanizer); no implementation/merge/adoption evidence. |
| 1 | issue | closed 2026-09-23 | closed, not adopted | Star Opportunity proposal (obra/superpowers plan-scoped SDD); no implementation/merge/adoption evidence. |

Every record carries `merge_identity: "unknown unless separately verified"`;
merge commits were not independently re-verified (no live access). Completion
above means "closed/merged per the packet", not re-verified runtime acceptance.

## 3. Outstanding repository items (owning records)

Stable links use base `66820d3357ecd6a05a57fd214b17a2bfca99d1d7`.

| Item | State | Owning source |
| --- | --- | --- |
| Broader manual answer-evaluation inspection | remaining, owner-manual | TODO.md:62, REMAINING_WORK.md:161, TROJAN_HORSE_AUDIT.md:200 |
| Optional web/API or UI layer | remaining, owner decision | REMAINING_WORK.md:165, TROJAN_HORSE_AUDIT.md:204 |
| Refine 48 topic labels / person-org aliases / 52 Zoom linkage states | remaining, optional | TODO.md:65, REMAINING_WORK.md:168, TROJAN_HORSE_AUDIT.md:210 |
| Semantic ranking / embeddings | remaining, gated on measured need | TODO.md:68, TROJAN_HORSE_AUDIT.md:212 |
| Test coverage in lower-covered modules | remaining, uncovered and ready | TROJAN_HORSE_AUDIT.md:214 |
| Remove empty legacy SQLite tables | remaining, owner migration decision | TROJAN_HORSE_AUDIT.md:216 |
| Complete Granola MCP shadow | remaining, conditional on an uncovered use case | TROJAN_HORSE_AUDIT.md:218 |
| Re-evaluate closed Star Opportunity proposals | closed, owner decision to reopen | issues 1, 2 |
| Milestones 1–3 and the full-scale audit receipts | claimed complete; owning receipts only, not re-verified here | TODO.md |

Also inspected and classified as non-outstanding: `docs/superpowers/plans/*`
checkboxes (the plans are marked executed/complete in their own status lines or
in TODO.md and are historical tracking, not open work); `progress.md` and
`findings.md` (historical Bridge material); `TESTING_GUIDE.md` and
`.claude/skills/**` checkboxes (templates/instructions).

Explicitly deferred by policy, therefore not jobs: mailbox access, Atlas
integration, cloud raw-data processing, graph/vector infrastructure, automatic
historical task backfill, polished career-document generation, provider
write-back (TODO.md "Explicitly deferred features";
`docs/adr/0001-local-work-corpus-boundary.md`).

## 4. Corrections applied to current records

- `CONTEXT.md` claimed the remaining product layer is "local answer
  synthesis/API/UI". The owning records show the answer CLI layer is delivered
  and the remaining edge is manual evaluation plus an optional web/API/UI.
  Corrected; receipts untouched.
- `TODO.md` "Continuation instructions" called the optional assistant layer "the
  remaining substantive product edge"; corrected to the delivered state.
- `HANDOFF.md` carried the 2026-10-05 managed rule-repair handoff as the current
  checkpoint; its bytes were preserved verbatim in
  [2026-10-05-managed-rule-repair-handoff.md](2026-10-05-managed-rule-repair-handoff.md)
  and `HANDOFF.md` now holds this audit's checkpoint.

No historical acceptance receipt was rewritten.

## 5. How to recheck this audit

```bash
# packet integrity (must match the manifest sha256)
sha256sum docs/reconciliation/intake-2026-10-10-part-1.json

# exactly one ready-jobs marker, and it parses
grep -rl 'g2k:ready-jobs' --include='*.md' .
python3 -c "import json,pathlib,re;t=pathlib.Path('docs/REPO_PLAN.md').read_text();\
b=re.search(r'\`\`\`json\n(.*?)\n\`\`\`',t,re.S).group(1);print(json.loads(b))"

# only allowed paths changed
git status --porcelain
```

## 6. PR report — captured revisions, inputs and coverage

Ready text for the audit PR body (the contract requires this report in the PR):

- Repository: `Khamel83/TrojanHorse`; captured source base
  `66820d3357ecd6a05a57fd214b17a2bfca99d1d7` (`origin/main`); packet captured
  `2026-10-11T09:06:50.418796+00:00`.
- Inputs read: `docs/reconciliation/intake-2026-10-10.json` (manifest) and
  `docs/reconciliation/intake-2026-10-10-part-1.json` (17/17 records; 2 open, 15
  closed). Part-1 sha256
  `01aecc997b94812d25f3c82ca40eeb3350415343429ced749c61ac45fcc813b8` matches the
  manifest entry; `omitted: []`.
- Readable: full bodies for the open issues #16/#17, the open comment on #17,
  and closed records #1–#15 as captured since 2026-07-12.
- Missing/unreadable: nothing omitted by the packet. `g2k-workspace` was
  unavailable (`ModuleNotFoundError: No module named 'g2k'`), so no live GitHub
  readback. Native merge identities are "unknown unless separately verified";
  the Mac host, local SQLite corpus/state, generated reports, and deployment
  receipts are outside this worktree.
- Changed: `TODO.md`, `CONTEXT.md`, `HANDOFF.md`, `docs/REPO_PLAN.md`,
  `docs/history/2026-10-10-repository-rationalization.md`,
  `docs/history/2026-10-05-managed-rule-repair-handoff.md` (prior handoff bytes
  preserved). The captured JSON is unchanged.
- Canonical plan: `docs/REPO_PLAN.md` — the only file with the ready-jobs marker;
  one uncovered ready job, all owner-gated/conditional items listed as blocked.
- Runtime acceptance: not established; documentation-only change, no
  code/provider/credential/deploy operation, no native issue created or closed.
- Verification: `PYTHONPATH=work-corpus/src python3 -m pytest -q work-corpus/tests`
  → `283 passed`; ready-jobs marker unique and its JSON parses with one job
  (title ≤120, body ≤1000, checkbox acceptance, `existing_issue: null`); relative
  document links resolve; `git status` clean.
