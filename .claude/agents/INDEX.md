# ONE_SHOT Agents

Custom agents for the ONE_SHOT framework. Each agent is a Claude Code agent
definition file (frontmatter + instructions).

## Creating an Agent

1. Copy `TEMPLATE.md` to a new `.md` file
2. Fill in the frontmatter fields
3. Write the agent instructions
4. Validate with `./scripts/validate-agents.py`

## Directory

```
.claude/agents/
  INDEX.md        — This file
  TEMPLATE.md     — Agent template
  *.md            — Agent definitions
```
