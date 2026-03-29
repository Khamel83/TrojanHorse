---
name: doc
description: Cache external documentation locally. Use when user says '/doc', 'cache docs', 'download docs', 'save documentation', 'fetch docs', or asks to reference external documentation.
---

# /doc — Local Documentation Caching

Cache **any external documentation** locally for your project:
- Libraries (npm packages, Python packages)
- Frameworks (Next.js, Convex, FastAPI)
- Services (Tailscale, OCI, Docker)
- CLIs and tools
- Anything with online docs

## Why Cache Docs Locally?

1. **Validate against actual docs** — not stale training data
2. **Avoid repeated web fetches** during development
3. **Version docs with your project** — docs travel with code
4. **Reference with `@filename`** — simple markdown inclusion

**No MCP required** — just fetch once, save to markdown, reference with `@`.

---

## Usage

```bash
# Cache documentation
/doc convex https://docs.convex.dev
/doc nextjs https://nextjs.org/docs
/doc tailscale https://tailscale.com/kb/api
/doc poetry https://python-poetry.org/docs

# List cached docs
/doc --list

# Show path to docs
/doc --show convex
```

---

## Directory Structure

Docs are saved to `$PROJECT/docs/external/`:

```
$PROJECT/docs/external/
├── convex/
│   └── README.md           # Full documentation
├── nextjs/
│   └── README.md
├── tailscale/
│   └── README.md
├── poetry/
│   └── README.md
└── .index.md               # List of all cached docs with source URLs
```

---

## How It Works

1. Uses **Jina.ai reader** (`https://r.jina.ai/<url>`) to fetch docs as markdown
2. Saves to `$PROJECT/docs/external/<name>/README.md`
3. Updates `$PROJECT/docs/external/.index.md` with all cached docs
4. Reference later with `@docs/external/<name>/README.md`

---

## Session Start: Check Local Docs First

Before using WebSearch for docs:

```bash
# Check what's cached locally
ls docs/external/

# Read the index
cat docs/external/.index.md

# Reference a doc
@docs/external/convex/README.md
```

If no local docs exist:
1. Suggest running `/doc <name> <url>` to cache them
2. Auto-detect: When you see external imports/dependencies, prompt to cache docs

---

## Examples

### Cache Convex Docs
```bash
/doc convex https://docs.convex.dev
```

### Cache Next.js Docs
```bash
/doc nextjs https://nextjs.org/docs
```

### Cache Poetry Docs
```bash
/doc poetry https://python-poetry.org/docs
```

---

## Integration with docs-first.md

The `docs-first.md` rule now checks `$PROJECT/docs/external/` before using WebSearch:

1. **Check local docs first** — `ls docs/external/`
2. **Use WebSearch only if** — no local docs exist
3. **Suggest caching** — `/doc <name> <url>` if docs would be useful

---

## Verification

After caching docs:

```bash
# Verify file was created
ls -la docs/external/convex/

# Check index was updated
cat docs/external/.index.md

# Reference in conversation
@docs/external/convex/README.md
```

---

## Keywords

documentation, docs, cache, fetch, download, reference, external, api docs, library docs
