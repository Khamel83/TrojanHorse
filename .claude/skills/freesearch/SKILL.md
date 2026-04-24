---
name: freesearch
description: Zero-token research using Argus search broker. Saves Claude tokens.
---

# /freesearch — Zero-Token Research via Argus

Uses 0 Claude Code tokens. Calls Argus in cheap mode (SearXNG).

## Usage

`/freesearch [topic]`

## Process (IMPORTANT: Follow this order)

1. **Check global docs-cache FIRST**:
   ```bash
   cat ~/github/docs-cache/docs/cache/.index.md | grep -i "[KEYWORD]"
   ```
   If found → Return cached doc path immediately

2. If NOT in cache → Ask 2-3 clarifying questions (goal, depth, audience)

3. **Search via Argus** (cheap mode = SearXNG only):
   ```bash
   curl -s -X POST http://100.126.13.70:8005/api/search \
     -H "Content-Type: application/json" \
     -d '{"query": "[TOPIC]", "mode": "cheap"}'
   ```

4. **If results include official docs** → Add to global cache:
   ```bash
   cd ~/github/docs-cache
   mkdir -p docs/cache/{category}/{name}
   # Write README.md with content
   # Update .index.md
   git add docs/cache/
   git commit -m "Add cache: {name}"
   git push
   ```

5. Create `docs/research/{date}_{topic}_final.md` in current project

## Output

```
[CACHED] Found in docs-cache: ~/github/docs-cache/docs/cache/tools/anthropic/README.md
```

OR

```
[Searched Argus: cheap mode] Key findings:
- [finding 1]
- [finding 2]

[Added to cache] ~/github/docs-cache/docs/cache/tools/{name}/README.md
Full research: docs/research/YYYY-MM-DD_{topic}_final.md
```

## Fallback

If Argus is unreachable:
```bash
curl -s http://100.126.13.70:8005/api/health >/dev/null 2>&1
```
...then check `config/search.yaml` for cheap mode providers and call directly.

## Notes

- Research takes 5-15 seconds
- Check cache BEFORE searching
- Only add official docs to cache (not random blog posts)
- Cache location: `~/github/docs-cache/` (global, not per-project)
