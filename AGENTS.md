<!-- FOR CLAUDE - NOT FOR HUMANS -->
<!-- Humans: See README.md for user guide, INDEX.md for skill reference -->

# ONE_SHOT v9

> **v9 = PLAY CALLING** - Explicit skill sequences in task_plan.md, automatic skill discovery, SkillsMP marketplace integration, deterministic execution via /run-plan.

> **Context is the scarce resource.** Delegate aggressively, parallelize always, write state to disk.

---

## SKILL ROUTER (18 Core Skills)

```yaml
skill_router:
  # Entry
  - pattern: "new project|build me|help me|/interview|/front-door"
    skill: front-door
    slash: "/front-door or /interview"

  # Interview Depth Overrides (v8.1 - with slash commands)
  - pattern: "/full-interview|full interview mode"
    skill: full-interview
    note: "Forces all 13+ questions, no bypass"
    slash: "/full-interview"

  - pattern: "/quick-interview|quick interview mode"
    skill: quick-interview
    note: "Only Q1, Q2, Q6, Q12 with smart defaults"
    slash: "/quick-interview"

  - pattern: "/smart-interview|reset interview"
    skill: smart-interview
    note: "Reset to auto-detect depth (default)"
    slash: "/smart-interview"

  # Autonomous (headless mode)
  - pattern: "autonomous|headless|background|overnight|just build it"
    skill: autonomous-builder

  # Planning
  - pattern: "plan|design|how should|what's the approach"
    skill: create-plan

  - pattern: "continuous plan|living plan|3-file plan|plan with files|multi-model coordination"
    skill: continuous-planner
    note: "3-file pattern (task_plan.md, findings.md, progress.md) - survives /clear, multi-model coordination"

  - pattern: "implement|execute|build it|run the plan"
    skill: implement-plan

  # Task Tracking (persistent)
  - pattern: "beads|ready tasks|what's next|next task|blockers|dependencies"
    skill: beads

  # Quality
  - pattern: "bug|error|fix|debug|broken|not working"
    skill: debugger

  - pattern: "review|check code|is this safe|pr review"
    skill: code-reviewer

  # Lessons Learned (NEW)
  - pattern: "oops|save this mistake|remember this|lessons learned|/lessons"
    skill: oops

  # Parallel Execution (NEW in v7.4)
  - pattern: "validate|check everything|run all checks|pre-commit"
    skill: parallel-validator

  - pattern: "rename across|update all|batch|bulk|mass update"
    skill: batch-processor

  # Context Management
  - pattern: "handoff|save context|before clear|context low"
    skill: create-handoff

  - pattern: "resume|continue|pick up|from handoff"
    skill: resume-handoff

  # Recovery & Thinking
  - pattern: "stuck|looping|confused|start over"
    skill: failure-recovery

  - pattern: "think|ultrathink|super think|mega think"
    skill: thinking-modes

  # Secrets
  - pattern: "secrets|env|credentials|api key"
    skill: secrets-vault-manager

  # Research (v8.1 - enhanced)
  - pattern: "research|investigate|look into|find out about|deep dive|what do you know about"
    skill: deep-research
    note: "Background Gemini CLI + Perplexity/Context7/Tavily APIs, saves Claude tokens"
    slash: "/deep-research"

  # Search Fallback (v8.1)
  - pattern: "web search failed|search not working|429|rate limit|search fallback|use search api"
    skill: search-fallback
    note: "Auto-fallback to Perplexity/Context7/Tavily/Brave/Bing APIs when WebSearch fails"
    slash: "/search-fallback"

  # Free Research (v8.1)
  - pattern: "freesearch|free research|/freesearch"
    skill: freesearch
    note: "Direct Gemini CLI via Bash, 0 Claude tokens"
    slash: "/freesearch"

  # Multi-Model Dispatch (v8.1)
  - pattern: "dispatch|route to|use codex|use gemini|multi-model|/dispatch"
    skill: dispatch
    note: "Route to local CLIs (claude/codex/gemini/qwen), minimize Claude tokens"
    slash: "/dispatch"

  # Skills Discovery
  - pattern: "browse skills|skillsmp|find skills|skill marketplace"
    skill: skillsmp-browser

  # Maintenance
  - pattern: "/update|update oneshot|upgrade oneshot|check version"
    skill: auto-updater
```

**All other skills**: Available on-demand via `/skill-name` or explicit request. See INDEX.md.

---

## SLASH COMMANDS (v8.3)

All skills can be invoked via `/skill-name`. Core slash commands:

| Command | Purpose |
|---------|---------|
| `/front-door` or `/interview` | Force interview mode |
| `/full-interview` | Full depth (all 13+ questions) |
| `/quick-interview` | Quick mode (Q1, Q2, Q6, Q12 only) |
| `/smart-interview` | Reset to auto-detect depth |
| `/continuous-planner` | Create living 3-file plan (survives /clear) |
| `/deep-research` | Background research via Gemini CLI or APIs |
| `/freesearch` | TRULY FREE research via Gemini CLI (0 tokens) |
| `/dispatch` | Route tasks to local AI CLIs (codex/gemini/qwen/zai) |
| `/search-fallback` | Fallback search APIs when WebSearch fails |
| `/update` | Update ONE_SHOT from GitHub |
| `/beads` or `/bd` | Task tracking commands |
| `/oops` | Save lessons learned |
| `/lessons` | View lessons learned |

**Any skill** can be invoked as `/skill-name` - e.g., `/debugger`, `/code-reviewer`, `/create-plan`

---

## AUTO-DELEGATION (v7.4)

**CRITICAL**: These fire AUTOMATICALLY without user request.

