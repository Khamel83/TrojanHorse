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

- [x] Local LLM Analysis `[L]` - analyze_local.py with Ollama + qwen3:8b
- [x] Cloud Intelligence `[M]` - cloud_analyze.py + process_gemini.py with OpenRouter
- [x] Privacy Architecture `[M]` - PII detection and local-first processing
- [x] Content Classification `[L]` - merged into unified analysis router
- [x] Cost Optimization `[S]` - cost tracking and daily limits
- [x] Analysis Router `[M]` - analysis_router.py unified interface

**Status:** ✅ MOSTLY COMPLETE - Core analysis capabilities implemented. Architecture unification completed via analysis_router.py. System ready for production testing.

### Dependencies

- Ollama ✅
- OpenRouter ✅

## Phase 3: Search & Memory Complete (v0.3.0)

**Goal:** Implement robust search and memory capabilities.
**Success Criteria:** Users can perform instant and semantic searches on their transcribed data.

### Features

- [x] Search Engine `[L]` - SQLite + FTS5 full-text search with ranking
- [x] Semantic Search `[XL]` - sentence-transformers + vector embeddings (all-MiniLM-L6-v2)
- [x] Hybrid Search `[M]` - Combined keyword + semantic search with weighted scoring
- [x] Web Interface `[XL]` - Flask + Bootstrap responsive interface with real-time search
- [x] Timeline Analysis `[L]` - Interactive Chart.js visualization with date filtering
- [x] Export System `[M]` - JSON, CSV, Markdown export formats
- [x] Batch Indexing `[M]` - Retroactive processing of existing transcripts
- [x] Database Schema `[S]` - Complete SQLite schema with FTS5 virtual tables
- [x] API Endpoints `[M]` - RESTful API for search, stats, timeline, export

**Status:** ✅ COMPLETE - Full search and memory system implemented with web interface. Production-ready search capabilities with both keyword and semantic understanding.

### Dependencies

- SQLite + FTS5 (built-in) ✅
- sentence-transformers ✅
- Flask + Flask-CORS ✅
- numpy, scikit-learn ✅
- Chart.js (CDN) ✅
- Bootstrap 5 (CDN) ✅

## Phase 4: Workflow Integration & Advanced Analytics Complete (v1.0.0)

**Goal:** Expand the system's capabilities for workflow integration and advanced analytics.
**Success Criteria:** System can integrate with external tools and provide cross-day pattern recognition.

### Features

- [x] Workflow Integration `[XL]` - Real-time context injection via hotkey client + internal API
- [x] Advanced Analytics `[XL]` - Cross-day pattern recognition, entity extraction, analytics dashboard
- [ ] Multi-device Sync `[L]` - Mac Mini + Raspberry Pi distributed processing (Future)
- [ ] API Ecosystem `[L]` - Extended integrations with external tools (Future)

**Status:** ✅ COMPLETE - Workflow integration and advanced analytics fully implemented. System provides real-time context injection through hotkey shortcuts and comprehensive analytics dashboard with entity tracking and trend analysis.

### Dependencies

- FastAPI + uvicorn ✅
- pynput (hotkey detection) ✅
- spaCy + en_core_web_sm (NER) ✅
- Chart.js (dashboard visualization) ✅

## Phase 5: System Reliability & Security Hardening (v1.1.0)

**Goal:** Address critical reliability and security issues to ensure production-ready system stability.
**Success Criteria:** All database operations secure, comprehensive error handling, >80% test coverage, no critical security vulnerabilities.

### Features

- [ ] Database Connection Management `[L]` - Proper connection pooling, cleanup, and error handling
- [ ] Security Hardening `[M]` - Input validation, SQL parameterization, injection prevention
- [ ] Error Handling Standardization `[M]` - Consistent patterns across all modules with proper logging
- [ ] Test Coverage Expansion `[L]` - Unit tests for audio_capture, transcribe, web_interface modules
- [ ] Security Audit Implementation `[S]` - Review and fix all identified vulnerabilities

**Status:** 🚧 IN PROGRESS - Critical issues identified in audit, systematic fixes being implemented.

### Dependencies

- pytest + pytest-cov (testing) ✅
- Comprehensive security review
- Database best practices implementation
