# ONE_SHOT v14 — Orchestration Control Plane

> Category-based routing. Claude plans, workers execute. Argus searches. Janitor runs in the background.

## OPERATORS

### `/short` — Quick Iteration
1. Load context: git log -5, TaskList, DECISIONS.md, BLOCKERS.md
2. Ask: "What are you working on?"
3. Execute via dispatch protocol (non-premium tasks → best worker for category)
4. Show delegation summary

### `/full` — Structured Work
1. Create/load IMPLEMENTATION_CONTEXT.md
2. Structured intake: goals, scope, architecture, constraints
3. Phase-based planning with milestones
4. Execute via dispatch protocol (parallel workers, category-ordered)
5. Context checkpoints (50% → suggest handoff, 70% → auto-handoff)
6. Verify and show completion summary

### `/conduct` — Multi-Model Orchestration
1. Detect available providers (read `config/workers.yaml`)
2. Ask clarifying questions — BLOCKING
3. Classify tasks by task class + category (see `docs/instructions/task-classes.md`)
4. Route: task class → lane → category preference → worker pool → reviewer
5. Dispatch non-premium tasks in parallel via dispatch protocol
6. Loop until goal is fully met

## DISPATCH PROTOCOL

All non-premium tasks use the dispatch protocol (`_shared/dispatch.md`):
- Classify task by class and category
- Resolve lane + worker ordering via `python3 -m core.router.resolve --class <class> --category <category>`
- Workers are ordered by category preference — first available wins
- Structured output captured and validated
- Manifests written to `1shot/dispatch/{id}.md`

```
classify → resolve (category-ordered workers) → build prompt → dispatch → capture → validate → commit
```

## TASK CLASSES & CATEGORY ROUTING

Tasks are classified by task class AND category. Category determines worker preference within a lane.

| Task Class | Lane | Category | Preferred Workers |
|-----------|------|----------|-------------------|
| plan | premium | general | claude_code |
| research | research | research | gemini_cli, codex |
| implement_small | cheap | coding | codex, gemini_cli, glm_claude |
| implement_medium | balanced | coding | codex, gemini_cli |
| test_write | cheap | coding | codex, gemini_cli, glm_claude |
| review_diff | premium | review | claude_code, codex |
| doc_draft | cheap | writing | gemini_cli, codex, glm_claude |
| search_sweep | research | research | gemini_cli, codex + argus |
| summarize_findings | cheap | writing | gemini_cli, codex, glm_claude |
| janitor_summarize | janitor | general | free (openrouter/free) |
| janitor_extract | janitor | general | free (openrouter/free) |
| janitor_hygiene | janitor | general | free (openrouter/free) |
| janitor_analyze | janitor | general | free (openrouter/free) |

Resolve routing: `python3 -m core.router.resolve --class <task_class> --category <category>`
Parallel dispatch: `python3 -m core.dispatch.run --class <class> --category <category> --prompt "..."`

## INTELLIGENCE TIERS

| Worker | Backend | Cost | Notes |
|--------|---------|------|-------|
| glm_claude | ZAI/GLM-5-turbo | Free until 2026-05-02 | Full Claude Code session, all tools |
| codex | ChatGPT Plus | $20/mo sub | Strong coding, structured output |
| gemini_cli | Google API | Free (sign-in) | Research, documentation |
| free | openrouter/free | $0 (always) | Background intelligence, janitor lane only |
| claw_code | OpenRouter | Pay per token | Manual opt-in via `--worker claw_code` |

Auto-expiry: `glm_claude` worker checks `plan_expires` from `config/workers.yaml` and disables itself when expired. `shot` terminal command auto-falls back to OpenRouter.

## UTILITY COMMANDS

| Command | Purpose |
|---------|---------|
| `/handoff` | Save context before /clear |
| `/restore` | Resume from handoff |
| `/research` | Background research via Argus |
| `/freesearch` | Zero-token search via Argus (cheap mode) |
| `/doc` | Cache external documentation |
| `/vision` | Image/website analysis |
| `/secrets` | SOPS/Age secrets management |
| `/debug` | Systematic debugging (4-phase: investigate → analyze → hypothesize → fix) |
| `/tdd` | Test-driven development (RED-GREEN-REFACTOR cycle) |

## TERMINAL ENTRY POINTS

| Command | Purpose |
|---------|---------|
| `shot "task"` | Auto-route to best model (GLM free → OpenRouter fallback) |
| `zai` | Force GLM-5-turbo via ZAI (free) |
| `or` | Force OpenRouter model (paid) |
| `or --code` | Force Qwen3-Coder (free on OpenRouter) |

## PLANNER/WORKER SPLIT

**Planner (Claude)**: planning, decomposition, repo synthesis, review, sensitive edits
**Workers (Codex, Gemini, GLM)**: bounded implementation, tests, docs, search summarization
**Dispatch**: category-ordered parallel execution with structured output and manifest tracking

## DECISION DEFAULTS

| Ambiguity | Default |
|-----------|---------|
| Multiple implementations | Simplest |
| Naming | Follow existing pattern |
| Refactor opportunity | Skip unless blocking |
| Lane selection | Use task class routing |

## AUTO-APPROVED

Reading files, writing to scope-matched files, running tests, git commit (not push), creating tasks.

## REQUIRES CONFIRMATION

Destructive ops, git push, external API calls that cost money, production deploy.

## V2 FEATURES

- Risk-based autonomy gating: `RiskLevel` (low/medium/high) controls what requires confirmation
- Structured exploration artifact: `explore.json` from intake phase
- Machine-readable plan schema: `plan.json` via `core/plan_schema.py`
- TASK_SPEC template: `templates/TASK_SPEC.md` for formal task specification
- Mandatory verification gate after each build step
- Scope creep detection in the build loop
- Session-end feedback loop: handoff proposes CLAUDE.md/rule updates when patterns repeat

## JANITOR SYSTEM

Background intelligence layer that runs automatically — no manual action needed.

**How it works:**
1. **PostToolUse hook** records every file read/write/edit to `.oneshot/events.jsonl` (transparent, zero overhead)
2. **System cron** (every 15min) finds unprocessed events across all projects, runs free model summarizer
3. **SessionEnd hook** marks session as ended; cron picks up remaining data

**What it produces:** structured decisions, blockers, discoveries, file change summaries — all queryable across sessions via grep, SQLite, or future sessions.

**Cost:** $0. openrouter/free model router. ~60-150 calls/day. Storage: ~30MB/year.

**Files:** `core/janitor/` — worker.py (OpenRouter caller), recorder.py (event log), jobs.py (job implementations), jobs_catalog.md (planned jobs)

**Cron install (all machines):** Already installed on oci-dev, homelab, macmini.

## SHARED MEMORY

Read `.claude/memory/memory.md` at session start for cross-agent learnings.
When you discover something useful for other agents, append a dated entry to the relevant file.

## VERSION

v14.3 | Janitor lane | Background intelligence | openrouter/free worker | Session recording
