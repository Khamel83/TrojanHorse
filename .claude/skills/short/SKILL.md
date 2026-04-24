---
name: short
description: Quick iterations on existing projects. Load context, ask what's next, execute in burn-down mode.
---

# /short — Quick Iteration Operator

Fast operator for existing projects. Loads context, asks what you're working on, executes.
Codex provides advisory second opinions — never a gate, never a blocker.

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
   - Read `1shot/LLM-OVERVIEW.md` if present (quick project orientation)

2. **Ask What's Next**
   ```
   "What are you working on?"
   ```

3. **Pre-Flight Review** (if the user describes a non-trivial change)
   - Check providers: `command -v codex >/dev/null 2>&1 && echo "codex: yes"`
   - If codex available, dispatch a quick adversarial take before starting
   - Follow dispatch protocol (see `~/.claude/skills/_shared/dispatch.md`)
   - This is advisory, not a gate. Don't stall on it.

4. **Docs Check** (if the task uses any external library, API, or tool)
   - Check local cache: `cat ~/github/docs-cache/docs/cache/.index.md`
   - If the tool is missing → run `/doc <name> <url>` to cache it first
   - Use cached docs as source of truth — do NOT rely on training data for syntax
   - If no external tools involved: skip this step

5. **Skill Discovery** (if the task is specialized)
   - Check `1shot/skills/` — already pulled skills for this project
   - If the task involves a specific domain, tool, or API not covered by core skills:
     ```bash
     ./scripts/skillsmp-search.sh "<task type>" --install
     ```
   - General tasks (write tests, fix bug, refactor): skip search, proceed
   - Specialized domains (security, blockchain, ML, infra, specific parsers): search

6. **Methodology Selection** (automatic)
   Inspect the task description. Apply the right protocol automatically:
   - **Bug fix** (fix, bug, broken, error, crash, failing, wrong, unexpected, regression,
     investigate, troubleshoot, not working, incorrect) → follow the `/debug` protocol:
     investigate → analyze → hypothesize → fix. Phases 1-3 are read-only.
   - **New feature / implementation** (implement, add, create, build, new endpoint, new function,
     new behavior) → follow the `/tdd` protocol: RED-GREEN-REFACTOR. No production code
     without a failing test shown first.
   - **Doc edit, config change, refactor**: no special methodology needed, execute directly.

7. **Execute in Burn-Down Mode**
   - Complete one task fully before starting next
   - If blocked > 2 attempts: log to `1shot/BLOCKERS.md`, skip, continue
   - No "pending review" — either done or blocked
   - **Do NOT create TaskList items for every little thing** — just do the work
   - After each significant change, dispatch a review via the dispatch protocol
     (see `~/.claude/skills/_shared/dispatch.md`)
   - If codex unavailable → Claude handles review inline

8. **Show Summary on Completion**
   ```
   📊 Session Summary
   ├─ Tasks completed: X
   ├─ Files changed: Y
   ├─ Codex reviews: N (issues found: M)
   ├─ Skills used: [list or "core only"]
   └─ Next: [next task or "all done"]
   ```

## Provider Routing

See `~/.claude/skills/_shared/dispatch.md` for the dispatch protocol.
See `~/.claude/skills/_shared/providers.md` for provider detection and commands.

**Short-specific routing**: Short dispatches workers for advisory reviews (pre-flight + post-completion).
Uses category-based worker selection — the resolver returns workers ordered by category preference.
Claude handles everything else. If workers are unavailable, zero degradation.

## Scope

Optional scope limits work to matching files:

```
/short src/auth/*.ts    # Only work on auth files
```

## `1shot/` Convention

Logs and state live in `1shot/`, not at the project root:
- `1shot/DECISIONS.md` — decision log
- `1shot/BLOCKERS.md` — blocked items
- `1shot/skills/` — project-local SkillsMP skills

Only `AGENTS.md` and `CLAUDE.md` belong at the root.

## Decision Defaults (Don't Ask)

| Ambiguity | Default |
|-----------|---------|
| Multiple implementations | Simplest |
| Naming | Follow existing pattern |
| Refactor opportunity | Skip unless blocking |
| Error handling | Match surrounding code |
| SkillsMP search? | Specialized domain → yes; general task → no |
| Codex review? | Always run if available (advisory only) |

When truly ambiguous, pick option A, note in `1shot/DECISIONS.md`.

## Auto-Approved Actions

- Reading any file
- Writing to scope-matched files
- Running tests and linters
- Creating/updating any file under `1shot/`
- Running `./scripts/skillsmp-search.sh`
- Calling Codex CLI via bash
- Git commit (not push)

## Requires Confirmation

- Destructive operations (rm -rf, DROP TABLE)
- Git push to shared branches
- External API calls that cost money
- Deploying to production
