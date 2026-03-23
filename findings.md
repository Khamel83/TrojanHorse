# Research Findings: TrojanHorse → "The Bridge"

> Research gathered during continuous planning. Survives `/clear` and `/compact`.

---

## Codebase Analysis (Explore Agent)

### What to KEEP

| File | Path | Value |
|------|------|-------|
| Atlas Client | `TrojanHorse/atlas_client.py` | Already has batch ingestion, health check |
| LLM Client | `TrojanHorse/llm_client.py` | OpenRouter with retry logic, useful for AI tagging |
| Models | `TrojanHorse/models.py` | YAML frontmatter parsing for markdown |
| API Server | `TrojanHorse/api_server.py` | FastAPI foundation |

### What to REMOVE

| Category | Files | Size/Complexity |
|----------|-------|-----------------|
| Audio Capture | `src/audio_capture.py`, `src/transcribe.py` | Mac-specific, replaced by Hyprnote |
| Vault Processing | `classifier.py`, `router.py`, `processor.py` | Internal logic not needed for bridge |
| RAG/Search | `rag.py`, `search_engine.py`, `semantic_search.py` | Atlas handles search |
| Web UI | `web_interface.py`, `templates/`, `static/` | Not needed for background service |
| Meeting Synthesis | `meeting_synthesizer.py` | Out of scope |

---

## External Research (WebSearch)

### Watchdog File Watching Patterns

**Sources:**
- [Mastering File System Monitoring with Watchdog in Python](https://buymeacoffee.com/rbxhszc/mastering-file-system-monitoring-watchdog-python)
- [Stack Overflow: Stop watchdog reacting to partially transferred files](https://stackoverflow.com/questions/42168512/python-stop-watchdog-reacting-to-partially-transferred-files)

**Key Findings:**
- Use `Timer` for debouncing (reset on each event)
- Check `os.path.exists()` before processing (handles temp files like `.swp`)
- For partial writes: wait for file handle release or use silence period

**Implementation Pattern:**
```python
class DebouncedHandler(FileSystemEventHandler):
    def __init__(self, delay=30):
        self.delay = delay
        self.timers = {}

    def on_modified(self, event):
        if event.src_path in self.timers:
            self.timers[event.src_path].cancel()
        self.timers[event.src_path] = Timer(self.delay, self.process, [event.src_path])
        self.timers[event.src_path].start()
```

### OPML to Markdown Conversion

**Sources:**
- [shkarlsson/workflowy2markdown](https://github.com/shkarlsson/workflowy2markdown)
- [Convert an OPML outline to Markdown (Gist)](https://gist.github.com/alecperkins/5671192)
- [OPML to Markdown to create a blogroll page](https://bacardi55.io/2024/08/11/opml-to-markdown-to-create-a-blogroll-page/)

**Key Findings:**
- Use `xml.etree.ElementTree` for parsing
- OPML structure: `<opml><body><outline>` with nested `<outline>` elements
- Each outline has `text` attribute, may have `_note` for content
- Convert depth to indentation (2 spaces per level)

### API Retry & Rate Limiting

**Sources:**
- [How to Retry Failed Python HTTP Requests in 2026](https://iproyal.com/blog/python-requests-retry/)
- [Handling API Rate Limits in Python: A Modular Retry](https://medium.com/@balakrishna0106/handling-api-rate-limits-in-python-a-modular-retry-mechanism-5f4d68f41f52)
- [Stack Overflow: Retry mechanism in requests](https://stackoverflow.com/questions/23267409/how-to-implement-retry-mechanism-into-python-requests-library)

**Key Findings:**
- 3-5 retry attempts with exponential backoff
- Handle 429 with `Retry-After` header if present
- Use `tenacity` library for cleaner code than manual retry loops
- For rate limiting: `wait_exponential_multiplier=1000, wait_exponential_max=10000`

**Implementation Pattern:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=10))
def post_to_atlas(payload):
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response
```

---

## Atlas API Integration

### Existing Client (`atlas_client.py`)

**Current Implementation:**
```python
class AtlasClient:
    def __init__(self, atlas_url: str, api_key: Optional[str] = None, timeout: int = 60)
    def health_check(self) -> bool
    def ingest_notes(self, notes: List[Dict[str, Any]]) -> bool
```

**Endpoint Pattern:** `{atlas_url}/ingest/batch`

**Payload Format:** List of note dictionaries

### Questions for Atlas

1. **Exact endpoint:** `/api/notes/` vs `/ingest/batch` vs other?
2. **Single note endpoint:** Is there a single-note POST for better granularity?
3. **Authentication:** Header format (`X-API-Key` vs `Authorization: Bearer`)?
4. **Response on success:** What does 200 return?

---

## Deployment Target: oci-dev

**From `~/AGENTS.md`:**
- **Hostname:** oci-dev
- **Platform:** linux (Oracle Cloud free tier)
- **Memory:** 24GB RAM
- **No Docker:** Services run directly with systemd

**Implications:**
- Must work without Mac-specific audio libraries
- Systemd service for auto-restart
- Python 3.x (confirm version)

---

## Dependencies Summary

**To Keep:**
```
typer>=0.9.0           # CLI framework
pyyaml>=6.0            # YAML parsing
requests>=2.31.0       # HTTP client
fastapi>=0.115.0       # Web framework (optional, for future)
uvicorn[standard]>=0.30.0  # ASGI server (optional)
```

**To Add:**
```
watchdog>=4.0.0        # File watching
python-dotenv>=1.0.0   # Config management
tenacity>=8.0.0        # Retry logic
```

**To Remove:**
```
numpy>=1.24.0          # Not needed for bridge
```

---

## Research Gaps

| Area | Status | Notes |
|------|--------|-------|
| Watchdog debouncing | ✅ Complete | Have implementation pattern |
| OPML parsing | ✅ Complete | Have conversion pattern |
| Retry logic | ✅ Complete | Tenacity pattern identified |
| Atlas API spec | ⚠️ Partial | Need to confirm endpoint/auth |
| systemd deployment | ✅ Complete | Have template from docs |

---

**Last Updated:** 2026-02-02
**Sources:** WebSearch + Explore Agent + Existing codebase analysis
