---
name: full
description: Structured operator for new projects, refactors, and complex implementations.
---

# /full — Full Operator for Complex Work

Structured operator for new projects, refactors, and complex implementations.
Claude plans and executes. Codex reviews the plan and challenges the implementation.

## Usage

```
/full
/full <project-description>
```

## Behavior

When invoked:

### Phase 1: Intake

1. **Load or Create `1shot/` Context**
   - Check for `1shot/PROJECT.md` — if missing, create from intake below
   - Check for `1shot/LLM-OVERVIEW.md` — if missing, create from template
   - Read `1shot/STATE.md` if resuming

2. **Structured Discovery**
   - What are you building?
   - What's the scope?
   - What's the target architecture?
   - Any constraints or preferences?

3. **Document Decisions**
   - Write to `1shot/PROJECT.md`
   - Note key decisions in `1shot/DECISIONS.md`

4. **Update `1shot/LLM-OVERVIEW.md`**
   - Fill in or refresh: what is this, stack, key files, how to run
   - Keep it current — it's the single source of truth for any LLM entering this project

### Phase 2: Planning

1. **Docs Check**
   - Identify all external libraries, APIs, and tools the project will use
   - Check cache: `cat ~/github/docs-cache/docs/cache/.index.md`
   - For anything missing → run `/doc <name> <url>` before coding begins
   - Use cached docs as source of truth — do NOT rely on training data for syntax

2. **Phase-Based Plan**
   - Break into milestones (not every sub-step)
   - Define acceptance criteria per milestone
   - Identify dependencies
   - Write `1shot/ROADMAP.md`

3. **Skill Discovery**
   - Check `1shot/skills/` for already-pulled project skills
   - For each high-level task type, ask: *"Is this specialized enough that a better community skill exists?"*
   - Specialized domains (security, blockchain, ML, infra tools, specific APIs, parsers): **search SkillsMP**
     ```bash
     ./scripts/skillsmp-search.sh "<task type>" --install
     ```
   - General tasks (write tests, refactor, add endpoint): skip search, proceed with core skills
   - If a skill is pulled, note it: "Using `1shot/skills/{name}` for [task type]"

4. **Create Task Queue**
   - Use native TaskCreate for each milestone (not every sub-step)
   - Set dependencies with addBlockedBy
   - Tasks track milestones, not individual file edits

5. **Detect Providers**
   ```bash
   command -v codex >/dev/null 2>&1 && echo "codex: yes" || echo "codex: no"
   command -v gemini >/dev/null 2>&1 && echo "gemini: yes" || echo "gemini: no"
   ```
   Note available providers in `1shot/STATE.md`.

6. **Codex Plan Review** (adversarial pass on the plan — before any code)
   - If codex available, send the plan for review:
     ```bash
     codex exec --full-auto "You are reviewing an implementation plan before execution. Here is the plan: [ROADMAP.md content]. Flag: (1) missing steps or dependencies, (2) tasks that could be combined, (3) risks not mentioned, (4) a better ordering. Be specific. Context: [PROJECT.md summary]"
     ```
   - Surface Codex's feedback — adjust plan if warranted, but proceed regardless
   - If codex unavailable → Claude does inline self-review, continue

### Phase 3: Execution

1. **Methodology Selection** (per milestone — automatic)
   For each milestone task, inspect the task description and apply the right protocol:
   - **Bug fix** (fix, bug, broken, error, crash, failing, wrong, unexpected, regression,
     investigate, troubleshoot, not working, incorrect) → follow the `/debug` protocol:
     investigate → analyze → hypothesize → fix. Phases 1-3 are read-only before any code.
   - **New feature / implementation** (implement, add, create, build, new endpoint, new function)
     → follow the `/tdd` protocol: RED-GREEN-REFACTOR. No production code without a failing
     test shown first.
   - **Doc edit, config change, refactor**: no special methodology needed.

2. **Milestone Tracking**
   - Work through tasks in order
   - Commit after each milestone
   - Update `1shot/STATE.md` with progress

