<!-- ONE_SHOT v6.0 -->
# IMPORTANT: Read AGENTS.md - it contains skill and agent routing rules.
#
# Skills (synchronous, shared context):
#   "build me..."     → front-door
#   "plan..."         → create-plan
#   "implement..."    → implement-plan
#   "debug/fix..."    → debugger
#   "deploy..."       → push-to-cloud
#   "ultrathink..."   → thinking-modes
#   "beads/ready..."  → beads (persistent tasks)
#
# Agents (isolated context, background):
#   "security audit..." → security-auditor
#   "explore/find all..." → deep-research
#   "background/parallel..." → background-worker
#   "coordinate agents..." → multi-agent-coordinator
#
# Always update TODO.md as you work.
<!-- /ONE_SHOT -->

# Project Instructions

## Overview
[Brief description of what this project does]

## Key Commands
```bash
# Setup
[setup commands]

# Run
[run commands]

# Test
[test commands]
```

## Architecture
[Key architectural decisions and patterns]

## Conventions
[Project-specific conventions and standards]

## Skill & Agent Usage
When working on this project:
- Planning: `create-plan` → `implement-plan`
- Debugging: `debugger` → `test-runner`
- Deploying: `push-to-cloud` → `ci-cd-setup`
- Context: `create-handoff` before `/clear`
- Security: `security-auditor` (isolated)
- Research: `deep-research` (isolated)
