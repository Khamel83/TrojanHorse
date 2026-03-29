---
name: freesearch
description: Zero-token research using Exa API directly via curl. Saves Claude tokens.
---

# /freesearch — Zero-Token Research via Exa API

Uses 0 Claude Code tokens. Calls Exa API directly via curl.

## Usage

`/freesearch [topic]`

## Process

1. Ask 2-3 clarifying questions (goal, depth, audience)
2. Create `docs/research/{date}_{topic}_in_progress.md`
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

4. Write results to in-progress file
5. Create `docs/research/{date}_{topic}_final.md` with:
   - Executive summary
   - Key findings
   - Sources with links
   - Related topics
6. Return summary + file path

## Output

```
Key findings:
- [finding 1]
- [finding 2]

Full research: docs/research/YYYY-MM-DD_{topic}_final.md
```

## Notes

- Research takes 10-30 seconds
- Save to project `docs/research/` (not ~/github/oneshot/research/)
- Include user's goal in the search query for better results
