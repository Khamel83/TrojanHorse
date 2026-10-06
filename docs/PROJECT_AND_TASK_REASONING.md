# Project and task reasoning — design review before further implementation

Owner direction, 2026-10-05: investigate Reflex and think through the probabilistic
identity/scope decisions before building further. Reminders remains the working
surface. This is a design proposal, not an activated policy or provider integration.

## What was inspected

Reflex origin/main was fetched at `3b86410e8847666cbfff79f61c7a7a0fbc56d660`.
Reviewed its README, design, runner, registry, resolution policy, project-routing,
candidate-reranking and grounding profiles, provider contract and evaluation guide.
The dirty Reflex checkout was preserved; fetched/runtime code matches the inspected
checkout, while intervening remote changes were working documentation only.
No Reflex changes, provider calls or sensitive-data transfers were made.

Reflex accepts versioned typed questions, bounded evidence and caller-supplied
candidates. It preserves distributions and request provenance. Choice resolution
is deterministic caller policy with explicit thresholds; the repository provides
no validated production thresholds. It does not extract a new project record,
retrieve candidates, authenticate evidence or mutate tasks by itself. The current
project-routing profile's __new_repo__ means review for a software repository;
it must not be repurposed as “create a USC work project” without a new profile.
Custom versioned profiles are supported. The current client sends state and
candidate descriptions to OpenRouter; a local dependency is not local inference.
A private-data processing route must be resolved before any real USC calls.

Source pointers, pinned to the inspected commit:
- https://github.com/Khamel83/reflex/blob/3b86410e8847666cbfff79f61c7a7a0fbc56d660/README.md
- https://github.com/Khamel83/reflex/blob/3b86410e8847666cbfff79f61c7a7a0fbc56d660/src/reflex_jev/runner.py
- https://github.com/Khamel83/reflex/blob/3b86410e8847666cbfff79f61c7a7a0fbc56d660/src/reflex_jev/profiles/project-routing.json
- https://github.com/Khamel83/reflex/blob/3b86410e8847666cbfff79f61c7a7a0fbc56d660/docs/evaluation.md
- https://github.com/Khamel83/reflex/blob/3b86410e8847666cbfff79f61c7a7a0fbc56d660/docs/provider.md

## The hard problem

The implemented task-state reducer begins AFTER the hard interpretation has
already happened: a task ID, person identity, event relation and provenance are
supplied by the caller. Its passing tests do not establish that a real meeting
will be assigned to the right project or close/reopen the right task. The missing
semantic contract must be settled before wiring it to a provider or Reminders.

A short active project list improves the candidate problem. It does not solve
identity alone. The same people discuss several projects; the same deliverable
name can recur; one meeting can concern several projects. Time is strong context,
but a late email about a finished project must still be reachable. Retrieve the
active candidates plus relevant recently closed/historical matches, not all 35
historical cards every time and not only currently open tasks.

## Proposed project boundary

A project is a coherent work outcome with a distinguishable scope and lifecycle,
not a meeting series, department name, common participant or shared keyword.
Maintain a compact internal description: intended outcome, inclusion/exclusion
boundaries, sponsor/participants when known, lifecycle/time window and known
aliases/deliverables. No new dashboard is needed to retain this context.

Examples (hypothetical, not new archival claims): a tuition-policy analysis and
an offboarding-recovery effort can share finance stakeholders but have different
outcomes. A later annual policy update can be a new episode linked to the previous
work rather than rewriting the old episode. Routine ongoing work needs a stable
operating bucket; not every task requires inventing a project.

Split a meeting into substantive passages before routing. A passage can match an
existing project, establish a genuinely new outcome, describe ongoing routine work,
or remain unclear. One explicit new mandate can establish a provisional project;
repetition is corroboration, not an arbitrary two-meeting admission rule. Preserve
why it was created. Subsequent context can confirm, rename, merge aliases or split
its scope without rewriting raw sources or losing old IDs. A task may also remain
unclassified while still appearing in the correct to-do list.

