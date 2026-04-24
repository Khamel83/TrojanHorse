---
name: research
description: Run deep research in a background sub-agent using Argus search broker. Falls back to Gemini CLI if Argus is unavailable.
---

# /research — Background Research via Argus

Run deep research in a background sub-agent. Argus handles search provider selection and fallback.

## Usage

`/research [topic]`

## Process

1. Ask 2-3 clarifying questions (goal, depth, audience)
2. **Check Argus availability**:
   ```bash
   python -c "from core.search.argus_client import is_available; print(is_available())" 2>/dev/null
   ```
   Or simply:
   ```bash
   curl -s http://100.126.13.70:8005/api/health >/dev/null 2>&1 && echo "argus: yes" || echo "argus: no"
   ```

3. **Mode 1: Argus (Primary)**
   Spawn background sub-agent:
   ```
   Task:
     subagent_type: general-purpose
     description: "Argus research: [topic]"
     run_in_background: true
     prompt: |
       Use Argus to research: [topic]
       
       1. Query Argus in research mode:
          curl -s -X POST http://100.126.13.70:8005/api/search \
            -d '{"query": "[research query]", "mode": "research"}'
       
       2. For key results, extract full content:
          curl -s -X POST http://100.126.13.70:8005/api/extract \
            -d '{"url": "RESULT_URL"}'
       
       3. Write findings to: docs/research/[slug]/research.md
       4. Structure: Executive Summary → Detailed Findings → Sources
   ```

4. **Mode 2: Gemini CLI (Fallback)**
   If Argus is unavailable:
   ```
   Task:
     subagent_type: general-purpose
     description: "Gemini research: [topic]"
     run_in_background: true
     prompt: |
       Run Gemini CLI for research:
       gemini --yolo "[research prompt]"
       
       Save output to: docs/research/[slug]/research.md
   ```

5. Present findings when agent completes
6. Save to `docs/research/[slug]/research.md`

## Search Config

Argus modes (from `config/search.yaml`):
- `discovery`: broad, multiple sources
- `precision`: targeted, high relevance
- `research`: comprehensive, all providers
- `cheap`: SearXNG only, cost-sensitive

## Notes

- Research takes 3-8 minutes in background
- Check `docs/research/` for past research
- Argus automatically handles provider fallback, ranking, and dedup
