---
name: conduct
description: Multi-model orchestration with lane-based routing. Classifies tasks, routes to appropriate lanes (premium/balanced/cheap/research), and loops until the goal is met. Use when the task is non-trivial and you want it to run until done. Trigger keywords: orchestrate, PMO, keep working, until done, multi-model, conduct.
---

# /conduct — Lane-Based Orchestrator

Classifies tasks by type, routes to lanes, dispatches to workers, reviews with Claude. Loops until done.

## Usage

```
/conduct
/conduct <idea or goal>
```

## Behavior

### Phase 0: Intake (BLOCKING — nothing else runs until complete)

1. **Detect providers and config**
   ```bash
   command -v codex >/dev/null 2>&1 && echo "codex: yes" || echo "codex: no"
   command -v gemini >/dev/null 2>&1 && echo "gemini: yes" || echo "gemini: no"
   python -c "from core.search.argus_client import is_available; print('argus:', is_available())" 2>/dev/null || echo "argus: no"
   ```
   If `config/lanes.yaml` and `config/workers.yaml` exist, read them for routing.
   If they don't exist, skip silently — execute all tasks inline with Claude.
   Never mention the absence of routing config to the user.

2. **Ask 5 required questions** using AskUserQuestion — do NOT proceed until answered:
   1. What is the goal / deliverable?
   2. What does done look like? (acceptance criteria — be specific)
   3. What is in scope? What is explicitly out of scope?
   4. Any constraints? (tech stack, time, things to avoid)
   5. What is the riskiest / most uncertain part?

3. **Initialize `1shot/`** in the project root (create if missing):
   - Write intake answers to `1shot/PROJECT.md`
   - Update `1shot/STATE.md`: phase = "intake → plan"
   - Create `1shot/skills/` directory

4. **Show PROJECT.md** to user and confirm before proceeding.

### Phase 1: Plan

1. **Explore codebase** (Explore subagent) — identify impacted files
2. **Persist exploration artifact** — Write structured output to `1shot/explore.json`:
   ```json
   {
     "goal": "[from PROJECT.md]",
     "candidate_files": ["list of relevant files"],
     "commands_to_run": ["test commands", "lint commands"],
     "constraints": ["architectural constraints discovered"],
     "unknowns": ["open questions to resolve"],
     "risk_assessment": {"level": "low|medium|high", "reasoning": "..."},
     "existing_patterns": ["patterns found in relevant files"]
   }
   ```
   This artifact is visible, editable, and reusable. Update it as exploration progresses.
3. **Docs Check**
   - Check cache: `cat ~/github/docs-cache/docs/cache/.index.md`
   - For anything missing → run `/doc <name> <url>` before assigning build tasks
4. **Write `1shot/ROADMAP.md`** — phases and success criteria
5. **Task specs for non-trivial work**: If any task is medium or high risk, generate a TASK_SPEC.md from the template at `templates/TASK_SPEC.md` and write it to `1shot/TASK_SPEC.md`. Use `1shot/explore.json` to populate the Files Involved section of TASK_SPEC.
6. **Generate machine-readable plan** — Create `1shot/plan.json` from the TASK_SPEC:
   Use the plan schema from `core/plan_schema.py`:
   ```python
   from core.plan_schema import Plan, PlanStep, VerifyStep, StepAction, VerifyType
   from core.task_schema import RiskLevel

   plan = Plan(
       objective="[from TASK_SPEC Goal]",
       risk_level=RiskLevel.medium,
       steps=[
           PlanStep(id="1", action=StepAction.explore, description="...", files=[...]),
           PlanStep(id="2", action=StepAction.implement, description="...", files=[...], depends_on=["1"]),
       ],
       verification=[
           VerifyStep(verify_type=VerifyType.test, command="pytest tests/"),
       ],
       rollback="git restore [files]",
   )
   ```
   Write to `1shot/plan.json`. This file is the executable plan that drives the build loop.
7. **Create native tasks** — one TaskCreate per deliverable:
   - subject: deliverable title
   - description: acceptance criteria, files to touch
   - Set addBlockedBy for dependencies
8. **Classify each task** using `docs/instructions/task-classes.md`:
   ```bash
   python -m core.router.resolve --class <task_class>
   ```
   This returns: lane, workers, reviewer, search_backend, fallback_lane
9. **Update STATE.md**: phase = "plan → build"

### Phase 2: Build Loop

Repeat until no unblocked tasks remain:

1. Pick next unblocked task (`TaskList` → lowest ID pending)
2. `TaskUpdate` → in_progress
3. **Select methodology** (automatic — based on task description):
   - **Bug fix** (fix, bug, broken, error, crash, failing, wrong, unexpected, regression,
     investigate, troubleshoot, not working, incorrect) → apply `/debug` protocol:
     investigate → analyze → hypothesize → fix. Phases 1-3 are read-only.
   - **New feature / implementation** (implement, add, create, build, new endpoint,
     new function, new behavior) → apply `/tdd` protocol: RED-GREEN-REFACTOR.
     No production code without a failing test shown first.
   - **Doc edit, config change, refactor, review**: no special methodology needed.
4. **Classify and dispatch**:
   - Determine task class (see task-classes.md)
   - Resolve lane: `python -m core.router.resolve --class <class>`
   - **Follow the dispatch protocol** (see `~/.claude/skills/_shared/dispatch.md`):
     - If premium lane → execute inline with Claude
     - Otherwise → build self-contained prompt → dispatch to Codex/Gemini
     - For parallel tasks → use `python3 -m core.dispatch.run --prompts-file batch.json`
     - Capture output, validate, write manifest to `1shot/dispatch/`
   - **CRITICAL: Use subprocess dispatch, NOT Agent tool subagents.**
     The dispatch runner (`core.dispatch.run`) spawns lightweight CLI processes.
     The Agent tool spawns full Claude Code sessions — only use Agent tool for
     complex multi-step reasoning that the dispatch runner can't handle.
     For batch file processing, extraction, summarization → always use `core.dispatch.run`.
