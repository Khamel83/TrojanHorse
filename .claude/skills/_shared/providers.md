# Shared Provider Routing Module

Reference this module from any skill that needs delegation or multi-model routing.
This is a DRY reference — skills include it by mention, not import.

---

## Provider Detection

```bash
command -v codex >/dev/null 2>&1 && echo "codex: yes" || echo "codex: no"
command -v gemini >/dev/null 2>&1 && echo "gemini: yes" || echo "gemini: no"
[ -d ~/github/claw-code-agent/src ] && echo "claw_code: yes" || echo "claw_code: no"
[ -n "$ZAI_API_KEY" ] && echo "zai: yes" || echo "zai: no"
[ -n "$OPENROUTER_API_KEY" ] && echo "openrouter: yes" || echo "openrouter: no"
python -c "from core.search.argus_client import is_available; print('argus:', is_available())" 2>/dev/null || echo "argus: no"
```

**Fallback chain for cheap lane**: codex → gemini_cli → claw_code
Within claw_code, model routing is automatic:
- GLM models (`glm-5.1`, `glm-4.7`, etc.) → ZAI endpoint (free on plan)
- Everything else → OpenRouter (paid)

`strategy: first_available` is implemented in `core/dispatch/run.py`.

Also read `config/workers.yaml` for machine-level worker placement (if it exists — skip silently if not).

---

## Lane-Based Routing

**Route by task class, not provider name.** See `docs/instructions/task-classes.md`.

```
task → task_class → lane → worker_pool → reviewer
```

Resolve routing:
```bash
python -m core.router.resolve --class <task_class>
```

Returns JSON: `{task_class, lane, workers[], review_with, search_backend, fallback_lane}`

---

## Lane Summary

| Lane | Planner | Workers (first_available order) | Review |
|------|---------|----------------------------------|--------|
| premium | claude_code | claude_code, codex | claude_code |
| balanced | claude_code | codex, gemini_cli | claude_code |
| cheap | claude_code | gemini_cli → codex → glm_claude | claude_code |
| research | claude_code | gemini_cli, codex | claude_code |

**glm_claude**: `claude` CLI running on ZAI/GLM-5-turbo via `ANTHROPIC_BASE_URL`. Full native toolchain (bash, read, edit, glob, grep, git). Free on GLM Coding Plan (expires **2026-05-02**). Same dispatch pattern as codex/gemini — `claude --print --dangerously-skip-permissions "prompt"`.

**claw_code**: Available but **manual opt-in only** (not in lane pools). Re-enable by adding `claw_code` back to `worker_pool` in `config/lanes.yaml`. Use `--worker claw_code` flag on dispatch.

---

## Category-Based Worker Preference

Each lane has `category_preference` in `config/lanes.yaml` that reorders workers
when the task category is known. Workers not in the preference list are appended
in their original pool order.

```
task → task_class → lane → category_preference[category] → reordered workers
```

| Category | Cheap Lane Preference | Balanced | Premium | Research |
|----------|-----------------------|----------|---------|----------|
| coding | codex, gemini_cli, glm_claude | codex, gemini_cli | claude_code, codex | codex, gemini_cli |
| research | gemini_cli, codex, glm_claude | gemini_cli, codex | claude_code, codex | gemini_cli, codex |
| writing | gemini_cli, codex, glm_claude | gemini_cli, codex | claude_code, codex | gemini_cli, codex |
| review | codex, glm_claude, gemini_cli | codex, gemini_cli | claude_code, codex | codex, gemini_cli |
| general | gemini_cli, codex, glm_claude | codex, gemini_cli | claude_code, codex | gemini_cli, codex |

Category is inferred from task_class by default, or passed explicitly via `--category`.
Inferred mapping: plan→general, research/search_sweep→research, implement_*/test_write→coding,
review_diff→review, doc_draft/summarize_findings→writing.

## claw_code Worker Model Priority

