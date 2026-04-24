# Dispatch Protocol

Reference this module from any skill that needs to route work to external workers.
Skills include it by mention, not import. This is the single source of truth for
how Claude delegates execution to Codex and Gemini.

---

## Overview

```
Claude (thinker) → classify task → build prompt → dispatch to worker(s) → capture output → validate → commit or retry
```

Claude plans, reviews, and integrates. Codex and Gemini execute.

---

## Step 1: Classify and Resolve

For each task to dispatch:

1. Determine task class using `docs/instructions/task-classes.md`
2. Determine category (coding, research, writing, review, general) — infer from the task
   description keywords (implement/code/fix→coding, research/search→research,
   doc/write/summarize→writing, review/audit→review, default→general)
3. Resolve lane, worker pool (reordered by category preference), and routing:
   ```bash
   python3 -m core.router.resolve --class <task_class> --category <category>
   ```
   Returns: `{task_class, category, lane, workers[], review_with, search_backend, fallback_lane}`
   Workers are already ordered by category preference — first available wins.
   If the resolver fails (missing config, import error, etc.), execute inline with Claude. Skip dispatch.
4. Read `max_parallel` from `config/lanes.yaml` for the resolved lane
5. If lane is `premium` → execute inline with Claude (no dispatch). Stop here.
6. Otherwise → continue to Step 2

---

## Step 2: Build Self-Contained Prompt

Every dispatched task must be **fully self-contained**. The worker gets a prompt
that includes everything it needs — no back-reference to conversation context.

### Prompt Template

```markdown
## Task
{one-line description}

## Task Class
{task_class} — {lane}

## Acceptance Criteria
- {criterion 1}
- {criterion 2}
- ...

## Context: Files to Read
- `path/to/file1.py` — {why relevant}
- `path/to/file2.ts` — {why relevant}

## Patterns to Follow
{if applicable: "Follow the existing pattern in path/to/reference.py"}

## Constraints
- {constraint 1}
- {constraint 2}

## Output Format
Return your changes as file diffs. If creating new files, show the full content.
End with a summary of what you changed and any concerns.
```

### Prompt Construction Rules

- **Always include the full acceptance criteria** — the worker can't ask questions
- **Always list specific files to read** — the worker needs to know what matters
- **Always state output format** — structured output from both Codex and Gemini
- **Never reference conversation history** — the prompt must stand alone
- **Keep under 4000 words** — context window limits on cheaper models
- **If the task needs files changed, say which ones and what to change**
- **Include shared memory instruction** — prepend: "Read `.claude/memory/memory.md` for shared learnings from past sessions. If you discover something notable, append a dated entry."

---

## Step 3: Dispatch

### Worker Commands

**GLM Claude** (full Claude Code session on GLM-5-turbo via ZAI, free until 2026-05-02):
```bash
ZAI_KEY="$(secrets get ZAI_API_KEY 2>/dev/null)" && \
ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic" \
ANTHROPIC_AUTH_TOKEN="$ZAI_KEY" \
ANTHROPIC_API_KEY="" \
ANTHROPIC_DEFAULT_OPUS_MODEL="glm-5-turbo" \
ANTHROPIC_DEFAULT_SONNET_MODEL="glm-5-turbo" \
claude --print --dangerously-skip-permissions "{prompt}"
```

**Codex** (structured JSON output):
```bash
unset OPENAI_API_KEY && \
codex exec --json --sandbox danger-full-access \
  -o /tmp/dispatch-{id}.json \
  "{prompt}"
```

**Gemini** (structured JSON output):
```bash
gemini -p "{prompt}" \
  --output-format json \
  --approval-mode yolo \
  > /tmp/dispatch-{id}.json 2>/dev/null
```

**Gemini** (streaming JSONL for long tasks):
```bash
gemini -p "{prompt}" \
  --output-format stream-json \
  --approval-mode yolo \
  > /tmp/dispatch-{id}.jsonl 2>/dev/null
```

### Parallel Execution

Run multiple dispatches in parallel using background processes:

```bash
# Launch workers
codex exec --json --sandbox danger-full-access -o /tmp/dispatch-1.json "task 1" &
PID1=$!
gemini -p "task 2" --output-format json --yolo > /tmp/dispatch-2.json 2>/dev/null &
PID2=$!
codex exec --json --sandbox danger-full-access -o /tmp/dispatch-3.json "task 3" &
PID3=$!

# Wait for all
wait $PID1; STATUS1=$?
wait $PID2; STATUS2=$?
wait $PID3; STATUS3=$?

# Check results
[ $STATUS1 -eq 0 ] && echo "task 1: ok" || echo "task 1: failed (exit $STATUS1)"
[ $STATUS2 -eq 0 ] && echo "task 2: ok" || echo "task 2: failed (exit $STATUS2)"
[ $STATUS3 -eq 0 ] && echo "task 3: ok" || echo "task 3: failed (exit $STATUS3)"
```

**Limits**:
- Respect `max_parallel` from `config/lanes.yaml` (default 3)
- Codex: no documented concurrency limit — each `codex exec` is independent
- Gemini CLI: 60 req/min (Google Sign-in), 10 req/min (API key)
- Machine resource: don't exceed ~6 parallel processes on oci-dev

---

## Step 4: Capture and Parse Output

