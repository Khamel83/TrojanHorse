# ONE_SHOT v14 — Orchestration Operating Contract

> Works in any project on any machine. Claude plans, workers execute, Argus searches, Janitor runs in the background.

---

## OPERATORS

### `/short` — Quick Iteration
1. Load context: `git log -5`, TaskList, DECISIONS.md, BLOCKERS.md
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
1. Check available workers (see INTELLIGENCE TIERS below)
2. Ask clarifying questions — BLOCKING, nothing runs until answered
3. Classify each task by task class + category
4. Route via the ROUTING TABLE below — first available worker in preferred order wins
5. Dispatch non-premium tasks in parallel
6. Loop until goal is fully met

---

## ROUTING TABLE

Classify tasks by class AND category. Category determines worker order within a lane.

| Task Class | Lane | Category | Worker Order |
|---|---|---|---|
| `plan` | premium | general | claude_code |
| `research` | research | research | gemini_cli → codex |
| `implement_small` | cheap | coding | codex → gemini_cli → glm_claude |
| `implement_medium` | balanced | coding | codex → gemini_cli |
| `test_write` | cheap | coding | codex → gemini_cli → glm_claude |
| `review_diff` | premium | review | claude_code → codex |
| `doc_draft` | cheap | writing | gemini_cli → codex → glm_claude |
| `search_sweep` | research | research | gemini_cli → codex (+ Argus) |
| `summarize_findings` | cheap | writing | gemini_cli → codex → glm_claude |
| `janitor_*` | janitor | general | openrouter/free only |

**In the oneshot project**, use the Python resolver:
```bash
python3 -m core.router.resolve --class implement_small --category coding
```

**In any other project**, read the table directly and pick the first available worker.

---

## DISPATCH PROTOCOL

```
classify task → pick worker from routing table → build self-contained prompt → dispatch → capture output → validate → commit
```

1. Classify: pick `task_class` + `category` from the table above
2. Pick worker: first available in the preferred order for that class
3. Build prompt: self-contained — include all context the worker needs, no shared state
4. Dispatch using the worker command below
5. Capture structured output, validate it meets the task goal
6. Manifests written to `1shot/dispatch/{id}.md` if the dir exists

---

## INTELLIGENCE TIERS & WORKER COMMANDS

| Worker | Cost | How to invoke |
|---|---|---|
| `glm_claude` | Free (ZAI plan, check expiry) | `zai` — full Claude Code session via GLM-5-turbo |
| `codex` | $20/mo (ChatGPT Plus sub) | `unset OPENAI_API_KEY && codex exec --sandbox danger-full-access "prompt"` |
| `gemini_cli` | Free (Google sign-in) | `gemini "prompt"` or `gemini -p "prompt"` |
| `free` | $0 always | OpenRouter free pool — janitor lane only, not for user tasks |
| `claw_code` | Pay per token | Manual opt-in only — `--worker claw_code` |

**glm_claude expiry:** Check `config/workers.yaml → plan_expires` in the oneshot project. After expiry, `zai` falls back to OpenRouter via the `shot` command.

**SSH dispatch** (run worker on a specific machine):
```bash
ssh oci-ts "cd ~/github/PROJECT && unset OPENAI_API_KEY && codex exec --sandbox danger-full-access 'prompt'"
ssh macmini-ts "cd ~/github/PROJECT && gemini 'prompt'"
```

---

## SEARCH (ARGUS)

All web search routes through Argus on homelab.

- **HTTP API**: `http://100.112.130.100:8270/api/search`
- **MCP tool** (Claude Code): `mcp__argus__search_web` — registered in `~/.claude/settings.json`

```bash
# From code
curl -s -X POST http://100.112.130.100:8270/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "...", "mode": "discovery"}'

# From Python (oneshot project)
from core.search.argus_client import search
results = search("query", mode="precision")
```

| Mode | Providers | Use for |
|---|---|---|
| `discovery` | SearXNG, Brave, Exa | Broad exploration |
| `precision` | Serper, Tavily | Targeted, high-relevance |
| `cheap` | SearXNG only | Quick lookups |
| `research` | All providers | Deep, comprehensive |

**In Claude Code**: just ask — Claude calls `mcp__argus__search_web` automatically. Use `/research` for background deep search, `/freesearch` for zero-token quick lookups.

**Fallback**: if Argus is unreachable (homelab down), use `gemini` CLI for research tasks.

---

## SECRETS

Vault: `~/github/oneshot/secrets/` — single source of truth, synced to all machines.
CLI: `secrets` — available everywhere after `bash ~/github/oneshot/install.sh`.

```bash
secrets get KEY                     # fetch one value
secrets set FILE KEY=value          # add/update a key
secrets set FILE KEY=value --commit # add, commit, and push
secrets init FILE                   # write FILE.env → .env in current dir
secrets list                        # show all vault files and key names
```

Full vault file index: `~/github/oneshot/docs/instructions/secrets.md`

---

