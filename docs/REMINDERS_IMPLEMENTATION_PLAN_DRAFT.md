# TrojanHorse Reminders implementation plan — draft for G2K adversarial review

## Owner outcome

The owner wants accurate own/delegated reminders by the next morning and a simple
ongoing work-memory loop. Reminders is the working surface. The existing curated
project/participant corpus is the blueprint. No dashboard or complete taxonomy
exercise. Explicit checkbox completion is accepted. A later explicit contradiction
returns the same task as Evidence needed; matching confirmation clears it.

Owner has authorized plan review/revision/final G2K review, implementation and
creation of the resulting work reminders. Optional owner input: unrecorded
completion/cancellation corrections and additions/exceptions to employee scope.
No credentials or rewritten project map are requested.

## Current verified starting point

- Canonical local corpus and copied historical package exist: 35 curated project
  cards, 230-row retained ledger, source pointers/hashes and participant-role context.
- A private blueprint reuses project IDs/aliases. Do not infer that every historical
  card is currently active or promote interpreted copy into independent evidence.
- Isolated task-state API: 46 focused tests pass. It handles owner completion,
  outstanding/confirmed events, old-source replay and persistent tasks; it is not
  wired into live intake or Reminders. Input identity/matching remains upstream.
- Wispr authenticated identity and recent meeting listing work. Screening September
  7 onward finds 30 work meetings, excluding 12 personal/coaching/legal/general
  training entries. Detailed transcripts still need retrieval and interpretation.
- Two exact existing iCloud lists resolve: Mine and Delegated under old Maya names;
  five existing reminders, all completed at discovery. Preserve records and IDs.
- G2K SSH client readiness passes; plan review uses a sanitized generic packet.
  Real private work interpretation must use the g2k-sensitive lane or stay local.
- No TrojanHorse web application or automatic Wispr connector is established.

## Stage A — validated overnight bootstrapping

1. G2K adversarial review of this exact draft, emphasizing omissions, incorrect
   assignment/completion, stale tasks, duplicate effects and practical simplification.
   Retain request hash, full response and receipt. Revise substantive findings,
   submit revised exact plan for final G2K review, and retain the final plan/hash.
2. Fetch complete transcripts for the 30 screened work meetings (bounded date
   window, not a historical full sweep). Preserve original Wispr IDs, event/capture
   dates and pagination ranges. Exclude personal segments from professional task
   interpretation even inside a mixed work meeting. Record coverage and gaps.
3. Interpret work passages in chronological context using the blueprint. Extract
   explicit assignments/promises; owner/person/project context; action; dates;
   evidence; and later confirmation/cancellation. Resolve speaker identity before
   assignment. Unknown ownership remains pending, not silently assigned to owner.
   Divide multi-project meetings into passages. Retrieve a few relevant cards;
   inspect more linked context only for uncertain matches. Do not require project
   classification before a valid own-task can enter the list.
4. Consolidate same commitment across sources, keeping versioned provenance. Match
   completed recent commitments too. Distinguish next occurrence/new scope from
   same unfinished work. A user checkbox is authoritative. Do not reopen the five
   existing completed reminders through historical backfill. Use explicit later
   evidence to resolve older commitments. For genuinely uncertain current status,
   create a clearly labelled confirmation reminder only when the underlying action
   and owner are supported. Never fill a numerical reminder quota.
5. Build a private reminder batch with source excerpts/locators, owner/project,
   title/body, source link, event time, due-date confidence, status and stable key.
   No personal/raw personnel/pay/medical material in reminder bodies. No invented
   deadlines, notifications or recurring schedules. Past promises may show their
   original date in the body, not an invented future due date.
6. Re-read exact lists, existing reminder bodies/IDs and completed states; detect
   matching prior items, service markers and competing writers. Before creating,
   reserve an operation in a private SQLite ledger. Reconcile ID/marker against
   the exact list after any uncertainty, then create/update and read back fields.
   Apply only source-supported new work and clearly labelled status-confirmation
   items. Rename the two existing lists to Trojan-Mine/Trojan-Delegated only after
   verifying identity and writer ownership; if unsafe, use project-owned new lists
   without deleting existing lists and record the choice. No fallback Inbox.
7. Save batch, coverage, source and verified native receipts privately. Report
   actual created/matched/pending/failed counts and known gaps. The next-morning
   deliverable is real verified reminders, not only source/tests/configuration.

## Stage B — smallest ongoing loop

Use one project-owned Mac process and its private state/lock to ingest captured
Wispr updates and pasted inputs, reconcile current tasks and synchronize Reminders.
Reuse a declared available capture path; do not pretend the session-only connector
is an unattended API. Inspect installed Wispr capture/access capability before
choosing a scheduler. If no unattended route exists, implement a resumable capture
inbox consumer first and state the ingestion limitation, while still delivering
Stage A. Source capture, interpretation and effect delivery have separate receipts.

Mirror checkbox changes into authoritative owner events. Suppress projection
echoes using stable task/reminder mapping and last delivered payload. Preserve
completion despite provider downtime. Later matching explicit outstanding-work
statement produces unchecked Evidence needed on that same reminder. A pasted older
email can clear it with a new confirmation event while retaining the email date.
Keep open tasks indefinitely and add recurrence attention without inventing effort.

Only the minimal authenticated paste page/endpoint is needed later at the selected
Cloudflare hostname. Existing Cloudflare authority/placement and release approval
are separate gates; no web deployment is necessary to fill Reminders tonight.
Raw professional corpus remains private. No autonomous contact with colleagues.

## Verification and acceptance

Before real writes: test deterministic state transitions plus idempotent create/
update/complete/retry reconciliation using a fake provider, and validate a few real
source chains against the exact transcript. G2K's plan approval is not source proof.
Then perform real scoped writes and verify exact account/list/item/title/body/date/
completion readback. Retry without creating duplicates. Preserve existing completed
records. Persist pending/failed effects instead of reporting them as delivered.
A natural unattended cycle is required before claiming always-updated operation.
