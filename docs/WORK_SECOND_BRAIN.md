# TrojanHorse: keep the work to-do lists current

Owner clarification: 2026-10-05. This narrows the first release to Apple Reminders
and a simple authenticated paste input. The broader historical work memory stays
behind it; dashboards and separate project/people web views are deferred.

## Everyday behavior

Omar checks Reminders to know what is outstanding: his work in Trojan-Mine and
employee assignments in Trojan-Delegated. Wispr meetings and pasted email/Slack
supply information automatically. Asking questions is optional.

| Input | What happens to the same task |
| --- | --- |
| Clear new commitment or assignment | Appears as open in the correct list |
| Omar checks it off or says done | Completed immediately; no proof requested |
| Later meeting clearly says that completed work is still outstanding | Returns unchecked, labelled “Evidence needed” |
| Matching email, Slack or meeting confirmation supplied | Completed; confirmation retained |
| Old recording is imported later, or work is merely mentioned again | Does not undo completion |
| Unclear reference or a different employee's work | Does not change an unrelated task |

Confirmation establishes completion only. Do not assess the deliverable, work
quality, business success or manager satisfaction. There is no routine verification
burden when Omar checks a task off. If later evidence contradicts it, surface the
specific reference in that same reminder and let him supply confirmation. Another
explicit owner completion is still accepted immediately.

A pasted older email can resolve a newer contradiction. Retain the original
message date separately from the date confirmation was supplied; never relabel
an old meeting as new merely because it was captured later. An unknown original
message date stays unknown and does not require guessing.

## What gets built first

`Wispr / pasted messages -> source-cited task updates -> Reminders`

Reuse existing source/version storage and task identity. A small LLM interpretation
step matches commitments, people and later confirmations to the right task.
Deterministic logic handles state, duplicate inputs, dates and reminder delivery.
A task can enter the list without a project classification or identified requester.
Open tasks remain open until resolved; they do not expire after fourteen days.
Retain the original text and all task transitions quietly for future usefulness.
Historical archive import does not resurrect every old promise as open work.

Reminders is the working surface. The only new web surface needed now is an
Access-authenticated paste box, preferably at trojan.khamel.com, with a submission
receipt. No dashboard, new project browser or general chat interface is required.
Links back to source context are useful, but building a hosted archive browser is
not a prerequisite for a correct list.

Use one reminder per task with a stable mapping. An “Evidence needed” task is
unchecked with that label and a short reference to the contradicting meeting in
its body. Keep its identity and previous confirmation. Synchronize manual checkbox
changes back into task state. Provider retries must not create duplicates or
turn projected checkbox changes into new user instructions.

The existing Maya lists must retain their history and exact identities during
cutover. Reconcile the prior writer before enabling TrojanHorse's writer. Existing
read-only discovery found five reminders, all completed; no native writes have
been made. Exact IDs and receipts remain private.

## Delivery sequence

1. Task transitions: open -> done -> evidence needed -> confirmed done. Verify old
   imports, duplicate input, wrong-task references and manual owner completion.
2. Wire new Wispr content and a durable paste input to those transitions. Verify
   one real commitment and one later confirmation without manual extraction.
3. Wire the Mac Reminders adapter and manual checkbox feedback. Verify the same
   task is created, completed, returned as evidence needed, and cleared by pasted
   confirmation, including a provider outage/retry without duplicates.
4. Release only the authenticated paste endpoint/page through the existing
   Cloudflare deployment path. Verify signed-in submission durability and denial
   of unauthorized requests. No dashboard is part of acceptance.

Acceptance is a current to-do list: meeting creates the right task, checking it
completes it, a later explicit contradiction asks for confirmation, pasted
confirmation clears it, and all changes remain attached to the same task.

## Verified state and remaining wiring

Historical package intake remains verified and preserved. The isolated task-state
API now supports the confirmation cycle. Its 36 tests plus 10 existing task tests
pass; focused Ruff passes. It is not yet initialized in the live corpus, connected
to Wispr/LLM intake or connected to Reminders. No Cloudflare deployment or list
cutover has occurred. Those are the next implementation steps, not capabilities
established by this document. Existing infrastructure inspection has no declared
TrojanHorse runtime host; deployment placement remains an implementation gate.
