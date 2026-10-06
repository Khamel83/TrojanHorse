# TrojanHorse work second brain

Owner decision: 2026-10-05. This supersedes the provisional professional-memory
product direction. Historical evidence export remains a supported output.

## Purpose and normal use

TrojanHorse continuously maintains Omar's work memory: projects, decisions,
responsibilities, people, his commitments and employees' assigned work. It takes
Wispr Flow meeting content and manually pasted emails or Slack messages. Omar
should not have to ask a question to make the system notice a commitment or keep
lists current. Search and the professional evidence export are secondary uses.

The preferred front door is `trojan.khamel.com`, authenticated through the
existing Cloudflare infrastructure, with a simple Cloudflare Pages interface.
Use a dedicated hostname rather than changing the existing apex site. Start with
a paste box, Mine, Delegated, Projects, and source/context links. Save a durable
receipt immediately; show queued/processed/failed state. Automatic intake must
keep working without the page open. Direct email and Slack connectors are not
required for the first release; copy/paste is the requested interim path.

## The operating rules

- “I'll send that on Tuesday” creates a commitment with the correct assignee,
  requester, project, due date and source passage. Resolve Tuesday from the actual
  meeting date/time zone, not the later import date. Unclear dates stay unset.
- Explicit owner “done” completes the matched task. It is authoritative; the
  system does not request additional proof or wait for a manager to agree.
- Later emails, delivered work, and manager acknowledgments can complete a task
  automatically when the referenced deliverable and task match clearly. General
  praise or an ambiguous “thanks” must not complete unrelated tasks. Uncertain
  matches appear in a small exception queue; routine clear matches need no review.
- Work assigned by Omar or others to an employee belongs in Delegated. Work Omar
  owns belongs in Mine. Accountability and execution ownership are separate.
- Open commitments do not expire after fourteen days. Historical import does not
  automatically resurrect every old promise as current work. Establish the live
  baseline from existing task lists and explicitly live commitments.
- Repeated meetings, forwarded emails and aliases can add evidence to one task;
  they do not create another task merely because a new file was captured.
- Preserve changes as events. An old transcript or stale model interpretation
  cannot reopen work Omar completed. Explicit owner reopening can reopen it.
- Every task and project update retains original source identity/version, passage,
  event time and capture time. Projects retain proposed/approved/implemented and
  outcome distinctions and Omar/staff attribution. Preserve corrections and
  counterevidence, including the separate Shoah and Libraries responsibilities.
- Resolve people using retained names/aliases and source context. Existing records
  are a starting directory, not proof that every colleague or identity is known.
  Ambiguous names remain unresolved instead of being merged by a language model.

## Simple architecture

`Wispr delta / paste inbox -> immutable source -> structured interpretation ->
validated events -> current projects and tasks -> Reminders + private web views`

Reuse the existing inventory, source versions, people/project entities and source
search. Preserve provider identities and reviewed-passage records. The LLM handles
meaning: who promised what, which project it belongs to, whether a later message
satisfies it, and whether two mentions describe the same work. It proposes a
bounded structured event with cited text. Deterministic code validates identity,
source/locator, date, transition, duplicate handling and delivery. Extraction must
not grant the model unrestricted writes to Reminders or production configuration.

Pages hosts the simple interface; server-side Functions can accept submissions.
Cloudflare Access must protect API and context routes as well as the page, including
alternate deployment URLs. Validate authorization at the processing boundary;
trusting an unverified client identity header is insufficient. Use the existing
account and credential inventory. No API keys in browser code. Cloudflare provides
submission durability before acknowledgement; a private consumer retrieves inputs
and processes them asynchronously. Select the smallest queue/storage binding after
account/deployment discovery. Never publish the full archive as static assets.

The existing large local corpus remains private; the website serves authenticated
context views with opaque identifiers through a declared service route. The Mac
owns native Reminders effects; the declared production service owns ingress and
work-state processing. Core-host placement and corpus-read access still require
an explicit deployment design: the infrastructure catalog currently records no
TrojanHorse runtime host. Do not expose a Mac development server as production.

Cloudflare references checked for this design:
[Pages Functions](https://developers.cloudflare.com/pages/functions/) and
[Access JWT validation](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/).
These establish available mechanisms, not a deployed TrojanHorse route.

## Reminders behavior and Maya migration

Use `Trojan-Mine` and `Trojan-Delegated` as the intended list names, bound to exact
account/list IDs. Inventory the existing Maya lists and task IDs first. Preserve
reminder bodies, dates, completion state, unrelated entries and provenance links.
Reuse existing records when transferring ownership; do not delete/recreate lists
or blindly replay the historical archive. Reconcile any other active reminder
writer before cutover so two systems do not update the same tasks.

Each task has one stable reminder mapping. Queue create/update/complete effects
with stable operation IDs; reconcile timeouts by reminder ID/marker and verify
readback before retry. Task completion and Reminders delivery are separate states:
a provider outage must not undo Omar's completion. Links open the original Wispr
item where available or the authenticated TrojanHorse context page. A reminder
Omar marks done manually feeds back an explicit owner-completion event. Suppress
projection echoes so they cannot become new assignments or completion events.

Native shell permission does not prove unattended worker permission. Bind and
verify the installed Mac caller before enabling automatic delivery. Read-only
list discovery and exact migration are separate from enabling the writer.

## Implementation order and acceptance

1. Persistent task events and transitions. Test assignment Tuesday, completion
   Thursday, duplicate imports, employee ownership, old-source replay, owner done,
   reopening and unresolved acknowledgments. Preserve all existing corpus tables.
2. Durable paste intake and the Wispr delta consumer. Version/capture sources,
   interpret into validated events, resolve identities and preserve failures for
   retry. Verify a new real meeting flows without manually invoking extraction.
3. Current Mine/Delegated/Projects views and private context pages. Verify an email
   paste updates the right task and does not inflate the project count.
4. Reminders reconciliation and controlled Maya ownership migration. Verify one
   real create, update and completion by exact IDs, plus offline/retry behavior;
   then verify a manual completion flows back without a loop.
5. Authenticated Pages release at the selected hostname through the reviewed
   deployment path. Verify unauthorized requests and alternate hostnames fail,
   signed-in paste is durable, context links work, and the end-to-end process
   handles a worker outage. Record deployed identity and downstream receipts.

Release acceptance is the owner's actual workflow: a new meeting creates the
correct Mine/Delegated task automatically; a later pasted email or meeting closes
it; Reminders agrees; one click returns to the cited context. A new question-answer
benchmark or another whole-history sweep is not a prerequisite for this workflow.

## Current evidence and limitations

The historical complete package was imported and retrieval-verified separately.
The existing answer CLI is useful but does not satisfy this proactive requirement.
Existing task proposals are regex-based, source-scoped and not a live event ledger.
Current source inspection has not established an automated Wispr delta job or a
TrojanHorse Cloudflare application. No production deployment or Reminders cutover
is established by this plan. The first bounded task-state API is implemented independently of the existing
live corpus: 25 new and 10 existing task tests pass, with focused Ruff checks.
It retains validated events and review outcomes, but does not authenticate input,
extract from text, run an LLM, populate people, or write to providers. Its
initialization has not been run against the live database.
