---
name: doc
description: Build or refresh documentation and research packs through Argus. Use when user says '/doc', 'cache docs', 'download docs', 'save documentation', 'fetch docs', or asks to reference external documentation.
---

# /doc — Argus Documentation Workflows

Argus is now the canonical docs and research corpus owner. Do not treat `~/github/docs-cache` as the primary store anymore.

## What `/doc` should do

Use Argus on homelab to:
- recover dead articles
- capture the important parts of a site and produce a cited summary
- build a docs + research pack that combines official docs and external research

The canonical corpus lives on homelab under:
- `/mnt/main-drive/appdata/argus/docs/cache`
- `/mnt/main-drive/appdata/argus/docs/research`
- `/mnt/main-drive/appdata/argus/imports/docs-cache`

## Preferred Path

Call the Python client in `core/search/argus_client.py`, not ad hoc scraping first.

```bash
python - <<'PY'
from core.search import argus_client
import json
print(json.dumps(argus_client.build_research_pack("topic", official_url="https://docs.example.com"), indent=2))
PY
```

The client resolves:
- `config/search.yaml` for the Argus base URL
- `ARGUS_API_KEY` from env
- or `secrets get ARGUS_API_KEY argus` from the oneshot vault

## Usage Patterns

### 1. Docs + Research Pack

Use when the user wants:
- official docs plus external research in one place
- a reusable corpus for later tasks
- deeper tool/framework grounding

Run:

```bash
python - <<'PY'
from core.search import argus_client
import json
print(json.dumps(
    argus_client.build_research_pack(
        "example sdk",
        official_url="https://docs.example.com",
    ),
    indent=2,
))
PY
```

### 2. Site Capture Summary

Use when the user wants:
- “copy the important parts of this site”
- a detailed summary with references
- not just a sitemap

Run:

```bash
python - <<'PY'
from core.search import argus_client
import json
print(json.dumps(
    argus_client.capture_site("https://docs.example.com"),
    indent=2,
))
PY
```

### 3. Dead Article Recovery

Use when the user wants:
- a dead URL recovered
- a moved article found
- archive recovery with a final report

Run:

```bash
python - <<'PY'
from core.search import argus_client
import json
print(json.dumps(
    argus_client.recover_article(
        "https://example.com/dead-post",
        title="Example Post",
    ),
    indent=2,
))
PY
```

### 4. Poll Workflow Status

If the user wants the finished result immediately, poll:

```bash
python - <<'PY'
from core.search import argus_client
import json
print(json.dumps(argus_client.workflow_status("run_id_here"), indent=2))
PY
```

## Local Project Copies

Default behavior:
- keep the canonical corpus in Argus on homelab
- only copy selected outputs into the current project if the user explicitly wants project-local artifacts

Do not recreate the old `docs/external/<name>/README.md` pattern by default.

## If Local Cache Scripts Are Used

Legacy helpers such as `docs-link` and `docs-check.sh` should treat Argus paths as the default cache root.

Default local mirror path:
- `${DOCS_CACHE:-$HOME/.local/share/argus/argus/docs/cache}`

If that path is empty on the current machine, say so plainly and use Argus remotely instead of pretending the corpus is local.
