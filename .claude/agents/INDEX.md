# Agents Index

ONE_SHOT v12.2 uses native Tasks + intelligent delegation. See `.claude/skills/INDEX.md` for available skills.

---

## Migration Notes

v9 used a directory-based agent system. v10+ simplified to:
- **Native Tasks** - TaskCreate, TaskGet, TaskUpdate, TaskList (primary)
- **Slash commands** - Invoke via `/skill-name`
- **Intelligent Delegation** - Assess, verify, trace with Agent Lightning spans
- **Routing** - Defined in `AGENTS.md`

No standalone agent files are needed in v10+.
