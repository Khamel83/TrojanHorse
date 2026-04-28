---
name: short
description: Quick iterations on existing projects. Load context, ask what's next, execute in burn-down mode. Implementation tasks dispatched to workers.
---

# /short — Quick Iteration Operator

Fast operator for existing projects. Loads context, asks what you're working on, executes.
**Implementation tasks are dispatched to workers. Claude only handles planning, review, and integration.**

## CRITICAL: Dispatch Is Mandatory

This operator REQUIRES external worker dispatch for implementation tasks.
Claude is the planner and reviewer ONLY. If you are about to write implementation code
yourself — STOP — you are violating this skill's contract. Build a prompt and dispatch.

## Usage

```
/short
/short <scope>
```

## Behavior

When invoked:

1. **Load Context**
   - Read recent git commits: `git log --oneline -5`
   - Check TaskList for pending/in_progress tasks (if any exist)
   - Read `1shot/DECISIONS.md`, `1shot/BLOCKERS.md` if present

2. **Ask What's Next**

3. **Verify Workers Are Available**
   ```bash
   python3 -m core.router.resolve --class implement_small --category coding
   ```
   If the router fails or returns no workers, stop and tell the user.

4. **Docs Check** (if the task uses any external library, API, or tool)
   - Check local cache: `cat ~/github/docs-cache/docs/cache/.index.md`
   - If missing → run `/doc <name> <url>` to cache it first

5. **Skill Discovery** (if the task is specialized)
   - Check `1shot/skills/` for already-pulled skills
   - Specialized domains (security, blockchain, ML, infra): search via `./scripts/skillsmp-search.sh`

6. **Methodology Selection** (automatic)
   - **Bug fix** → `/debug` protocol (investigate → analyze → hypothesize → fix)
   - **New feature** → `/tdd` protocol (RED-GREEN-REFACTOR)
   - **Doc edit, config change, refactor**: no special methodology needed

7. **Execute in Burn-Down Mode**

   For each task:
   - **Planning/review tasks**: Claude handles inline
   - **Implementation tasks** (code changes, test writing, refactoring):
     ```bash
     python3 -m core.router.resolve --class <task_class> --category <category>
     # Build self-contained prompt from dispatch.md template
     python3 -m core.dispatch.run \
       --class <task_class> \
       --category <category> \
       --prompt "..." \
       --output 1shot/dispatch \
       --manifest 1shot/dispatch
     ```
   - After dispatch completes: review output, validate, integrate, commit
   - **If dispatch fails**: retry with fallback_lane once, then log blocker and skip
   - **Do NOT implement code yourself as a fallback**

   After each significant change, dispatch a review via the dispatch protocol.

8. **Show Summary on Completion**
   ```
   Session Summary
   ├─ Tasks completed: X
   ├─ Workers used: [codex: N, gemini: M, glm: P]
   ├─ Files changed: Y
   ├─ Dispatches: total N (succeeded: M, failed: P)
   └─ Next: [next task or "all done"]
   ```

## Provider Routing

See `~/.claude/skills/_shared/dispatch.md` for the dispatch protocol.
See `~/.claude/skills/_shared/providers.md` for provider detection and commands.

## `1shot/` Convention

- `1shot/DECISIONS.md` — decision log
- `1shot/BLOCKERS.md` — blocked items
- `1shot/skills/` — project-local SkillsMP skills

## Auto-Approved Actions

- Reading any file
- Writing to scope-matched files
- Creating/updating any file under `1shot/`
- Running tests and linters
- Calling Codex/Gemini/GLM CLI via bash (dispatch)
- Git commit (not push)

## Requires Confirmation

- Destructive operations (rm -rf, DROP TABLE)
- Git push to shared branches
- External API calls that cost money
- Deploying to production
