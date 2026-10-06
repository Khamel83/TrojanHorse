# LLM overview — TrojanHorse

Updated 2026-10-06. Read AGENTS.md and HANDOFF.md before editing. This briefing
summarizes verified source/runtime boundaries; it grants no additional authority.

TrojanHorse is Omar's work second brain: live Wispr and pasted email/Slack should
maintain projects, people and own/delegated tasks in Apple Reminders. No dashboard
is required. The historical professional corpus supplies the project blueprint.

## Verified implementation and effects

- Active code is Python/SQLite under work-corpus/src/work_corpus/. Legacy root
  TrojanHorse/, bridge/ and Atlas lanes are historical, not this runtime.
- Immutable source/version storage, local normalization/search/answer and provider
  capture ingestion already exist. Raw sensitive material stays outside Git.
- The supplied package intake retained 116 files, 108 normalized documents,
  35 project definitions and 20 H001 aliases; no historical card rewrite.
- work_state.py implements deterministic source/owner events and task projection.
- reminders_bridge.py reserves effects before native writes, reconciles markers,
  binds exact account/list/item IDs and verifies payloads. Owner edits are preserved.
- scripts/bootstrap_reminders.py validates a reviewed private source batch and
  delivers it. Thirty recent work meetings produced 24 verified reminders:
  Trojan-Mine 12, Trojan-Delegated 12; seven ask to confirm current status.
- G2K requested plan revisions, then approved the exact revised plan. 59 focused
  tests pass, plus Ruff/diff checks. Plan approval is not semantic certification.
- Source branch feature/work-second-brain is pushed and unmerged. Native effects
  are delivered on the authorized Mac. No Cloudflare site, unattended Wispr
  consumer, pasted-message endpoint or installed checkbox feedback is active.

## Behavioral authority

Owner done/checkbox means done immediately. Later explicit outstanding evidence
about the same work returns that same task as Evidence needed; matching confirmation
clears it. Older confirmation supplied now may be used while retaining its source
date. Old replay or mere mention does not reopen work. Open tasks do not expire.
Newer event information defaults authoritative; capture date is not event date.
New scope/recurrence is distinct linked work. Maya migration is out of scope.

Use the owner-provided roster and contextual spelling variants. Do not guess
identity from a diarization label. Keep execution, supervision and participation
separate. Use OWNER_RECENCY_ADDENDUM.md and private owner overrides for corrections.

## Restart and validation

Read TODO.md, CONTEXT.md, HANDOFF.md, docs/WORK_SECOND_BRAIN.md and the immutable
G2K-approved docs/REMINDERS_IMPLEMENTATION_PLAN_FINAL.md. Private sources, batches,
IDs, review responses and receipts are under canonical
work-corpus/corpus/reports/work-brain-bootstrap-20261006/.

```bash
PYTHONPATH=work-corpus/src pytest -q --no-cov work-corpus/tests/test_reminders_batch.py work-corpus/tests/test_reminders_bridge.py work-corpus/tests/test_work_state.py work-corpus/tests/test_tasks.py
```

Do not blindly rerun the initial batch after owner changes. Reconcile its reserved
IDs and last payload; never overwrite completion to reproduce a bootstrap receipt.
Next prove installed-caller access, natural new-source delivery and checkbox-to-ledger
feedback. Earlier Granola scheduler receipts do not establish unattended Wispr access.