### Codex Output (JSONL)

Parse with `jq`:
```bash
# Final agent message
jq -s '[.[] | select(.type=="item.completed") | select(.item.type=="agent_message") | .item.text] | last' /tmp/dispatch-{id}.json

# All messages
jq -s '[.[] | select(.type=="item.completed") | select(.item.type=="agent_message")]' /tmp/dispatch-{id}.json

# Token usage
jq -s '[.[] | select(.type=="turn.completed") | .usage] | last' /tmp/dispatch-{id}.json

# Errors
jq -s '[.[] | select(.type=="error")]' /tmp/dispatch-{id}.json
```

### Gemini Output (JSON)

```bash
# Response text
jq -r '.response' /tmp/dispatch-{id}.json

# Session stats (tokens, duration)
jq '.stats' /tmp/dispatch-{id}.json

# Exit code tells success/failure
# 0 = success, non-zero = failure
```

### Gemini Output (Stream JSONL)

```bash
# Final result
jq -s '[.[] | select(.type=="result") | .data] | last' /tmp/dispatch-{id}.jsonl

# Tool calls made
jq -s '[.[] | select(.type=="tool_use")]' /tmp/dispatch-{id}.jsonl
```

---

## Step 5: Validate

After capturing output, validate against acceptance criteria:

1. **Check exit code**: 0 = success, non-zero = failure
2. **Check for errors in output**: parse error events from JSON
3. **Check acceptance criteria**: did the worker's output satisfy each criterion?
4. **If validation passes**: proceed to Step 6
5. **If validation fails**: proceed to Step 7 (retry/escalate)

---

## Step 6: Write Manifest

Write a manifest file for every dispatched task:

```
1shot/dispatch/{task-id}.md
```

### Manifest Format

```markdown
# Dispatch: {task-id}

## Status: succeeded | failed | retrying | escalated

## Task
- **Class**: {task_class}
- **Lane**: {lane}
- **Worker**: codex | gemini_cli
- **Prompt**: (truncated, first 200 chars)
- **Acceptance Criteria**: (from original task)

## Execution
- **Started**: {ISO timestamp}
- **Completed**: {ISO timestamp}
- **Duration**: {seconds}
- **Output file**: `/tmp/dispatch-{id}.json`
- **Exit code**: {code}
- **Tokens used**: {if available from JSON}

## Result
- **Passed validation**: yes | no
- **Summary**: {one-line of what happened}

## Retry History
- Attempt 1: {status}, {timestamp}
- Attempt 2: {status}, {timestamp} (if retried)
```

---

## Step 7: Retry and Escalation

### Retry Logic

- **Attempt 1**: dispatch to lane's worker pool
- **Attempt 2**: dispatch to fallback_lane (if configured)
- **Attempt 3**: Claude handles inline with full context

### When to Retry

- Worker exit code is non-zero
- Output contains errors
- Acceptance criteria not met
- Worker produced no useful output (empty response)

### When to Escalate Immediately

- The task involves auth, secrets, or data mutation
- The task requires repo-wide synthesis
- The prompt was malformed (Claude's fault — fix the prompt, not the worker)

### Circuit Breaker

If same task fails 3 times total:
1. Log to manifest with status `escalated`
2. Log to `BLOCKERS.md` or `1shot/ISSUES.md`
3. Skip to next task
4. If 3 consecutive tasks hit circuit breaker → stop, surface to user

---

## Step 8: Integrate and Commit

After successful dispatch:

1. **Read the worker's output** — understand what changed
2. **Read modified files** — confirm diffs match intent
3. **Run tests** if applicable: `./scripts/ci.sh` or project test command
4. **Commit**: `git add <files> && git commit -m "feat: <task description>"`
5. **Update manifest**: status = `succeeded`
6. **Update task tracker**: `TaskUpdate` completed

---

## Worker Selection

Worker ordering is **category-driven** via `config/lanes.yaml`. The resolver returns
workers already sorted by category preference. Just pick the first available.

| Category | Cheap Lane (first_available) | Balanced | Premium | Research |
|----------|------------------------------|----------|---------|----------|
| coding | codex → gemini_cli → glm_claude | codex → gemini_cli | claude_code → codex | codex → gemini_cli |
| research | gemini_cli → codex → glm_claude | gemini_cli → codex | claude_code → codex | gemini_cli → codex |
| writing | gemini_cli → codex → glm_claude | gemini_cli → codex | claude_code → codex | gemini_cli → codex |
| review | codex → glm_claude → gemini_cli | codex → gemini_cli | claude_code → codex | codex → gemini_cli |
| general | gemini_cli → codex → glm_claude | codex → gemini_cli | claude_code → codex | gemini_cli → codex |

No manual selection needed — `python3 -m core.router.resolve --class <class> --category <cat>`
returns the correct order. See `~/.claude/skills/_shared/providers.md` for full provider details.

## Terminal Entry Points

From the terminal (outside CC sessions), use shell functions:
- `shot "task"` — auto-routes to best model (GLM by default, falls back to OpenRouter when ZAI expires)
- `zai` — force GLM-5-turbo (ZAI, free)
- `or` — force OpenRouter model (paid)
- `or --code` — force Qwen3-Coder (OpenRouter, free)

Inside a CC session, use the dispatch protocol above to hand off tasks to workers.