3. **Dispatch Non-Premium Tasks**
   - For each milestone task, classify using task-classes.md and determine category
   - **Follow the dispatch protocol** (see `~/.claude/skills/_shared/dispatch.md`):
     - Premium tasks (planning, review, integration) → Claude handles inline
     - Implementation, test, doc tasks → dispatch to best available worker for that category
     - Use `python3 -m core.dispatch.run --category <category>` for parallel execution
     - Write manifests to `1shot/dispatch/`
   - Review dispatch output, validate against acceptance criteria, commit

4. **Burn-Down Mode**
   - Complete one milestone fully before starting next
   - If blocked > 2 attempts: log to `1shot/BLOCKERS.md`, skip, continue

5. **Context Checkpoints**
   - At 50% context: suggest /handoff
   - At 70% context: auto-create handoff

### Phase 4: Completion

1. **Challenge Pass** (adversarial review of full implementation)
   - `git diff $(git merge-base HEAD main)..HEAD` — full diff since full started
   - **Follow the dispatch protocol** for the review (see `_shared/dispatch.md`):
     - Dispatch to Codex for adversarial review
     - Use `codex exec --json -o /tmp/full-challenge.json`
   - If codex unavailable: Claude performs adversarial review inline
   - New issues found → fix, then re-verify

2. **Verification (MANDATORY — evidence required)**

   **No verification, no completion. Assertions don't count — show the output.**

   Every milestone must pass this checklist. Each step requires actual command output.

   1. **Run targeted tests** — if test files exist, run them. Show output.
   2. **Run lint/static analysis** — show output (or lack of errors). No linter? State what was tried.
   3. **Run type check** — show output.
   4. **Check acceptance criteria** — go through each criterion one by one. Cite evidence.
   5. **Review diff against plan** — confirm changed files match ROADMAP.md scope.

   If any check fails:
   - Do not proceed to the summary — go back and fix the issue
   - Re-run the failed check(s) to confirm the fix
   - Document persistent failures in `1shot/BLOCKERS.md`

3. **Update `1shot/LLM-OVERVIEW.md`**
   - Refresh "Current State" section to reflect what was built

4. **Summary**
   ```
   📊 Implementation Complete
   ├─ Milestones: X/Y completed
   ├─ Files changed: Z
   ├─ Commits: N
   ├─ Codex reviews: M (issues found: P)
   ├─ Skills pulled: Q (in 1shot/skills/)
   └─ Next steps: [if any]
   ```

## Provider Routing

See `~/.claude/skills/_shared/dispatch.md` for the dispatch protocol.
See `~/.claude/skills/_shared/providers.md` for provider detection and commands.

**Full-specific routing**: Claude plans and reviews. Codex and Gemini execute implementation tasks via the dispatch protocol. Research tasks route to Gemini. Full is one operator, not a PMO — don't make it behave like conduct.

## `1shot/` Structure

```
1shot/
├── LLM-OVERVIEW.md   # Full project context — keep updated
├── PROJECT.md        # Goals, scope, acceptance criteria
├── STATE.md          # Current phase and loop state
├── ROADMAP.md        # Milestones and plan
├── DECISIONS.md      # Decision log
├── BLOCKERS.md       # Blocked items
└── skills/           # SkillsMP-pulled project skills
    └── {name}/
        └── SKILL.md
```

Only `AGENTS.md` and `CLAUDE.md` belong at the project root. Everything else goes in `1shot/`.

## Decision Defaults

| Ambiguity | Default |
|-----------|---------|
| Stack | Follow CLAUDE.md defaults |
| Multiple implementations | Simplest |
| Naming | Follow existing pattern |
| Auth | Supabase Auth (email/password + Google OAuth) |
| Database | SQLite → Supabase Postgres |
| Deploy | Vercel / oci-dev |
| SkillsMP search bar | Specialized domain → search; general task → skip |
| Codex review? | Always run if available (advisory, not a gate) |

## Auto-Approved Actions

- Reading any file
- Writing to scope-matched files
- Creating/updating any file under `1shot/`
- Running `./scripts/skillsmp-search.sh`
- Running tests and linters
- Calling Codex and Gemini CLI via bash
- Git commit (not push)
- Creating native tasks

## Requires Confirmation

- Destructive operations
- Git push to shared branches
- External API calls that cost money
- Deploying to production
- Major architecture changes
