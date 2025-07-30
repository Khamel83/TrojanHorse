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

- [ ] Local LLM Analysis `[L]`
- [ ] Cloud Intelligence `[M]`
- [ ] Privacy Architecture `[M]`
- [ ] Content Classification `[L]`
- [ ] Cost Optimization `[S]`

### Dependencies

- Ollama
- OpenRouter

## Phase 3: Search & Memory (v0.3.0)

**Goal:** Implement robust search and memory capabilities.
**Success Criteria:** Users can perform instant and semantic searches on their transcribed data.

### Features

- [ ] Search & Memory `[L]`
- [ ] Semantic Search `[XL]`
- [ ] Timeline Analysis `[L]`
- [ ] Export System `[M]`

### Dependencies

- SQLite + FTS5

## Phase 4: Future (v1.0.0)

**Goal:** Expand the system's capabilities for workflow integration and advanced analytics.
**Success Criteria:** System can integrate with external tools and provide cross-day pattern recognition.

### Features

- [ ] Workflow Integration `[XL]`
- [ ] Advanced Analytics `[XL]`
- [ ] Multi-device Sync `[L]`
- [ ] API Ecosystem `[L]`
