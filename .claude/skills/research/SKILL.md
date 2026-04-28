---
name: research
description: Run deep research via Argus search broker, dispatched to background workers. Not a Claude-inline task.
---

# /research — Background Research via Argus

Research is dispatched to workers. Claude coordinates, not executes.

## CRITICAL: Dispatch Is Mandatory

Research queries MUST go through Argus or Gemini CLI as a subprocess.
Claude does NOT do web research inline. Build the query, dispatch, integrate results.

## Usage

`/research [topic]`

## Process

1. Ask 1-2 clarifying questions (goal, depth)
2. **Check Argus availability**:
   ```bash
   python -c "from core.search.argus_client import is_available; print(is_available())" 2>/dev/null
   ```
3. **Dispatch research to worker** (MANDATORY):
   - If Argus available, dispatch via the research lane:
     ```bash
     python3 -m core.dispatch.run \
       --class doc_draft \
       --category research \
       --prompt "Research: [topic]. Query Argus in research mode via HTTP API, extract key results, write findings to docs/research/[slug]/research.md. Structure: Executive Summary → Findings → Sources." \
       --output 1shot/dispatch \
       --manifest 1shot/dispatch
     ```
   - If Argus unavailable, dispatch to Gemini CLI:
     ```bash
     python3 -m core.dispatch.run \
       --class doc_draft \
       --category research \
       --prompt "Research: [topic]. Write findings to docs/research/[slug]/research.md." \
       --worker gemini_cli \
       --output 1shot/dispatch
     ```
4. Review worker output when dispatch completes
5. Integrate findings, present summary

## Search Modes (from config/search.yaml)

- `discovery`: broad, multiple sources
- `precision`: targeted, high relevance
- `research`: comprehensive, all providers
- `cheap`: SearXNG only

## Notes

- Research takes 3-8 minutes in background
- Check `docs/research/` for past research
- Argus automatically handles provider fallback, ranking, and dedup
