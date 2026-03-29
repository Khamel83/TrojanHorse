# ONE_SHOT v13 — Operator Framework

**10 skills.** Three operators. Seven utilities.

---

## Operators

| Skill | Purpose |
|-------|---------|
| `/short` | Quick iterations on existing projects |
| `/full` | New projects, refactors, complex work |

### /short — Quick Iteration

Fast operator for existing work:
- Loads recent context (git log, tasks, decisions)
- Asks: "What are you working on?"
- Discovers relevant skills on demand
- Executes in burn-down mode
- Shows delegation summary on completion

### /full — Structured Work

Full operator for complex tasks:
- Creates IMPLEMENTATION_CONTEXT.md
- Structured intake and discovery
- Phase-based planning with milestones
- Skill discovery via this index
- Execution with context checkpoints
- Completion summary

---

## Utility Skills

| Skill | Purpose |
|-------|---------|
| `/handoff` | Save context before /clear |
| `/restore` | Resume from handoff |
| `/research` | Background research mode |
| `/doc` | Cache external documentation |
| `/freesearch` | Zero-token web search (Exa) |
| `/vision` | Image/website visual analysis |
| `/secrets` | SOPS/Age secrets management |

---

## Architecture

```
Menu-based (old):
25+ slash commands → user picks one → executes

Operator-based (v13):
/short or /full → discover skills → execute → summary
```

**Why?** Reduced complexity, fewer commands to maintain, skill discovery happens when needed.

---

## Where Skills Live

```
~/.claude/skills/<name>/SKILL.md  → Personal skills (available in all projects)
```

### Required Format

Each SKILL.md MUST have this frontmatter:

```yaml
---
name: skill-name
description: What it does and WHEN to use it. Include trigger keywords.
---
```

**Critical**: The `name:` field is REQUIRED. Without it, the skill won't be discovered.

### Example

```
~/.claude/skills/
├── short/
│   └── SKILL.md
├── full/
│   └── SKILL.md
├── handoff/
│   └── SKILL.md
└── ...
```

### Why Commands Didn't Work

Claude Code v2.1+ uses the **skills** system, not `~/.claude/commands/`.

- Skills are **model-invoked** — Claude decides when to use them based on description
- Commands were **user-invoked** — required explicit `/command` typing

The `~/.claude/commands/` directory is deprecated. Use `~/.claude/skills/` instead.

---

## Full Spec

See `AGENTS.md` for complete operator protocol, decision defaults, and auto-approval rules.
