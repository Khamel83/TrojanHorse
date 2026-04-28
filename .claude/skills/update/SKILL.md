---
name: update
description: Pull latest oneshot from GitHub and sync skills/agents to the current project, or all projects with --all.
---

# /update — Sync OneShot to Current Project

Pull the latest oneshot and propagate skills, agents, and AGENTS.md to the current project.

## Usage

```
/update           # pull + sync current project only
/update --all     # pull + sync all projects
/update --dry-run # preview what would change without touching anything (--all only)
/update --self    # pull oneshot only, skip project sync
```

## Steps

1. **Pull latest oneshot**
   ```bash
   cd ~/github/oneshot && git pull --rebase
   ```
   If this fails (local changes), stash first:
   ```bash
   git stash && git pull --rebase && git stash pop
   ```

2. **Sync**

   **Default (current project only)**:
   ```bash
   bash ~/github/oneshot/scripts/oneshot-update.sh sync $(pwd)
   ```
   Then commit and push the result:
   ```bash
   git add .claude/ AGENTS.md 2>/dev/null || true
   git diff --cached --quiet || git commit -m "chore: sync oneshot framework (skills, agents, AGENTS.md)"
   git push
   ```
   If push fails (remote ahead), fix with:
   ```bash
   git stash && git pull --rebase && git push && git stash pop
   ```

   **`--all` (every project under ~/github/)**:
   ```bash
   bash ~/github/oneshot/scripts/sync-all-projects.sh
   ```
   With `--dry-run`:
   ```bash
   bash ~/github/oneshot/scripts/sync-all-projects.sh --dry-run
   ```

3. **Fix any push failures** (--all mode)
   For each failed project, the likely cause is remote ahead of local. Fix with:
   ```bash
   cd ~/github/<project>
   git stash
   git pull --rebase
   git push
   git stash pop
   ```
   Do this for every project listed in `FAILED:` — don't leave them behind.

4. **Report results**
   ```
   OneShot update complete
   ├─ oneshot: <old-sha> → <new-sha>  (or "already up to date")
   ├─ synced: N projects
   ├─ skipped: N (no .claude/ dir or oneshot itself)
   ├─ failed: N
   └─ fixed: [list of projects that needed manual push]
   ```

## What Gets Synced

| What | Where | Notes |
|------|-------|-------|
| Skills | `.claude/skills/` | `--delete` removes obsolete skills |
| Agents | `.claude/agents/` | Only if project already has the dir |
| AGENTS.md | `AGENTS.md` | Only if file exists in the project |

Project-local files (`CLAUDE.md`, `CLAUDE.local.md`, `config/`, `1shot/`) are never touched.

## Notes

- The auto-updater pulls oneshot once per day on session start — `/update` is for forcing it now
- `sync-all-projects.sh` auto-discovers every repo under `~/github/` with a `.claude/` dir
- Each synced project gets a `chore: sync oneshot framework` commit and is pushed
- Run from any directory — scripts use absolute paths
