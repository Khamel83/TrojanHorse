---
name: handoff
description: Create a structured handoff document to preserve context before /clear or /compact.
---

# /handoff — Save Context Before /clear

Create a structured handoff document to preserve context for seamless resumption.

## When to Use

- Before `/clear` or `/compact`
- Context running low (hook may auto-trigger at 80%)
- End of work session
- Switching tasks temporarily

## Handoff Document

Write to: `thoughts/shared/handoffs/YYYY-MM-DD-{slug}-handoff.md`

```markdown
# Handoff: [Task Name]

**Created**: YYYY-MM-DD HH:MM
**Context Used**: ~X% when created

## Quick Summary
[2-3 sentences]

## What's Done
- [x] Item 1 (commit: abc123)
- [x] Item 2 (commit: def456)

## In Progress
- [ ] Current task
  - Done: [specifics]
  - Remaining: [specifics]

## Not Started
- [ ] Remaining task 1
- [ ] Remaining task 2

## Active Files
- `src/auth/login.ts` — line 45-80 needs completion
- `tests/auth.test.ts` — 3 passing, 2 pending

## Key Decisions Made
1. Decision: [what] | Rationale: [why]

## Important Discoveries
- [Thing learned during implementation]

## Blockers / Open Questions
| # | Question | Status |
|---|---------|--------|
| 1 | [Question] | Waiting on user |

## Beads State
[If .beads/ exists: run bd sync, capture in-progress and ready tasks]

## Next Steps (Prioritized)
1. **Immediate**: [First thing when resuming]
2. **Then**: [Second priority]

## Resume
/restore @thoughts/shared/handoffs/YYYY-MM-DD-{slug}-handoff.md
```

## Process

1. Capture what's done (list completed tasks with commits)
2. Capture in-progress work (where exactly did you stop?)
3. Document key decisions and discoveries
4. Note blockers
5. Write prioritized next steps
6. If beads: `bd sync`
7. Commit handoff: `docs: create handoff for [feature]`

## Best Practices

- Create early (don't wait until context is exhausted)
- Be specific ("line 45 of login.ts" not "somewhere in login")
- Include reasoning (future you needs the "why")
- Commit immediately