## Proposed task identity

Match the commitment, not the sentence: responsible person, expected action or
result, recipient/object, project/context and relevant episode or deadline. Text
similarity is a retrieval aid, not proof of sameness. A small task can belong to a
large project. Omar's follow-up responsibility can be separate from an employee's
execution task; preserve that distinction instead of copying one task into both
lists. An assigned owner change is explicit, not inferred from who speaks next.

The system must distinguish a repeated mention from a new action, and a completed
artifact from a revised version. Retain the original completed action when a later
request asks for further work. Do not silently redefine its original scope.

## What recurrence means

| Later evidence after a checkbox | Interpretation to distinguish | Reminder consequence |
| --- | --- | --- |
| “We still haven't received the promised report” | Same commitment explicitly outstanding | Same task returns as Evidence needed |
| “Please update that report with the new figures” | New work or expanded scope after prior completion | New linked task; prior completion retained |
| “Send this month's report” | Next instance of a recurring obligation | New occurrence, not a contradiction of last month |
| “The report is still outstanding,” but another owner/report is meant | Incorrect identity/category match | Correct association; do not reopen unrelated work |
| Old transcript reimported | Repeated old evidence | No new task or recurrence count |
| “Thanks for sending the report” | Matching completion confirmation | Clear the same task if identity is supported |

A task returning should gain attention and retain its return history. It should
not automatically gain an invented effort estimate or become a project. Repeated
legitimate returns may expose hidden dependencies, unclear ownership or larger
scope; that is a separate judgment. Count distinct underlying events, not five
copies of the same meeting. If evidence establishes multiple actions/dependencies,
propose a larger task breakdown or project boundary change. Classification errors
must not be counted as operational failure or inflated work size.

## Where Reflex could help

Use specific bounded questions after extraction/retrieval, rather than one
probability that authorizes everything:

1. Project association: supplied active/relevant project IDs versus new coherent
   outcome, routine work or unclear. A proposed new project also needs an extracted
   description and source passage; Reflex selects a relation, not the contents.
2. Task association: which supplied commitment, if any, the passage concerns.
   Include no match/unclear and the relevant completed tasks.
3. Relation to that commitment: new assignment, repetition, completion confirmation,
   explicit outstanding contradiction, new recurring occurrence or changed scope.
   Contradiction cannot be assumed merely because a task was selected.

These questions can be evaluated separately and batched where supported. Reflex
can be used where it improves the decisions; exact IDs, user checkbox events,
source hashes, arithmetic, date comparison, duplicate handling and effect delivery
remain deterministic. Do not add calls merely to use every built-in profile.

Keep distributions with candidate/profile versions so a later correction is
explainable. No hard-coded 0.8 threshold is justified by the example README.
Wrong automatic task changes should carry a higher penalty than temporarily
unmatched information. When a reference genuinely cannot be resolved, retain it
and surface a specific clarification in Reminders rather than inventing a match
or requiring a separate dashboard. Most clear cases should flow automatically.

## Design evidence needed before implementation resumes

Work through a small set of actual source sequences already retained locally:
new project mandate; shared participants across two projects; a repeated promise;
checkbox followed by outstanding evidence; old-email confirmation; new version
request; monthly recurrence; incorrect employee match; multi-project meeting;
old source replay. For each, record expected project identity, task identity,
relation and visible reminder behavior. Use clear passages with ambiguities and
counterexamples, not only easy examples. Do not reopen the whole archive.

Compare ordinary structured LLM interpretation with a Reflex-assisted judgment on
the same candidates before claiming improvement. Candidate retrieval misses and
judgment mistakes are different failures. Start with offline examples/design
walkthrough; any future live evaluation first resolves the private-data route.
No provider integration, thresholds or production deployment is authorized by this
review alone. The owner's current instruction is to think before building further.
