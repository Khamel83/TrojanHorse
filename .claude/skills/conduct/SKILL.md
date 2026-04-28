---
name: conduct
description: Multi-model orchestration with lane-based routing. Classifies tasks, routes to appropriate lanes (premium/balanced/cheap/research), and loops until the goal is met. Use when the task is non-trivial and you want it to run until done. Trigger keywords: orchestrate, PMO, keep working, until done, multi-model, conduct.
---

# /conduct — Lane-Based Orchestrator

Classifies tasks by type, routes to lanes, dispatches to workers, reviews with Claude. Loops until done.

## CRITICAL: Dispatch Is Mandatory

This operator REQUIRES external worker dispatch. Claude is the planner and reviewer ONLY.
Implementation tasks MUST go to codex/gemini/glm via `core.dispatch.run` or subprocess.
**There is no "do it inline" fallback. If dispatch fails, log a blocker and escalate.**

## Usage

```
/conduct
/conduct <idea or goal>
```

## Behavior

### Phase 0: Intake (BLOCKING — nothing else runs until complete)

1. **Detect providers and verify routing works**
   ```bash
   command -v codex >/dev/null 2>&1 && echo "codex: yes" || echo "codex: no"
   command -v gemini >/dev/null 2>&1 && echo "gemini: yes" || echo "gemini: no"
   python3 -m core.router.resolve --class implement_small --category coding
   ```
   The router MUST return a valid lane with workers. If it fails, stop and tell the user.
   `config/lanes.yaml` and `config/workers.yaml` MUST exist. If they don't, stop and tell the user.

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
3. **Docs Check** — `cat ~/github/docs-cache/docs/cache/.index.md` → cache missing docs via `/doc`
4. **Write `1shot/ROADMAP.md`** — phases and success criteria
5. **Task specs for non-trivial work**: Generate TASK_SPEC.md from `templates/TASK_SPEC.md`
6. **Generate machine-readable plan** — Create `1shot/plan.json` from `core/plan_schema.py`
7. **Create native tasks** — one TaskCreate per deliverable
8. **Classify each task**: `python -m core.router.resolve --class <task_class> --category <category>`
9. **Update STATE.md**: phase = "plan → build"

### Phase 2: Build Loop (ALL implementation via dispatch)

Repeat until no unblocked tasks remain:

1. Pick next unblocked task (`TaskList` → lowest ID pending)
2. `TaskUpdate` → in_progress
3. **Select methodology** (automatic — based on task description):
   - **Bug fix** → `/debug` protocol (investigate → analyze → hypothesize → fix)
   - **New feature** → `/tdd` protocol (RED-GREEN-REFACTOR)
   - **Doc edit, config change, refactor**: no special methodology needed
4. **Classify and dispatch** (MANDATORY — no exceptions):
   - Determine task class (see task-classes.md)
   - Resolve lane: `python -m core.router.resolve --class <class> --category <category>`
   - **If lane is NOT premium**: Build self-contained prompt → dispatch to worker:
     ```bash
     python3 -m core.dispatch.run \
       --class <task_class> \
       --category <category> \
       --prompt "Your self-contained prompt here..." \
       --output 1shot/dispatch \
       --manifest 1shot/dispatch
     ```
   - **If lane IS premium**: Claude handles inline (planning, review, integration only)
   - **For parallel tasks**:
     ```bash
     echo '[{"id":"1","prompt":"task 1"},{"id":"2","prompt":"task 2"}]' > /tmp/batch.json
     python3 -m core.dispatch.run --class <task_class> --prompts-file /tmp/batch.json --parallel 3
     ```
   - **CRITICAL: Use subprocess dispatch, NOT Agent tool subagents.**
     `core.dispatch.run` spawns lightweight CLI processes.
     Agent tool spawns full Claude Code sessions — never use Agent for dispatch.
   - If NO workers are available (codex, gemini, glm all fail): **log blocker, stop, tell user**
5. **Review**: If task requires review, dispatch review to reviewer
6. **Scope check** — `git diff --name-only` against TASK_SPEC "Files Involved"
7. **Verify**: Run Phase 3 verification checklist
8. `TaskUpdate` → completed (only after verification passes)
9. Update `1shot/STATE.md`
10. **Circuit breaker**: if same task failed 3x → log blocker → skip → continue

If 3 consecutive tasks hit circuit breaker → stop, surface to user.

### Phase 3: Verify (MANDATORY — evidence required)

**No verification, no completion. Assertions don't count — show the output.**

1. **Run targeted tests** — if test files exist for the changed files, run them.
2. **Run lint/static analysis** — shellcheck, prettier, ruff, or whatever the project uses.
3. **Run type check** — tsc, pyright, or equivalent.
4. **Check acceptance criteria** — go through each criterion, cite evidence.
5. **Review diff** — `git diff` and confirm changed files match plan scope.

If any check fails:
- `TaskUpdate` back to **pending** — never mark as completed with failing checks
- Loop back to Phase 2
- Document persistent failures in `1shot/BLOCKERS.md`

### Phase 4: Challenge (two-stage review)

#### Stage A: Spec Compliance
Re-read `1shot/PROJECT.md`. For each acceptance criterion: cite evidence. Check scope violations.
**Stage A fail** → do not run Stage B. Create tasks to address gaps.

#### Stage B: Code Quality
```bash
unset OPENAI_API_KEY && codex exec --json --sandbox danger-full-access \
  -o /tmp/conduct-challenge.json \
  "Review this diff for code quality: (1) what could break in production, (2) what edge cases are unhandled, (3) are there any security concerns, (4) does it follow the repo's existing patterns. Diff: [content]"
```
Parse: `jq 'select(.type=="item.completed") | .item.text' /tmp/conduct-challenge.json`
If Codex unavailable: log blocker, surface to user. Do NOT review inline.

### Phase 5: Session-End Learning

If any correction was given 2+ times during this session:
- Write proposal to `docs/instructions/learned/{date}-{topic}.md`

### Done

```
Conduct Complete
├─ Tasks: X/Y completed
├─ Lanes used: [list]
├─ Workers used: [list with counts]
├─ Files changed: Z
├─ Commits: N
└─ Blockers: M (see 1shot/ISSUES.md)
```

---

## Routing Reference

See `docs/instructions/task-classes.md` for full classification guide.
See `~/.claude/skills/_shared/dispatch.md` for the dispatch protocol.
See `~/.claude/skills/_shared/providers.md` for provider detection and commands.

**Key rule**: Route by task class, not provider name. Use lane policy from config.
Claude thinks. Codex and Gemini execute. This is non-negotiable.