```yaml
auto_delegation:
  # File count triggers (>5 files → delegate)
  - signal: "Glob/Grep returning >5 files"
    action: "Spawn Explore agent, return summary only"

  # Duration triggers (>15s → background)
  - signal: "npm|pytest|docker|build command"
    action: "run_in_background: true"

  # Security triggers (auto-audit)
  - signal: "Editing auth/secrets/credentials files"
    action: "Spawn security-auditor in background"

  # Search failure triggers (auto-fallback)
  - signal: "WebSearch returns 429/rate limit/error"
    action: "Invoke search-fallback skill automatically"

  - signal: "Monthly usage limit exceeded|zai search limit|MCP usage limit|GLM search quota|quota exceeded"
    action: "Invoke search-fallback skill automatically"

  - signal: "WebSearch failed|search not working|SearchAPI error"
    action: "Invoke search-fallback skill automatically"

  # Context triggers (pre-emptive)
  - signal: "Context >30% + complex task"
    action: "Delegate exploration to subagent"
  - signal: "Context >50%"
    action: "Create handoff, delegate remaining"
```

**Key change from v7.3:** Bias toward delegation. Don't wait for user to say "background".

---

## RESILIENT EXECUTION (v7.4)

**All long-running work runs in tmux** - survives terminal disconnect.

```yaml
resilience:
  # Default: All builds use tmux
  - command: "oneshot-build"
    mode: tmux_session
    heartbeat: 30s
    checkpoint: 5m

  # Aggressive state sync
  - trigger: "task status change"
    action: "bd sync immediately"
  - trigger: "file committed"
    action: "bd sync"
  - trigger: "every 5 minutes"
    action: "checkpoint commit + bd sync"

  # Recovery
  - on_disconnect: "work continues in tmux"
  - on_reconnect: "tmux attach -t oneshot-*"
  - on_crash: "bd sync && bd ready to resume"
```

**Key principle:** If terminal dies, work continues. If work dies, state is recoverable.

---

## CONTEXT MANAGEMENT

### Task Groups (3-5 tasks each)
```
Plan has N tasks → Create beads tasks with dependencies
Execute one group → bd update status → Check context
If context > 50% → Pause, bd sync, suggest /compact
After /compact → bd ready shows exactly what's next
```

### Beads = Persistent State
All task progress tracked via beads (survives /clear, /compact, sessions):
```bash
bd ready --json     # What's next?
bd update <id> --status in_progress
bd close <id> --reason "commit: abc123"
bd sync             # Always sync before session end
```

### Pre-Implementation Flow
```
If context > 30% before implement-plan:
  → bd sync (save current state)
  → Suggest /compact first
```

---

## FILE HIERARCHY

| Priority | File | Purpose |
|----------|------|---------|
| 1 | CLAUDE.md | Project-specific rules |
| 2 | AGENTS.md | This file (skill routing) |
| 3 | `.beads/` | Persistent task state (bd ready) |
| 4 | TODO.md | Session visibility |

---

## THINKING MODES

| Trigger | Depth |
|---------|-------|
| "think" | Quick check |
| "think hard" | Trade-offs |
| "ultrathink" | Architecture |
| "super think" | System design |
| "mega think" | Strategic |

---

## PHILOSOPHY

> "It's harder to read code than to write it." — Joel Spolsky

**NEVER rewrite from scratch.** Extend, refactor, use existing solutions.

**USER TIME IS PRECIOUS. AGENT COMPUTE IS CHEAP.**
Ask ALL questions UPFRONT. Get ALL info BEFORE coding.

---

## RESET

Say `(ONE_SHOT)` to re-anchor to these rules.

---

## DOCUMENTATION MAINTENANCE (For LLMs)

### When to Update Documentation

| File | Update Trigger |
|------|----------------|
| `README.md` | New user-facing features, version bumps, workflow changes |
| `AGENTS.md` | New skills added to router, orchestration changes |
| `INDEX.md` | Skills added/removed/renamed |

### README.md Update Rules

README.md is the PRIMARY user documentation. Keep it:
1. **User-focused** - Write for humans, not LLMs
2. **Clear** - Simple language, examples that work
3. **Minimal** - Remove what doesn't help users succeed
4. **Single source** - Don't duplicate content elsewhere

**When updating README.md:**
- Add to "For LLMs: Documentation Maintenance" section
- Follow existing structure (Quick Start → How to Use → Advanced → For LLMs)
- Test examples before committing
- Update version bump checklist

### AGENTS.md Update Rules

AGENTS.md is for LLMs only. Keep it:
1. **Precise** - Every word matters for routing
2. **Minimal** - Compress context, remove redundancy
3. **Technical** - LLMs parse this, not humans
4. **Current** - Version must match actual release

**When updating AGENTS.md:**
- Update version header when releasing
- Add skills to router if they're core (used frequently)
- Keep patterns grep-friendly
- Test routing after changes

### Related Files Matrix

| File | Audience | Changes Require |
|------|----------|-----------------|
| README.md | Users + LLMs | User-facing feature changes |
| AGENTS.md | LLMs only | Skill router changes |
| CLAUDE.md | LLMs only | Project-specific rules |
| INDEX.md | Users + LLMs | Skills catalog changes |

### Documentation Sync

When updating user-facing features:
1. Update README.md first (user perspective)
2. Update AGENTS.md if router changes needed (LLM perspective)
3. Test both work together
4. Commit together or in quick succession

---

**Version**: 8.3 | **System Tokens**: ~2k (down from 20k) | **Core Skills**: 18 | **Total Skills**: 51 | **Slash Commands**: Yes | **Context**: Ultra-compressed JSON | **New**: Continuous Planning (3-file pattern)
