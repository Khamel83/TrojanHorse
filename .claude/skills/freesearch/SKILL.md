---
name: freesearch
description: Zero-token research using Exa API directly via curl. Saves Claude tokens.
---

# /freesearch — Zero-Token Research via Exa API

Uses 0 Claude Code tokens. Calls Exa API directly via curl.

## Usage

`/freesearch [topic]`

## Process (IMPORTANT: Follow this order)

1. **Check global docs-cache FIRST**:
   ```bash
   cat ~/github/docs-cache/docs/cache/.index.md | grep -i "[KEYWORD]"
   ls ~/github/docs-cache/docs/cache/*/
   ```
   If found → Return cached doc path immediately

2. If NOT in cache → Ask 2-3 clarifying questions (goal, depth, audience)

3. Search Exa API via curl:

```bash
# Decrypt Exa key (uses --config so it works from ANY directory)
EXA_KEY=$(sops --config ~/github/oneshot/secrets/.sops.yaml --decrypt --output-type json ~/github/oneshot/secrets/research_keys.json.encrypted | jq -r '.EXA_API_KEY')

# Search
curl -s -X POST 'https://api.exa.ai/search' \
  -H "x-api-key: $EXA_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "[TOPIC]",
    "type": "auto",
    "numResults": 10,
    "contents": { "text": { "maxCharacters": 20000 } }
  }'
```

4. **If Exa finds official docs** → Add to global cache:
   ```bash
   cd ~/github/docs-cache
   mkdir -p docs/cache/{category}/{name}
   # Write README.md
   # Update .index.md with: Name | Category | Related | URL | YYYY-MM-DD
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
[Searched Exa] Key findings:
- [finding 1]
- [finding 2]

[Added to cache] ~/github/docs-cache/docs/cache/tools/{name}/README.md
Full research: docs/research/YYYY-MM-DD_{topic}_final.md
```

## Notes

- Research takes 10-30 seconds
- Check cache BEFORE searching - this is the whole point
- Only add official docs to cache (not random blog posts)
- Cache location: `~/github/docs-cache/` (global, not per-project)