Used when codex and gemini_cli are unavailable. Priority order in `config/models.yaml`:

**ZAI (free on GLM Coding Plan, expires 2026-05-02):**

glm_claude harness → `api.z.ai/api/anthropic` (Anthropic-compat, full claude CLI):

| Model | Cost | Strengths |
|-------|------|-----------|
| glm-5-turbo | free | fast, strong coding+reasoning — **default** |

claw_code harness → `api.z.ai/api/coding/paas/v4` (OpenAI-compat, claw-code-agent):

| Model | Cost | Strengths |
|-------|------|-----------|
| glm-5-turbo | free | **default fallback** |
| glm-5.1 | free | deep reasoning |
| glm-4.7 | free | balanced |
| glm-4.5-air | free | throughput |

**OpenRouter (paid) — routed to `openrouter.ai/api/v1`:**

| Model | Input/M | Output/M | Strengths |
|-------|---------|----------|-----------|
| deepseek/deepseek-v3.2 | $0.26 | $0.38 | coding, low-cost |
| google/gemini-2.5-flash-lite | $0.10 | $0.40 | throughput, cheapest |
| minimax/minimax-m2.7 | $0.30 | $1.20 | long context |
| moonshotai/kimi-k2.5 | $0.38 | $1.72 | strong agentic |

All models support tool calling. Key env vars: `ZAI_API_KEY` (in `research_keys.env`), `OPENROUTER_API_KEY` (in `services.env`).

---

## Dispatch Commands

**Codex** (adversarial review, challenge, worker tasks):

Structured output (preferred for all programmatic dispatch):
```bash
unset OPENAI_API_KEY && codex exec --json --sandbox danger-full-access "PROMPT"
# Returns JSONL stream: thread.started, turn.started, item.*, turn.completed
# Parse final agent message:  | jq 'select(.type == "item.completed") | select(.item.type == "agent_message")'
```

Quick single-run with last-message capture:
```bash
unset OPENAI_API_KEY && codex exec --sandbox danger-full-access -o /tmp/codex-output.txt "PROMPT"
```

Structured output with schema (for downstream processing):
```bash
unset OPENAI_API_KEY && codex exec --sandbox danger-full-access --output-schema ./schema.json -o ./result.json "PROMPT"
```

Resume a previous session:
```bash
unset OPENAI_API_KEY && codex exec resume --last "follow-up prompt"
```

**Gemini** (research fallback):
```bash
printf '%s' "PROMPT" | gemini -p "" -o text --approval-mode yolo
```

**Claw Code** (OpenRouter models — cheap lane):
```bash
cd ~/github/claw-code-agent && \
OPENAI_BASE_URL=https://openrouter.ai/api/v1 \
OPENAI_MODEL=openai/gpt-4o-mini \
python3 -m src.main agent "PROMPT" --cwd /path/to/repo --allow-write --allow-shell
```
Model is configurable via `OPENAI_MODEL` env var or `--model` flag on dispatch.
See `config/models.yaml` `claw_code` section for supported models.

**Argus** (search):
```bash
curl -s -X POST http://100.126.13.70:8005/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "QUERY", "mode": "discovery"}'
```

---

## Worker Placement

From `config/workers.yaml`:
- `local` (localhost) — planner, claude_code
- `oci` (oci-dev) — planner, claude_code
- `claw` (localhost) — worker, claw_code (OpenRouter models)
- `macmini` — worker, opencode (future)
- `homelab` — worker, opencode (future)

Dispatch to remote worker via SSH when configured.

---

## Quality Gate

75% consensus required when multiple providers contribute. If not reached:
- Log disagreement to `1shot/ISSUES.md`
- Claude makes final call

---

## Circuit Breaker

- Same task fails 3x → log blocker → skip → continue
- 3 consecutive tasks fail → stop, surface to user
- Lane escalation: cheap → balanced → premium → inline (Claude handles directly)
