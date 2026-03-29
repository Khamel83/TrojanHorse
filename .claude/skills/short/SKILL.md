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

3. **Pre-Flight Codex Review** (if the user describes a non-trivial change)
   - Check: `command -v codex >/dev/null 2>&1`
   - If available, send a quick adversarial take before starting:
     ```bash
     codex exec --full-auto "You are a quick adversarial reviewer. The user wants to: [description]. Before they start, flag: (1) anything that could break, (2) a simpler approach if one exists, (3) dependencies they might miss. Be brief — 5 bullet points max."
     ```
   - Surface Codex's feedback to the user, then proceed regardless
   - If codex unavailable → skip silently
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

6. **Execute in Burn-Down Mode**
   - Complete one task fully before starting next
   - If blocked > 2 attempts: log to `1shot/BLOCKERS.md`, skip, continue
   - No "pending review" — either done or blocked
   - **Do NOT create TaskList items for every little thing** — just do the work
   - After each significant change, run Codex adversarial review:
     ```bash
     codex exec --full-auto "Review this change for: (1) bugs, (2) edge cases, (3) what was missed. Be specific and brief. Context: [diff + task description]"
     ```
   - If codex finds real issues → fix before moving on
   - If codex unavailable → skip silently

7. **Show Summary on Completion**
   ```
   📊 Session Summary
   ├─ Tasks completed: X
   ├─ Files changed: Y
   ├─ Codex reviews: N (issues found: M)
   ├─ Skills used: [list or "core only"]
   └─ Next: [next task or "all done"]
   ```

## Provider Routing

See `~/.claude/skills/_shared/providers.md` for provider detection and dispatch commands.

**Short-specific routing**: Short only uses Codex for advisory reviews (pre-flight + post-completion). No Gemini, no research routing. If Codex is unavailable, everything runs through Claude with zero degradation.

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
