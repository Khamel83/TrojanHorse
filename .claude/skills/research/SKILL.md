---
name: research
description: Run deep research in a background sub-agent using Gemini CLI or free search APIs.
---

# /research — Background Research via Gemini CLI or Search APIs

Run deep research in a background sub-agent. Saves Claude tokens by using Gemini CLI or free search APIs.

## Usage

`/research [topic]`

## Process

1. Ask 2-3 clarifying questions (goal, depth, audience)
2. Check if `gemini` CLI is available → Mode 1 (Gemini), else → Mode 2 (APIs)
3. Spawn background sub-agent

### Mode 1: Gemini CLI (Primary)

```
Task:
  subagent_type: general-purpose
  description: "Gemini research: [topic]"
  run_in_background: true
  prompt: |
    Run Gemini CLI for deep research:
    gemini --yolo "[comprehensive research prompt covering:
    overview, current state, technical details, practical applications,
    challenges, future outlook, resources]"

    Save output to: docs/research/[slug]/research.md
    Structure as: Executive Summary → sections → Resources
```

### Mode 2: Free Search APIs (Fallback)

Try APIs in this order: Perplexity → Tavily → Brave → Bing

```bash
# Decrypt keys
OUTPUT=$(sops -d --output-type dotenv ~/github/oneshot/secrets/research_keys.env.encrypted 2>/dev/null)

# Perplexity (AI answers + citations)
PERPLEXITY_KEY=$(echo "$OUTPUT" | grep -oP 'PERPLEXITY_API_KEY=\K[^\\]+')
curl -s -X POST "https://api.perplexity.ai/chat/completions" \
  -H "Authorization: Bearer $PERPLEXITY_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"sonar","messages":[{"role":"user","content":"QUERY"}],"max_tokens":500}'

# Tavily (AI answers + sources)
TAVILY_KEY=$(echo "$OUTPUT" | grep -oP 'TAVILY_API_KEY=\K[^\\]+')
curl -s https://api.tavily.com/search -H "Content-Type: application/json" \
  -d '{"api_key":"KEY","query":"QUERY","search_depth":"advanced","include_answer":true}'
```

3. Present findings when agent completes
4. Save to `docs/research/[slug]/research.md`

## If using /cp (continuous planner)

Write findings to `findings.md` in the plan directory so they persist across sessions.

## Notes

- Research takes 3-8 minutes in background
- Check `docs/research/` for past research
- Keys stored in `~/github/oneshot/secrets/research_keys.env.encrypted`