5. **Review**: If task requires review, dispatch review to reviewer (see dispatch.md Step 7)
6. **Scope check** — Before verification, compare actual changes against plan:
   ```bash
   # Get files actually changed
   git diff --name-only

   # Compare against planned files from TASK_SPEC (1shot/TASK_SPEC.md "Files Involved" section)
   ```

   - If changes touch files listed in "Must NOT Touch" → **STOP**, flag as blocker, require human decision
   - If changes touch files not in "Will Change" or "Read-Only" → **WARN**, log to `1shot/BLOCKERS.md` with explanation, ask if the new files should be added to the plan
   - If changes are within plan → continue to verification

   This prevents the common pattern where a "small fix" grows to touch unrelated subsystems.
7. **Verify**: Run the Phase 3 verification checklist (see below) — all checks must pass before marking completed
8. `TaskUpdate` → completed (only after verification passes)
9. Update `1shot/STATE.md`: increment loop count, log action
10. **Circuit breaker**: if same task failed 3x → log blocker → skip → continue

If 3 consecutive tasks hit circuit breaker → stop, surface to user.

### Phase 3: Verify (MANDATORY — evidence required)

**No verification, no completion. Assertions don't count — show the output.**

Every task must pass this checklist before it can be marked completed. No exceptions —
"trivial," "just a doc edit," and "obviously correct" all get verified.

For each completed task, run this checklist. **Each step requires showing actual command
output.** "I checked it" or "tests pass" without output = verification not done.

1. **Run targeted tests** — if test files exist for the changed files, run them.
   Show the output. If no test files exist, state explicitly: "No test files found for
   {files changed}." This is not a pass — it's a gap.
2. **Run lint/static analysis** — shellcheck, prettier, ruff, or whatever the project uses.
   Show the output (or lack of errors). If no linter is configured, state what was tried.
3. **Run type check** — tsc, pyright, or equivalent. Show the output.
4. **Check acceptance criteria** — go through each criterion from `1shot/PROJECT.md` or the
   task description one by one. For each: state the criterion, then cite the evidence
   (file changed, output shown, behavior confirmed). A criterion without evidence is unverified.
5. **Review diff** — `git diff` and confirm changed files match the plan scope.
   Flag anything out of scope.

If any check fails:
- `TaskUpdate` back to **pending** — never mark as completed with failing checks
- Loop back to Phase 2 with the specific failure as context
- Document what failed in `1shot/BLOCKERS.md` if it was not resolved in one retry

### Phase 4: Challenge (two-stage review)

Two-stage adversarial review. Stage A must pass before Stage B runs.

#### Stage A: Spec Compliance

Did we build what PROJECT.md asked for?

1. Re-read `1shot/PROJECT.md` — every acceptance criterion, scope constraint, and goal
2. For each acceptance criterion: cite the evidence (file changed, test output, behavior confirmed)
3. Check scope: are there changes to files that were explicitly out of scope?
4. **If any criterion has no evidence** → fail Stage A, create tasks to address gaps, loop to Phase 2
5. **If scope was violated** → fail Stage A, flag for human review

**Stage A pass** → proceed to Stage B. **Stage A fail** → do not run Stage B.

#### Stage B: Code Quality

Is the implementation well-built?

1. `git diff $(git merge-base HEAD main)..HEAD` — full diff since conduct started
2. If Codex available:
   ```bash
   unset OPENAI_API_KEY && codex exec --json --sandbox danger-full-access -o /tmp/conduct-challenge.json "Review this diff for code quality: (1) what could break in production, (2) what edge cases are unhandled, (3) are there any security concerns, (4) does it follow the repo's existing patterns. Diff: [content]"
   ```
   Parse: `jq 'select(.type=="item.completed") | .item.text' /tmp/conduct-challenge.json`
   If Codex unavailable: Claude performs code quality review inline.
3. New issues → create Tasks → loop to Phase 2
4. Clean pass → update STATE.md: phase = "complete"

### Phase 5: Session-End Learning

If any correction was given 2+ times during this session:
- Write proposal to `docs/instructions/learned/{date}-{topic}.md`
- Never auto-edit `CLAUDE.md` or rules

### Done

```
Conduct Complete
├─ Tasks: X/Y completed
├─ Lanes used: [list]
├─ Files changed: Z
├─ Commits: N
└─ Blockers: M (see 1shot/ISSUES.md)
```

---

## Routing Reference

See `docs/instructions/task-classes.md` for full classification guide.
See `~/.claude/skills/_shared/dispatch.md` for the dispatch protocol (how to build prompts, run parallel workers, capture output, write manifests).
See `~/.claude/skills/_shared/providers.md` for provider detection and commands.

**Key rule**: Route by task class, not provider name. Use lane policy from config.
Claude thinks. Codex and Gemini execute.

---

## Decision Defaults

| Ambiguity | Default |
|-----------|---------|
| Multiple implementations | Simplest one |
| Naming | Follow existing pattern |
| Lane selection | Use task class routing |
| Stack | Follow CLAUDE.md defaults |

---

## Auto-Approved Actions

- Reading any file
- Writing to scope-matched files
- Creating / updating `1shot/` files
- Running tests and linters
- Git commit (not push)
- Creating and updating native tasks

## Requires Confirmation

- Destructive operations (rm -rf, DROP TABLE, reset --hard)
- Git push to shared branches
- External API calls that cost money
- Deploying to production