## STACK DEFAULTS

Pick the right stack without asking. Detect from project files:

| Detection | Type | Stack |
|---|---|---|
| `vercel.json` or `supabase/` | Web app | Vercel + Supabase (Auth + Postgres) + Python + HTML/JS |
| `setup.py` or `pyproject.toml` | CLI | Python + Click + SQLite |
| `*.service` systemd file | Service | Python + systemd → oci-dev |
| Docker Compose | Service | Deploy to homelab via `hl remote-recreate-SERVICE` |

**Never use**: nginx/traefik (use Tailscale Funnel), self-hosted Postgres (use Supabase), Express/FastAPI for web (use Python serverless on Vercel), AWS/GCP/Azure (use OCI free tier or homelab).

---

## PLANNER / WORKER SPLIT

**Planner (Claude)**: planning, decomposition, repo synthesis, final review, sensitive edits (auth, data mutation, production deploys)

**Workers (Codex, Gemini, GLM)**: bounded implementation, test generation, doc drafting, search summarization

**Rule**: never delegate planning or review. Never let a worker touch auth, secrets, or production without planner review.

---

## DECISION DEFAULTS

| Ambiguity | Default |
|---|---|
| Multiple implementations | Simplest |
| Naming | Follow existing pattern in repo |
| Refactor opportunity | Skip unless blocking |
| Error handling | Match surrounding code |
| Stack choice | Follow detection table above |
| Lane selection | Use routing table above |

---

## AUTO-APPROVED

Reading files, writing to scope-matched files, running tests, `git commit` (not push), creating tasks, calling Argus search.

## REQUIRES CONFIRMATION

Destructive ops (`rm -rf`, DROP TABLE), `git push`, external API calls that cost money, production deploy, force push.

---

## UTILITY SKILLS (Claude Code)

| Skill | Purpose |
|---|---|
| `/handoff` | Save context before `/clear` |
| `/restore` | Resume from handoff |
| `/research` | Background research via Argus |
| `/freesearch` | Zero-token search via Argus cheap mode |
| `/doc` | Cache external documentation locally |
| `/vision` | Analyze images or websites |
| `/secrets` | Manage vault interactively |
| `/debug` | 4-phase systematic debugging |
| `/tdd` | RED-GREEN-REFACTOR cycle |
| `/adversarial-review` | Gemini second-opinion on design decisions |

---

## TERMINAL ENTRY POINTS

| Command | Purpose |
|---|---|
| `shot "task"` | Auto-route: GLM free → OpenRouter fallback |
| `zai` | Force GLM-5-turbo via ZAI |
| `or` | Force OpenRouter model |
| `or --code` | Force Qwen3-Coder (free) |

---

## JANITOR (BACKGROUND INTELLIGENCE)

Runs automatically on all machines — no action needed. Cost: $0.

1. PostToolUse hook records file reads/writes/edits → `.janitor/events.jsonl`
2. Cron (every 15 min) processes events, runs free model summarizer
3. Produces: test gap analysis, code smells, dep map, staleness, onboarding summary

Signal files in `.janitor/` — read on demand, never block on them.

---

## SHARED MEMORY

Read `.claude/memory/memory.md` at session start for cross-agent learnings.
When you discover something useful for other agents, append a dated entry.

---

## VERSION

v14.4 | Self-contained cross-project contract | Search, secrets, stack defaults, worker commands
<!-- janitor:begin:capability -->
## Shared agent capability: g2k

g2k is the shared remote model-routing and GitHub issue-to-PR capability for
this workspace.

A model may be running locally on the Mac or another machine, but g2k's
provider access, unattended workers, routing, state, and credentials live on
the OCI VM. Local machines are callers or observers, not alternate g2k homes.

Use g2k/OMP when available instead of creating another provider integration.
Use GitHub issues and pull requests for durable work. Do not assume that local
provider credentials, filesystem state, or a local g2k daemon exists. See
`INFRA.md` for the machine-specific access path and boundaries.
<!-- janitor:end:capability -->
<!-- janitor:begin:working-docs -->
## Keep the working docs current

Update these files whenever they become wrong, not on every turn, and commit
them with the work they describe:

- `TODO.md`: when you start, finish, add, or drop a task. Mark finished items
  `[x]` with evidence; strike dropped items with a reason.
- `CONTEXT.md`: when the owner makes a decision or the verified state changes.
- `HANDOFF.md`: before you stop or hand off: what is done, what is in flight,
  the next step, and the commands that recheck it.
- `INFRA.md`: when a host, service, port, credential location, or deploy path
  changes.

A change is not done until it is deployed and verified. If the repository has
a deploy command or automation, run it (or confirm it ran) and check the
result. Registration steps the deploy depends on (for example a consumer list
or catalog entry) are part of the change. Never leave a "remember to run X"
step for the owner; if something truly needs the owner, write it in
`HANDOFF.md` as a blocker with the exact command.
<!-- janitor:end:working-docs -->
