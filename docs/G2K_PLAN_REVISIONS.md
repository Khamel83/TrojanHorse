# G2K adversarial review revision record — 2026-10-06

The initial tool-free request returned tool-call markup without a verdict; it is
retained as an invalid review. The explicit text-only retry returned REVISE.
Full raw requests/responses/hashes are private in the worktree's private-review/.

| Finding | Revision |
| --- | --- |
| List rename/collision risk | New project-owned lists; Maya records read-only; no rename/move/delete |
| Vague item/writer identity | Stable reconciled task ID, persisted native/list IDs, operation marker/ledger, one writer; unmarked matches pending |
| Evidence needed conflated with initial uncertainty | Two task states, each on one existing reminder; never duplicate confirmation objects |
| Past due dates unspecified | Original past promise only in body; no invented future dates or notifications |
| Owner edits could be overwritten | Compare last delivered state, preserve edited fields, conflict ledger; update unchanged managed fields only |
| Sensitive transcript processing unclear | Local retrieval/storage/interpretation; any remote work-content call uses sensitive route; generic plan review has no transcripts |
| Coverage overclaim | Explicit placed/matched/pending/excluded/source gaps; no completeness/always-updated claim |
| Pre-existing item changes | Maya records and unrelated existing reminders read-only; no broad cleanup |

The reviewer suggested a dedupe key including native UID and source excerpt hash.
The revision keeps UID/list/source hashes for receipts, but uses a stable task ID
before a UID exists; a source excerpt can change without changing the commitment.
The reviewer suggested only completion-bit updates. The revision preserves owner
edits while allowing status/context updates to unchanged project-managed fields,
which is necessary to display Evidence needed on the same reminder.
The reviewer conflated provider route with source retrieval host. The revision
states local Wispr capture and any sensitive remote interpretation separately;
no default G2K route receives work transcripts. These are reasoned modifications,
not silent acceptance of technically incorrect suggestions.

Final review applies to the exact final plan document/hash, not this commentary
or the confidential candidate batch. Native readback remains separate acceptance.
