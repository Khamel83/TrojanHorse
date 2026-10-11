# TrojanHorse repository plan

Single canonical ordered plan for outstanding repository work. This is the only
file in the repository that carries the ready-jobs marker.

- Coordinator (tracking-only): [#16](https://github.com/Khamel83/TrojanHorse/issues/16)
- Audit task: [#17](https://github.com/Khamel83/TrojanHorse/issues/17)
- Captured source base: `66820d3357ecd6a05a57fd214b17a2bfca99d1d7` (`origin/main`, fetched)
- Native intake packet: `docs/reconciliation/intake-2026-10-10.json` and
  `docs/reconciliation/intake-2026-10-10-part-1.json`
  (sha256 `01aecc997b94812d25f3c82ca40eeb3350415343429ced749c61ac45fcc813b8`)
- Full classification, coverage and unknowns:
  [docs/history/2026-10-10-repository-rationalization.md](history/2026-10-10-repository-rationalization.md)
- Reconciled: 2026-10-10 (documentation audit; the packet is dated evidence, not
  live status)

Task prose and acceptance receipts stay in their owning records — `TODO.md`
(checklist and receipts), [REMAINING_WORK.md](REMAINING_WORK.md),
[TROJAN_HORSE_AUDIT.md](TROJAN_HORSE_AUDIT.md),
[LOCAL_WORK_CORPUS_STATUS.md](LOCAL_WORK_CORPUS_STATUS.md) — and
`docs/superpowers/plans/` (executed historical plans). This file owns only
ordering, dependencies, owner decisions, acceptance criteria and proposed
native dispositions; it copies no task prose.

## Why this file is the canonical plan

The audit contract prefers reusing an existing canonical plan. None of the
existing documents is a suitable repo-level ordered plan:

- `TODO.md` is the task checklist with historical acceptance receipts; its
  outstanding items live inside a Janitor-managed block
  (`<!-- janitor:begin:todo -->` … `<!-- janitor:end:todo -->`, lines 271–308 of
  the captured base) that Janitor regenerates, so it is not a stable source for
  a ready-jobs marker.
- [REMAINING_WORK.md](REMAINING_WORK.md) is a dated status map, not a plan with
  dependencies, owner decisions and native dispositions.
- `docs/superpowers/plans/*` are executed historical implementation plans.

Therefore `docs/REPO_PLAN.md` is created as the one canonical plan. The
coordinator [#16](https://github.com/Khamel83/TrojanHorse/issues/16) stays
tracking-only; this audit does not enqueue implementation or change
code/runtime.

## Verified current state (dated)

At the captured source base `66820d33`, the owning records report the archive,
search, deterministic organization and local answer CLI milestones delivered,
with the canonical Mac `com.khamel83.work-corpus-granola-delta` LaunchAgent
installed and supervised. Those are receipts from their own checkpoints
(2026-09-08/09). This audit re-verified none of them: the corpus database,
generated reports and the Mac host are outside this worktree, and native merge
identities are unverified in the packet. No runtime acceptance is claimed here.

Classification of every visible item, with stable source links, is in the
history evidence file. Summary:

| Item | State | Owning record |
| --- | --- | --- |
| Ingestion, exact search, deterministic organization, first pass | claimed complete (receipts not re-verified) | TODO.md Milestones 1–2 |
| Local `answer`/`answer-compare`/`answer-eval` CLI milestone | claimed complete (receipts not re-verified) | TODO.md Milestone 3 |
| Canonical Mac Granola delta maintenance job | claimed deployed and supervised | LOCAL_WORK_CORPUS_STATUS.md |
| Broader answer-evaluation inspection | remaining | TODO.md:62, REMAINING_WORK.md:161, TROJAN_HORSE_AUDIT.md:200 |
| Optional web/API or UI layer | remaining (owner decision) | REMAINING_WORK.md:165, TROJAN_HORSE_AUDIT.md:204 |
| Topic labels / person-org aliases / 52 Zoom linkage states | remaining (optional) | TODO.md:65, TROJAN_HORSE_AUDIT.md:210 |
| Semantic ranking / embeddings | remaining (optional, gated) | TODO.md:68, TROJAN_HORSE_AUDIT.md:212 |
| Test coverage in lower-covered modules | remaining | TROJAN_HORSE_AUDIT.md:214 |
| Empty legacy SQLite tables | remaining (owner migration decision) | TROJAN_HORSE_AUDIT.md:216 |
| Granola MCP shadow gaps | remaining (conditional) | TROJAN_HORSE_AUDIT.md:218 |
| Closed Star Opportunity proposals #1, #2 | closed, no adoption evidence | issues 1, 2 |
| Janitor docs projections #3–#15 | complete/merged (#13 superseded) | PRs 3–15 |

All source links below use the captured base
`66820d3357ecd6a05a57fd214b17a2bfca99d1d7` so they remain stable as this
worktree changes.

## Ordered plan

### Track 0 — repository rationalization (this audit)

- **A1** — Merge this reviewed documentation PR (only `TODO.md`, `CONTEXT.md`,
  `HANDOFF.md`, `docs/REPO_PLAN.md`, and Markdown under `docs/history/` plus the
  captured intake packet).
  - Dependency: trusted exact-head plan review PASS.
  - Owner decision: none outstanding; the owner authorized this single
    documentation reconciliation.
  - Acceptance criteria: review PASS on the exact head; the ready-jobs marker
    parses; only the allowed paths changed; the captured JSON is byte-identical
    to its manifest hash.
  - Disposition: source-only; it does not establish runtime acceptance and does
    not close any implementation item.
- **A2** — After A1 merges, G2K may link existing ready issues and admit at most
  one finite batch for uncovered ready jobs through its ready-jobs contract
  (see the batch below). The coordinator [#16](https://github.com/Khamel83/TrojanHorse/issues/16)
  remains parked/tracking-only.

### P0 — no open blocker

The maintenance timer is reported active in the owning records. No P0 item is
open in this audit; runtime state was not re-verified here.

### P1 — remaining product work (owner-gated or manual)

- **R1 — Broader answer-evaluation inspection.**
  - State: remaining. Source: [TODO.md:62](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/TODO.md#L62),
    [REMAINING_WORK.md:161](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/docs/REMAINING_WORK.md#L161),
    [TROJAN_HORSE_AUDIT.md:200](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/docs/TROJAN_HORSE_AUDIT.md#L200).
  - Dependency: the local corpus and its generated reports; none of that state
    is in this worktree.
  - Owner decision: none; this is manual owner/human review.
  - Acceptance criteria: each returned source/version locator checked against
    the local source; unsupported claims, missing citations, date errors and
    conflict handling recorded.
  - Disposition: keep in TODO as the top remaining owner-review item; no native
    issue.

- **R2 — Optional web/API or UI layer over the CLI.**
  - State: remaining. Source: [REMAINING_WORK.md:165](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/docs/REMAINING_WORK.md#L165),
    [TROJAN_HORSE_AUDIT.md:204](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/docs/TROJAN_HORSE_AUDIT.md#L204).
  - Dependency: R1 evidence that the CLI is insufficient for a real need.
  - Owner decision: required — prioritize only if its operational value is
    clear; raw text must stay local and the sanitized gateway boundary retained.
  - Acceptance criteria (if approved): every answer keeps source locators; raw
    packets never leave the Mac; the existing sanitized comparison boundary is
    preserved and tested.
  - Disposition: not ready — owner-gated scope decision; no native issue.

### P2 — optional refinement

- **R3 — Refine 48 generic topic labels, person/organization aliases and 52
  Zoom linkage states.** Source: [TODO.md:65](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/TODO.md#L65),
  [TROJAN_HORSE_AUDIT.md:210](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/docs/TROJAN_HORSE_AUDIT.md#L210).
  Dependency: core views in use. Owner decision: "if useful" — required.
  Acceptance: aliases carry source locators; no identity inferred from a title
  alone; raw files untouched. Not ready — owner-gated and needs the local corpus.
- **R4 — Semantic ranking/embeddings.** Source: [TODO.md:68](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/TODO.md#L68),
  [TROJAN_HORSE_AUDIT.md:212](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/docs/TROJAN_HORSE_AUDIT.md#L212).
  Dependency: measured need from exact search. Owner decision: required.
  Acceptance: local-data boundary preserved. Not ready — gated on measured need.
- **R5 — Test coverage in lower-covered modules.** Source: [TROJAN_HORSE_AUDIT.md:214](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/docs/TROJAN_HORSE_AUDIT.md#L214).
  Dependency: none. Owner decision: none. Acceptance: focused tests for
  `normalize`, `granola_api`, `transcription`, `doctor` asserting
  consumer-visible behavior; the active suite passes; no runtime/provider
  change. **Ready** — see the batch below (`existing_issue: null`).
- **R6 — Remove empty legacy SQLite tables.** Source: [TROJAN_HORSE_AUDIT.md:216](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/docs/TROJAN_HORSE_AUDIT.md#L216).
  Owner decision: required — separate migration decision. Not ready.
- **R7 — Complete the Granola MCP shadow.** Source: [TROJAN_HORSE_AUDIT.md:218](https://github.com/Khamel83/TrojanHorse/blob/66820d3357ecd6a05a57fd214b17a2bfca99d1d7/docs/TROJAN_HORSE_AUDIT.md#L218).
  Dependency/condition: only if it serves a use case not covered by REST.
  Owner decision: required. Not ready — conditional; REST coverage is complete.
- **R8 — Re-evaluate closed Star Opportunity proposals.** Source:
  [#1](https://github.com/Khamel83/TrojanHorse/issues/1),
  [#2](https://github.com/Khamel83/TrojanHorse/issues/2). Both closed
  2026-09-23 with no adoption, merge or implementation evidence in the packet.
  Owner decision: required to reopen. Not ready.

Explicitly deferred by existing policy (not jobs): mailbox access, Atlas
integration, cloud raw-data processing, graph/vector infrastructure, automatic
historical task backfill, polished career-document generation, and provider
write-back — see `TODO.md` "Explicitly deferred features" and
[adr/0001-local-work-corpus-boundary.md](adr/0001-local-work-corpus-boundary.md).

## Proposed native issue dispositions

| Native | Kind | Classification | Proposed disposition |
| --- | --- | --- | --- |
| [#17](https://github.com/Khamel83/TrojanHorse/issues/17) | issue (open) | audit task | Complete when this documentation PR merges (source-only). The orchestrator/Janitor closes it; no runtime change. |
| [#16](https://github.com/Khamel83/TrojanHorse/issues/16) | issue (open) | coordinator | Keep open, parked/tracking-only. No change; it stays the one tracking record. |
| [#15](https://github.com/Khamel83/TrojanHorse/pull/15), [#14](https://github.com/Khamel83/TrojanHorse/pull/14), [#12](https://github.com/Khamel83/TrojanHorse/pull/12), [#11](https://github.com/Khamel83/TrojanHorse/pull/11), [#10](https://github.com/Khamel83/TrojanHorse/pull/10), [#9](https://github.com/Khamel83/TrojanHorse/pull/9), [#8](https://github.com/Khamel83/TrojanHorse/pull/8), [#7](https://github.com/Khamel83/TrojanHorse/pull/7), [#6](https://github.com/Khamel83/TrojanHorse/pull/6), [#5](https://github.com/Khamel83/TrojanHorse/pull/5), [#4](https://github.com/Khamel83/TrojanHorse/pull/4), [#3](https://github.com/Khamel83/TrojanHorse/pull/3) | PR (closed) | completed Janitor documentation projections (`merged_at` set in the packet) | No action; retained as evidence. Merge commits were not independently re-verified. |
| [#13](https://github.com/Khamel83/TrojanHorse/pull/13) | PR (closed, not merged) | duplicate/superseded | Superseded by [#14](https://github.com/Khamel83/TrojanHorse/pull/14): identical title and identical body sha256 `19f38f8b2ba6d609c7c9797ff952b927d375954c4f727b394bec237348b08134`, merged later the same day. No action. |
| [#2](https://github.com/Khamel83/TrojanHorse/issues/2) | issue (closed) | closed, not adopted | Star Opportunity proposal (humanizer). No implementation, merge or adoption evidence. Reopen only on explicit owner decision. |
| [#1](https://github.com/Khamel83/TrojanHorse/issues/1) | issue (closed) | closed, not adopted | Star Opportunity proposal (plan-scoped subagent development). No implementation, merge or adoption evidence. Reopen only on explicit owner decision. |

## Ready job batch

Admission rule: after trusted exact-head review and merge of this plan, G2K
links existing ready issues and admits at most one finite batch of uncovered
ready jobs. Nothing here is a native issue; the audit itself creates none. Jobs
needing an owner/access/deploy gate are excluded above. Only one item is
independently ready.

<!-- g2k:ready-jobs:v1 -->
```json
{"jobs": [{"title": "Raise test coverage in lower-covered work-corpus modules", "body": "- [ ] Add focused tests for the lowest-covered modules named in docs/TROJAN_HORSE_AUDIT.md: `normalize`, `granola_api`, `transcription`, and `doctor`.\n- [ ] Each new test asserts consumer-visible behavior (parsing outcomes, retry/terminal accounting, checkpoint handling, doctor checks), not wiring or mock echoes.\n- [ ] `PYTHONPATH=work-corpus/src python3 -m pytest -q work-corpus/tests` passes, and existing tests are not re-pinned to incidental behavior.\n- [ ] No runtime, provider, corpus-data or secret change; raw files and ignored state stay untouched.\nOwning record: docs/TROJAN_HORSE_AUDIT.md (P2, lower-covered modules) at base 66820d3357ecd6a05a57fd214b17a2bfca99d1d7.", "source": "docs/TROJAN_HORSE_AUDIT.md P2 bullet (TROJAN_HORSE_AUDIT.md:214 at 66820d3357ecd6a05a57fd214b17a2bfca99d1d7)", "existing_issue": null}]}
```

## Coverage, omissions and unknowns

- Read: the manifest and the single captured part (17/17 records; 2 open,
  15 closed). No part was omitted (`omitted: []`), and the part's sha256 matches
  the manifest. The packet covers full bodies for both open issues, the open
  issue comment, and closed records since 2026-07-12 only.
- Not verifiable in this worktree: native merge identities ("unknown unless
  separately verified" in the packet), live issue/PR state, the Mac launchd job,
  the local SQLite corpus and generated reports, and any deployment receipt.
- The `g2k-workspace` helper was unavailable in this session (module resolution
  error), so no live GitHub readback was performed; classifications rest on the
  captured packet plus tracked repository files.
- Unknowns and unresolved acceptance stay open; this audit closes no
  implementation item and claims no runtime acceptance.
