---
name: restore
description: Restore context from a handoff document and continue work.
---

# /restore — Resume from Handoff

Restore context from a handoff document and continue work.

## Usage

`/restore` — finds most recent handoff
`/restore @thoughts/shared/handoffs/YYYY-MM-DD-file.md` — specific handoff

## Process

### Phase 0: Check Tasks First (Always)

```
TaskList    # See all tasks, check for in_progress
```

If tasks exist with status="in_progress" → fast path (skip to resume announcement).
If no active tasks → read handoff file for full context.

**Legacy fallback**: If native tasks unavailable, check beads:
```bash
bd sync
bd list --status in_progress --json
bd ready --json
```

### Phase 1: Context Restoration

1. Read handoff document completely
2. Parse: what's done, in progress, key decisions, blockers
3. Read referenced artifacts (plan file, TODO.md, active files)

### Phase 2: State Verification

4. Verify current state matches handoff (check commits exist, files in expected state)
5. Check if blockers were resolved

### Phase 3: Resume Announcement

```markdown
## Resuming: [Task Name]

**Handoff from**: YYYY-MM-DD

### Progress
| Status | Item |
|--------|------|
| Done | Item 1 |
| Done | Item 2 |
| **Resuming** | Item 3 |
| Pending | Item 4 |

### Decisions Restored
- [Key decision 1]

### Blockers: [Resolved/Still pending]

### Immediate Next Action
[What you're about to do]
```

### Phase 4: Continue

Start with first item in "Next Steps" from handoff.

## Finding Handoffs

```bash
ls -t thoughts/shared/handoffs/ | head -5  # Recent handoffs
```

If multiple exist, list them and ask which to resume (or use most recent).

## Scenarios

- **Blockers still pending**: Highlight them, ask user, continue with non-blocked items
- **State has changed**: Note differences, ask for guidance if conflicting
- **Multiple handoffs**: List with dates, ask which to resume
