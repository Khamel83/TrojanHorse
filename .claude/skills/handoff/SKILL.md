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

## Learnings & Suggested Updates

Analyze the session for patterns that should be captured for future sessions:

### Commands & Workflows That Worked
- [Any CLI commands, tools, or workflows that were effective]

### Pitfalls Encountered
- [Errors, gotchas, or mistakes that future sessions should avoid]

### Assumptions That Were Wrong
- [Any initial assumptions that turned out to be incorrect]

### Suggested CLAUDE.md / Rule Updates
- [Specific lines or sections that would have helped — be precise]

### Suggested Instruction Updates
- [Changes to docs/instructions/ that would improve future sessions]

> For each suggestion, be specific. BAD: "Update docs". GOOD: "Add to .claude/rules/community.md: 'Email handler imports db lazily — patch api._supabase.db in tests, not api.handlers.email.db'"

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
6. Analyze session for learnings (see "Learnings & Suggested Updates" section)
7. If beads: `bd sync`
8. Commit handoff: `docs: create handoff for [feature]`
9. Review learnings and propose lesson saves (see Feedback Loop below)

## Feedback Loop: Propose Lesson Saves

After writing and committing the handoff document, review the "Learnings & Suggested Updates" section:

1. Scan for learnings that were encountered or noted **2+ times** during the session
   (e.g., a pitfall hit repeatedly, a workaround used more than once, a wrong assumption corrected and then referenced again)
2. Mark each repeated learning as a **lesson candidate**
3. Present proposals to the user:

```
I noticed these patterns during our session. Want me to save any as lessons?

1. [Pattern summary] — encountered N times
   Target: docs/instructions/learned/{date}-{topic}.md

2. [Pattern summary] — encountered N times
   Target: docs/instructions/learned/{date}-{topic}.md
```

4. If the user approves, write the lesson to `docs/instructions/learned/{date}-{topic}.md` and commit
5. If no learnings had 2+ occurrences, skip this step silently — do not propose one-off observations

**Important**: Do NOT automatically edit CLAUDE.md or instruction files. Only write to `docs/instructions/learned/` when the user explicitly approves.

## Best Practices

- Create early (don't wait until context is exhausted)
- Be specific ("line 45 of login.ts" not "somewhere in login")
- Include reasoning (future you needs the "why")
- Commit immediately
