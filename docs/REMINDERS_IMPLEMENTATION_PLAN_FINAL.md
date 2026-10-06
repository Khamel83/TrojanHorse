# TrojanHorse Reminders implementation plan

Version 2 — revised after G2K adversarial review, 2026-10-06.
Final-review status and exact plan hash are recorded separately in the review receipt.

## The first deliverable

Populate two project-owned Apple Reminders lists with source-backed work drawn
from recent Wispr meetings: Trojan-Mine and Trojan-Delegated. The supplied 35-card
project/participant blueprint supplies context. The owner supplied five employees,
spelling variants, boss and boss's boss; the private roster is the assignment scope.
Other people's tasks are retained as context, not assigned to the owner's lists.
The owner will correct unrecorded completions tomorrow; no further input is required.

Reminders is the task interface. No dashboard, broad taxonomy redesign or full
historical sweep. No quota: publish only attributable work, with uncertainty visible.

## What tonight covers

Thirty work meetings from September 7 onward, screened from 42 entries. Personal,
coaching/legal and generic training entries are excluded. Use complete transcript
ranges, retaining original provider ID, actual event time, capture time and hash.
Personal segments within work meetings stay out of work interpretations/reminder
bodies. Sources remain private on the Mac. Local source interpretation is allowed;
any remote professional-content interpretation must use the sensitive G2K route.
Normal G2K plan review receives only generic design and verified counts, no private
transcripts. Provider route choice does not replace source evidence verification.

The overnight deliverable is one reconciled bootstrap batch, with verified native
readback and a coverage report. It does not establish continuous Wispr collection.

## Review sequence

Retain the first adversarial G2K verdict/findings. Revise the plan and record how
each material finding was addressed. Submit this exact revised document for final
G2K review. Retain request/plan hashes, response and verdict. Implement only after
an explicit usable approval. A malformed response or attempted tool call is not
approval and must be recorded as such. G2K reviews this plan, not confidential
sources or source accuracy. No reviewer tools or external actions are needed.

## Interpretation and task identity

Use each incoming substantive passage with a few relevant existing cards. Match
owner, action/object, recipient/context and relevant episode, not just words.
Split multi-project meetings. Inspect additional linked context only for uncertain
matches. No project ID or requester classification is required to create a task.
Use contextual roster aliases, not unrestricted fuzzy identity merging.

Read later source evidence before deciding whether an earlier promise is current.
Retain completion/cancellation facts and consolidate repeated commitments. A newer
request for another version or recurring period is distinct from unfinished old
work. If a task's current status is unknown after source review, its one reminder
is prefixed “Confirm current status”; no duplicate confirmation task is created.
Uncertain ownership or source attribution is held out, with a reason in coverage.
Preserve old promised dates in the body; all bootstrap reminders have no due date
or notification unless a clear future date is supported. Never invent a new date.

Stable task IDs are assigned to reconciled commitments. Once assigned, new source
references attach to the same ID. Each native operation has a stable marker derived
from project namespace, task ID and operation ID. Source excerpt hashes support
reconciliation but are not the task's identity: wording and later sources can change.
Store exact evidence substrings/locators and verify them against the retained source
before any native write. A title/action is a close paraphrase, never a fabricated
promise. Exclude employee-level pay, health, adverse personnel/case details and
family/private context from native title/body; retain concise business context.

## Native lists and effects

Create or reuse the exact project-owned Trojan-Mine/Trojan-Delegated lists in the
confirmed iCloud account. If duplicate names or conflicting identities exist,
stop the affected operation rather than selecting the first name. Save account/list
UIDs and use them thereafter. Existing Maya lists and their five completed reminders
are read-only: no rename, move, deletion or reopening during bootstrap.

Read the exact target lists, including completed items, before creating. A known
mapping or stable task marker identifies an existing item. An unmarked plausible
match is logged pending rather than automatically claimed or overwritten. Reserve
the task operation in a private SQLite ledger before the provider call; store its
payload hash, request, attempt state and native ID. After timeout/error, reconcile
by UID/marker before retry. Multiple/conflicting matches become uncertain, not a
second create. Native markers are not uniqueness constraints; one project writer
and reconciliation enforce retry safety.

For each write, read back account/list/item identity and title/body/completed/date
fields, then persist verified receipt. Failure remains failed/uncertain; it is not
counted as delivered. No fallback Inbox. No deletion or movement of pre-existing
items. Rollback is targeted by created UID, never a broad list reset; any cleanup
requires its own justified action. Save source/batch/coverage/receipt files privately.

## The completion loop

| Event | Effect on the same task/reminder |
| --- | --- |
| Owner checkbox or explicit done | Completed immediately, no proof demanded |
| Later clearly matched outstanding-work statement | Unchecked, Evidence needed |
| Matching supplied confirmation | Completed; original source date retained separately from confirmation time |
| Old meeting replay or mere repeated mention | No reopening |
| New requested version/recurring instance | New linked commitment, old completion retained |

Evidence needed is a task state reflected in one reminder, not a second reminder
object. It is distinct from initial Confirm current status. Completion confirmation
says nothing about deliverable quality. A paste can confirm with an older email;
an unknown email date stays unknown. Count distinct events, not imported copies.

Native field ownership: compare readback with last delivered payload. Owner edits
to title/body/due date are preserved, never automatically overwritten. On unchanged
managed fields, the bridge may update the status prefix/context and completion bit.
On conflict, retain a ledger conflict and preserve edited fields; do not manufacture
another reminder. Manual checkbox changes become explicit owner events before sync,
so projection echoes and source replay cannot undo them. Provider outage cannot
undo task completion. This continuous loop requires separate source and installed
caller acceptance; the bootstrap receipt alone does not prove it.

## Implementation order and verification

1. Final G2K review, complete local source capture, chronological extraction and
   owner-scoped reconciliation using the supplied blueprint.
2. Implement/test an idempotent native adapter/ledger and private bootstrap command.
   Test fake-provider retry, ambiguous/multiple markers, owner edits, date handling
   and completion cycle, alongside the existing deterministic task-state tests.
3. Validate real candidate excerpts and identity/context. Create/reuse the two
   project-owned lists; deliver the qualified batch; read back every actual item.
4. Report placed, already matched, pending and excluded counts with source/date
   coverage and failures. Retain the final plan and both G2K review receipts.
5. Continue with a project-owned capture/paste inbox consumer and Reminders checkbox
   reconciliation. Inspect unattended Wispr access first; a session connector is
   not a daemon API. If absent, deliver the verified bootstrap and state this gap.
   Do not claim always-updated intake from a configured timer or manual capture.
6. Later, publish only the minimal Cloudflare-authenticated paste page/endpoint
   through the existing release authority. No web deployment is required tonight.

Acceptance tonight: actual source-grounded reminders in the two lists, accurate
assignment scope, visible unknown status, preserved prior completed items, durable
readback receipts, and truthful coverage. No autonomous contact with colleagues.
