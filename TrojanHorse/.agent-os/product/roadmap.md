# Product Roadmap

## Phase 1: MVP Complete (v0.1.0)

**Goal:** Establish core functionality for audio capture, transcription, and organization.
**Success Criteria:** System can reliably capture and transcribe audio, organizing it into daily folders.

### Features

- [x] Continuous audio capture `[M]`
- [x] Multi-engine transcription `[L]`
- [x] Health monitoring `[M]`
- [x] macOS service integration `[S]`
- [x] Daily folder organization `[S]`

### Dependencies

- FFmpeg
- faster-whisper (optional)
- BlackHole

## Phase 2: Local-First Intelligence (v0.2.0)

**Goal:** Enhance the system with local and cloud-based AI for analysis and insights.
**Success Criteria:** System can perform local and cloud-based analysis, with a focus on privacy and cost optimization.

### Features

- [x] Local LLM Analysis `[L]` (analyze_local.py implemented)
- [x] Cloud Intelligence `[M]` (cloud_analyze.py + process_gemini.py implemented)
- [x] Privacy Architecture `[M]` (PII detection in analyze_local.py)
- [ ] ~~Content Classification~~ `[L]` (merged into unified analysis router)
- [x] Cost Optimization `[S]` (cost tracking in process_gemini.py)

**Status:** Architecture needs unification - complex implementations exist but need simplification

### Dependencies

- Ollama ✅
- OpenRouter ✅

## Phase 3: Search & Memory (v0.3.0)

**Goal:** Implement robust search and memory capabilities.
**Success Criteria:** Users can perform instant and semantic searches on their transcribed data.

### Features

- [ ] Search & Memory `[L]` (SQLite + FTS5 implementation)
- [ ] Semantic Search `[XL]` (sentence-transformers + vector embeddings)
- [ ] Timeline Analysis `[L]` (web interface with date filtering)
- [ ] Export System `[M]` (merged into web interface)

**Status:** Ready for implementation via system-completion spec

### Dependencies

- SQLite + FTS5 (built-in)
- sentence-transformers
- Flask

## Phase 4: Future (v1.0.0)

**Goal:** Expand the system's capabilities for workflow integration and advanced analytics.
**Success Criteria:** System can integrate with external tools and provide cross-day pattern recognition.

### Features

- [ ] Workflow Integration `[XL]`
- [ ] Advanced Analytics `[XL]`
- [ ] Multi-device Sync `[L]`
- [ ] API Ecosystem `[L]`
