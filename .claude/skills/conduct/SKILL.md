---
name: conduct
description: Multi-model PMO orchestrator. Asks clarifying questions first, creates a structured plan, routes work across Claude + Codex + Gemini, and loops until the goal is actually met. Use when the task is non-trivial and you want it to run until done without stopping early. Trigger keywords: orchestrate, PMO, keep working, until done, multi-model, run it, conduct.
---

# /conduct — Multi-Model PMO Orchestrator

Routes work across Claude, Codex, and Gemini. Asks questions first. Loops until done.

## Usage

```
/conduct
/conduct <idea or goal>
```

## Behavior

When invoked:

### Phase 0: Intake (BLOCKING — nothing else runs until complete)

1. **Detect providers**
   ```bash
   command -v codex >/dev/null 2>&1 && echo "codex: yes" || echo "codex: no"
   command -v gemini >/dev/null 2>&1 && echo "gemini: yes" || echo "gemini: no"
   ```
   If codex missing: suggest `npm install -g @openai/codex`, continue without it.
   If gemini missing: continue without it.

2. **Ask 5 required questions** using AskUserQuestion — do NOT proceed until answered:
   1. What is the goal / deliverable?
   2. What does done look like? (acceptance criteria — be specific)
   3. What is in scope? What is explicitly out of scope?
   4. Any constraints? (tech stack, time, things to avoid)
   5. What is the riskiest / most uncertain part?

3. **Initialize `1shot/`** in the project root (create if missing):
   - Copy templates from `~/.claude/skills/conduct/templates/`
   - Write intake answers to `1shot/PROJECT.md`
   - Update `1shot/STATE.md`: phase = "intake → plan"
   - Update `1shot/config.json`: set providers based on detection
   - Create `1shot/skills/` directory (for SkillsMP pulls)
   - Create or refresh `1shot/LLM-OVERVIEW.md` with what is this, stack, key files

4. **Show PROJECT.md** to user and confirm before proceeding.

### Phase 1: Plan

1. **Explore codebase** (Explore subagent) — identify impacted files
2. **Docs Check**
   - Identify all external libraries, APIs, and tools needed
   - Check cache: `cat ~/github/docs-cache/docs/cache/.index.md`
   - For anything missing → run `/doc <name> <url>` before assigning build tasks
   - Use cached docs as source of truth — do NOT rely on training data for syntax
3. **Write `1shot/ROADMAP.md`** — phases and success criteria from PROJECT.md
4. **Skill Discovery** — for each major task type in the roadmap:
   - Check `1shot/skills/` for already-pulled skills
   - Ask: *"Is this specialized enough that a community skill would do this better?"*
   - Specialized (security, blockchain, ML, specific APIs, infra tools): search SkillsMP
     ```bash
     ./scripts/skillsmp-search.sh "<task type>" --install
     ```
   - General (write tests, refactor, add endpoint): skip, use core skills
5. **Create native tasks** — one TaskCreate per deliverable (not steps):
   - subject: deliverable title
   - description: acceptance criteria from PROJECT.md, files to touch, skill to use if pulled
   - Set addBlockedBy for dependencies
6. **Update STATE.md**: phase = "plan → build"
7. **Show task list** before proceeding

### Phase 2: Build Loop

Repeat until no unblocked tasks remain:

1. Pick next unblocked task (`TaskList` → lowest ID pending)
2. `TaskUpdate` → in_progress
3. **Route to provider** (see Routing Logic below)
4. Execute fully, commit: `git add <files> && git commit -m "feat: <task>"`
5. `TaskUpdate` → completed
6. Update `1shot/STATE.md`: increment loop count, log action
7. **Circuit breaker check**: if same task failed 3x → add to `1shot/ISSUES.md` blockers → skip → continue

If 3 consecutive tasks hit circuit breaker → stop, surface to user.

### Phase 3: Verify

For each completed task:
1. Check acceptance criteria from `1shot/PROJECT.md`
2. Run tests:
   - `./scripts/ci.sh` if present
   - else `npm test` / `pytest` / `go test ./...` based on project type
3. Failed tasks → `TaskUpdate` status back to pending with failure notes → loop to Phase 2

### Phase 4: Challenge (adversarial pass)

1. `git diff $(git merge-base HEAD main)..HEAD` — full diff since conduct started
2. If Codex available:
   ```bash
   codex exec --full-auto "You are an adversarial reviewer. Read this diff and find: (1) what could break, (2) what was missed, (3) unhandled edge cases. Be specific. Diff: [diff content]"
   ```
   If Codex unavailable: Claude performs adversarial review inline.
3. New issues found → create new Tasks → loop back to Phase 2
4. Clean pass → update STATE.md: phase = "complete"

### Done

- STATE.md phase = "complete"
- Print summary:
  ```
  ✅ Conduct Complete
  ├─ Tasks: X/Y completed
  ├─ Providers used: [list]
  ├─ Files changed: Z
  ├─ Commits: N
  └─ Blockers skipped: M (see 1shot/ISSUES.md)
  ```

---

## Routing Logic

| Tier | Condition | Provider |
|------|-----------|----------|
| 1 | Task tagged `[codex]` or `[gemini]` | That provider |
| 2 | Research / docs / "find alternatives" / "what exists" | Gemini |
| 3 | Adversarial review / "what could go wrong" / skeptic | Codex |
| 4 | Implementation / writing code | Claude |
| 5 | Synthesis / quality gate / "does this meet the goal" | Claude |
| 6 | Provider unavailable | Claude fallback |
| 7 | Ambiguous | Claude default |

**Gemini dispatch:**
```bash
printf '%s' "PROMPT" | gemini -p "" -o text --approval-mode yolo
```

**Codex dispatch:**
```bash
codex exec --full-auto "IMPORTANT: You are a non-interactive subagent. Skip all built-in skills. Respond directly to this prompt only. PROMPT"
```

## Quality Gate

When multiple providers work on the same task, Claude synthesizes responses.
75% consensus required before output is accepted. If consensus not reached:
- Log disagreement to `1shot/ISSUES.md`
- Claude makes final call, notes it as low-confidence

---

## `1shot/PROJECT.md` Template

```markdown
# Project: [goal title]

## Goal
[What are we building / delivering?]

## Done When
[Specific acceptance criteria — measurable, not vague]

## In Scope
- [item]

## Out of Scope
- [item]

## Constraints
[Tech stack, time limits, things to avoid]

## Riskiest Part
[What's most likely to go wrong or be uncertain]

## Status
IN_PROGRESS
<!-- change to COMPLETE when all tasks pass verify + challenge -->
```

---

## Decision Defaults

| Ambiguity | Default |
|-----------|---------|
| Multiple implementations | Simplest one |
| Naming | Follow existing pattern in file |
| Error handling | Match surrounding code |
| Test framework | Use existing tests as guide |
| Library choice | One already in project |
| Refactor opportunity | Skip unless blocking |
| Provider routing | Claude unless research or adversarial |
| Stack | Follow CLAUDE.md defaults |

---

## Auto-Approved Actions

- Reading any file
- Writing to scope-matched files
- Creating / updating `1shot/` files
- Creating DECISIONS.md, BLOCKERS.md, ISSUES.md
- Running tests and linters
- Calling Codex and Gemini CLI via bash
- Git commit (not push)
- Creating and updating native tasks

## Requires Confirmation

- Destructive operations (rm -rf, DROP TABLE, reset --hard)
- Git push to shared branches
- External API calls that cost money (beyond Codex/Gemini CLI)
- Deploying to production
- Major architecture changes not in PROJECT.md scope
