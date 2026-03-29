# Claude Code Skills Reference

## Quick Reference

### Correct Location
```
~/.claude/skills/<skill-name>/SKILL.md
```

### Required Format
```yaml
---
name: skill-name
description: What it does and WHEN Claude should use it. Include trigger keywords.
---

# Skill Title

Instructions here...
```

### Key Points

1. **`name:` field is REQUIRED** — Without it, skill won't be discovered
2. **`description:` must include triggers** — Claude uses this to decide when to invoke
3. **Directory name should match skill name** — For clarity
4. **Skills are model-invoked** — Claude decides when to use them automatically

## Common Issues

### Skills not appearing

**Symptom**: `/help` doesn't show your skills, or `/skill-name` returns "Unknown skill"

**Causes**:
1. Missing `name:` field in frontmatter
2. Invalid YAML syntax (tabs instead of spaces)
3. Wrong location (should be `~/.claude/skills/<name>/SKILL.md`)
4. File named incorrectly (must be `SKILL.md`, not `skill.md` or `<name>.md`)

### How to verify

```bash
# Check skill exists
ls ~/.claude/skills/<name>/SKILL.md

# Verify frontmatter
head -5 ~/.claude/skills/<name>/SKILL.md
```

### Frontmatter validation

Valid:
```yaml
---
name: my-skill
description: Does X when user says Y or Z.
---
```

Invalid (missing name):
```yaml
---
description: Does X when user says Y or Z.
---
```

Invalid (tabs in YAML):
```yaml
---
	name: my-skill    # TABS NOT ALLOWED
description: ...
---
```

## Migration from Commands

If you have files in `~/.claude/commands/` that aren't working:

```bash
# Convert each command to a skill
for cmd in command1 command2; do
  mkdir -p ~/.claude/skills/$cmd
  cp ~/.claude/commands/$cmd.md ~/.claude/skills/$cmd/SKILL.md

  # Add name field if missing
  sed -i "1,2s|---|---\nname: $cmd|" ~/.claude/skills/$cmd/SKILL.md
done

# Backup and remove old commands
mkdir -p ~/.claude/commands-backup
mv ~/.claude/commands/*.md ~/.claude/commands-backup/
```

## Sources

- Official docs: https://docs.anthropic.com/en/docs/claude-code/skills
