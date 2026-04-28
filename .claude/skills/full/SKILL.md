---
name: full
description: Structured operator for new projects, refactors, and complex implementations. Implementation dispatched to workers.
---

# /full — Full Operator for Complex Work

Structured operator for new projects, refactors, and complex implementations.
Claude plans and reviews. Codex and Gemini execute implementation tasks via dispatch.
**There is no "Claude handles implementation inline" path. If dispatch fails, log a blocker.**

## CRITICAL: Dispatch Is Mandatory

This operator REQUIRES external worker dispatch for ALL implementation tasks.
Claude's role: planning, review, integration. That's it. Workers do the coding.

## Usage

```
/full
/full <project-description>
```

## Behavior

### Phase 1: Intake

1. **Load or Create `1shot/` Context**
2. **Structured Discovery** — what, scope, architecture, constraints
3. **Document Decisions** → `1shot/PROJECT.md` and `1shot/DECISIONS.md`
4. **Update `1shot/LLM-OVERVIEW.md`** if needed

### Phase 2: Planning

1. **Docs Check** — `cat ~/github/docs-cache/docs/cache/.index.md` → cache missing via `/doc`
2. **Phase-Based Plan** → `1shot/ROADMAP.md`
3. **Skill Discovery** — check `1shot/skills/`, search SkillsMP for specialized domains
4. **Create Task Queue** — TaskCreate per milestone
5. **Verify Workers** — this is MANDATORY before proceeding:
   ```bash
   command -v codex >/dev/null 2>&1 && echo "codex: yes" || echo "codex: no"
   command -v gemini >/dev/null 2>&1 && echo "gemini: yes" || echo "gemini: no"
   python3 -m core.router.resolve --class implement_medium --category coding
   ```
   If NO workers available: stop and tell the user. Do not proceed without workers.
6. **Codex Plan Review** — dispatch plan for adversarial review BEFORE coding:
   ```bash
   unset OPENAI_API_KEY && codex exec --json --sandbox danger-full-access \
     -o /tmp/full-plan-review.json \
     "Review this implementation plan: [ROADMAP content]. Flag: (1) missing steps, (2) tasks to combine, (3) risks, (4) better ordering."
   ```
   Surface feedback, adjust plan. If codex unavailable: log blocker, proceed.

### Phase 3: Execution

1. **Methodology Selection** (per milestone — automatic)
   - **Bug fix** → `/debug` protocol
   - **New feature** → `/tdd` protocol
   - **Doc edit, config change, refactor**: no special methodology

2. **Milestone Tracking** — commit after each milestone

3. **Dispatch ALL Implementation Tasks** (MANDATORY)
   For each milestone task:
   ```bash
   # Classify and resolve
   python3 -m core.router.resolve --class <task_class> --category <category>

   # Dispatch to worker
   python3 -m core.dispatch.run \
     --class <task_class> \
     --category <category> \
     --prompt "Self-contained prompt: task, acceptance criteria, files to read, patterns, constraints, output format" \
     --output 1shot/dispatch \
     --manifest 1shot/dispatch
   ```
   - Review dispatch output, validate against acceptance criteria, commit
   - If dispatch fails: retry with fallback_lane, then log blocker and skip
   - **Do NOT implement code yourself**

4. **Burn-Down Mode** — complete one milestone fully before next

5. **Context Checkpoints** — at 50% suggest /handoff, at 70% auto-handoff

### Phase 4: Completion

1. **Challenge Pass** — dispatch adversarial review to Codex:
   ```bash
   unset OPENAI_API_KEY && codex exec --json --sandbox danger-full-access \
     -o /tmp/full-challenge.json \
     "Review this diff for code quality: (1) production risks, (2) unhandled edge cases, (3) security concerns, (4) pattern adherence. Diff: [content]"
   ```
   If Codex unavailable: log blocker, surface to user.

2. **Verification (MANDATORY — evidence required)**
   1. Run targeted tests — show output
   2. Run lint/static analysis — show output
   3. Run type check — show output
   4. Check acceptance criteria — cite evidence per criterion
   5. Review diff against plan scope

3. **Update `1shot/LLM-OVERVIEW.md`** with current state

4. **Summary**
   ```
   Implementation Complete
   ├─ Milestones: X/Y completed
   ├─ Workers used: [codex: N, gemini: M, glm: P]
   ├─ Files changed: Z
   ├─ Commits: N
   └─ Next steps: [if any]
   ```

## Provider Routing

See `~/.claude/skills/_shared/dispatch.md` for the dispatch protocol.
See `~/.claude/skills/_shared/providers.md` for provider detection and commands.

## `1shot/` Structure

```
1shot/
├── LLM-OVERVIEW.md   # Full project context
├── PROJECT.md        # Goals, scope, acceptance criteria
├── STATE.md          # Current phase and loop state
├── ROADMAP.md        # Milestones and plan
├── DECISIONS.md      # Decision log
├── BLOCKERS.md       # Blocked items
├── dispatch/         # Dispatch manifests and output
└── skills/           # SkillsMP-pulled project skills
```

## Auto-Approved Actions

- Reading any file
- Writing to scope-matched files
- Creating/updating any file under `1shot/`
- Running tests and linters
- Calling Codex/Gemini/GLM CLI via bash (dispatch)
- Git commit (not push)

## Requires Confirmation

- Destructive operations
- Git push to shared branches
- External API calls that cost money
- Deploying to production
- Major architecture changes
