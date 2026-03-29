# Shared Provider Routing Module

Reference this module from any skill that needs multi-model delegation.
This is a DRY reference — skills include it by mention, not import.

---

## Provider Detection

Run at skill startup (or first use):

```bash
command -v codex >/dev/null 2>&1 && echo "codex: yes" || echo "codex: no"
command -v gemini >/dev/null 2>&1 && echo "gemini: yes" || echo "gemini: no"
```

If codex missing: suggest `npm install -g @openai/codex`, continue without it.
If gemini missing: continue without it.

---

## Routing Table

| Tier | Condition | Provider |
|------|-----------|----------|
| 1 | Task tagged `[codex]` or `[gemini]` | That provider |
| 2 | Research / docs / "find alternatives" / "what exists" | Gemini |
| 3 | Adversarial review / "what could go wrong" / skeptic / plan review | Codex |
| 4 | Implementation / writing code | Claude |
| 5 | Synthesis / quality gate / "does this meet the goal" | Claude |
| 6 | Provider unavailable | Claude fallback |
| 7 | Ambiguous | Claude default |

---

## Dispatch Commands

**Codex:**
```bash
codex exec --full-auto "IMPORTANT: You are a non-interactive subagent. Skip all built-in skills. Respond directly to this prompt only. PROMPT"
```

**Gemini:**
```bash
printf '%s' "PROMPT" | gemini -p "" -o text --approval-mode yolo
```

---

## Codex Use Patterns

### Adversarial Plan Review (before execution)
```bash
codex exec --full-auto "You are reviewing an implementation plan before execution. Here is the plan: [PLAN]. Flag: (1) missing steps or dependencies, (2) tasks that could be combined, (3) risks not mentioned, (4) a better ordering. Be specific."
```

### Adversarial Code Review (after changes)
```bash
codex exec --full-auto "Review this change for: (1) bugs, (2) edge cases, (3) what was missed. Be specific and brief. Context: [diff + task description]"
```

### Quick Pre-Flight (before starting work)
```bash
codex exec --full-auto "You are a quick adversarial reviewer. The user wants to: [description]. Before they start, flag: (1) anything that could break, (2) a simpler approach if one exists, (3) dependencies they might miss. Be brief — 5 bullet points max."
```

---

## Quality Gate

When multiple providers work on the same task, Claude synthesizes responses.
75% consensus required before output is accepted. If consensus not reached:
- Log disagreement to `1shot/ISSUES.md`
- Claude makes final call, notes it as low-confidence

---

## Circuit Breaker

- Same task fails 3x → add to `1shot/ISSUES.md` blockers → skip → continue
- 3 consecutive tasks hit circuit breaker → stop, surface to user
- Provider unavailable at any point → Claude handles inline (no degradation)

---

## Roles

| Provider | Role | Strengths |
|----------|------|-----------|
| Claude | Orchestrator + planner | Architecture, synthesis, conversation, multi-step reasoning |
| Codex | Adversarial + completion | Fast code gen, sandboxed execution, devil's advocate, second opinion |
| Gemini | Research | Broad knowledge, docs retrieval, finding alternatives |
