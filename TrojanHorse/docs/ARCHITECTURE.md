# Architecture Overview

## System Design Philosophy

TrojanHorse follows the **AgentOS** methodology, treating each component as an autonomous agent with clear input/output contracts and independent failure modes.

## Core Principles

1. **Local-First**: All critical processing happens on-device
2. **Modular Design**: Components can be developed, tested, and deployed independently
3. **Graceful Degradation**: System continues operating even if non-critical components fail
4. **Observable**: Comprehensive logging and monitoring for debugging and optimization
5. **Privacy-Preserving**: Sensitive data never leaves the local environment unless explicitly configured

## Component Architecture

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                                  TrojanHorse System                                       │
├───────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │   capture   │  │ transcribe  │  │   analyze   │  │   analytics │  │   internal  │  │
│  │   .audio    │──┤  .whisper   │──┤  .router    │──┤   .engine   │──┤    .api     │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                            │                │                │          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │   search    │  │    web      │  │   health    │  │   hotkey    │  │             │  │
│  │  .engine    │  │ .interface  │  │  .monitor   │  │   .client   │  │             │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
├───────────────────────────────────────────────────────────────────────────────────────────┤
│    Local Analysis (Ollama)  │  Cloud Analysis (OpenRouter) │                           │
│         analyze_local.py    │        cloud_analyze.py      │                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

## Module Specifications

### capture.audio
**Purpose**: Continuous audio recording from multiple sources
**Inputs**: Microphone stream, system audio (via BlackHole)
**Outputs**: 5-minute WAV chunks in temp directory
**Technology**: FFmpeg with AVFoundation backend
**Failure Mode**: Stop recording, alert user, attempt restart (managed by `health_monitor`)

**Key Features**:
- Device priority management (AirPods > Built-in > Internal)
- Automatic file rotation every 5 minutes
- Graceful shutdown handling
- Audio device detection and validation

### transcribe.whisper
**Purpose**: Convert audio files to text transcripts
**Inputs**: WAV files from capture.audio
**Outputs**: Text files with timestamps and metadata
**Technology**: MacWhisper Pro → faster-whisper → system whisper
**Failure Mode**: Retry with fallback engines, move failed files to `failed/` directory

**Key Features**:
- Multi-engine fallback strategy
- Automatic language detection
- Post-processing and metadata addition
- Integration with analysis router for immediate processing

### analyze.router
**Purpose**: Unified analysis interface routing to local or cloud processing
**Inputs**: Transcript files, user choice (local/cloud/both)
**Outputs**: Analysis results, daily summary updates
**Technology**: Python router calling specialized analysis modules
**Failure Mode**: Graceful degradation, preserve transcript if analysis fails, retry mechanism for cloud calls

**Key Features**:
- Interactive analysis choice with auto-mode settings
- Backward compatibility with existing analysis formats
- Unified interface replacing complex analyze_local.py and process_gemini.py
- Cost tracking and privacy filtering (redaction of keywords)

### analytics.engine
**Purpose**: Performs cross-transcript analysis, entity extraction, and trend calculation.
**Inputs**: Raw transcript text from database.
**Outputs**: Populated `analytics_entities` and `analytics_trends` database tables.
**Technology**: `spaCy` for Named Entity Recognition (NER), SQLite for storage.
**Failure Mode**: Logs errors, skips problematic transcripts.

**Key Features**:
- Identifies PERSON, ORG, GPE entities.
- Calculates daily and weekly entity frequencies.
- Determines trending entities.

### internal.api
**Purpose**: Provides a lightweight, local API for quick search access, primarily for the hotkey client.
**Inputs**: HTTP GET requests with a `query` parameter.
**Outputs**: JSON response with top search results.
**Technology**: FastAPI, Uvicorn, `search_engine.py`.
**Failure Mode**: Returns error response, logs issues.

**Key Features**:
- Fast, low-overhead search endpoint.
- Integrates with existing hybrid search functionality.

### hotkey.client
**Purpose**: Listens for a system-wide hotkey to trigger searches via the internal API and display notifications.
**Inputs**: User-defined hotkey press, clipboard content.
**Outputs**: macOS system notifications.
**Technology**: `pynput`, `pyperclip`, `requests`, `osascript`.
**Failure Mode**: Logs errors, displays error notifications.

**Key Features**:
- Configurable hotkey.
- Seamless integration with system clipboard.
- Displays search results as non-intrusive notifications.

### search.engine
**Purpose**: Fast keyword and semantic search across all transcripts
**Inputs**: Search queries, date filters, content type filters
**Outputs**: Ranked search results with snippets
**Technology**: SQLite + FTS5 + sentence-transformers embeddings
**Failure Mode**: Fallback to basic file search, continue indexing

**Key Features**:
- Hybrid search combining keyword + semantic similarity
- Batch indexing of existing transcripts
- Performance optimization for large transcript volumes (VACUUM command)

### web.interface
**Purpose**: Browser-based search and browsing interface, including analytics dashboard.
**Inputs**: HTTP requests, search queries
**Outputs**: HTML search interface and results, analytics visualizations
**Technology**: Flask with responsive design, Chart.js
**Failure Mode**: Fallback to command-line search tools

**Key Features**:
- Timeline view for conversation patterns
- Mobile-responsive design
- Basic authentication for security
- Post-processing and metadata addition
- Audio cleanup after successful transcription
- Analytics Dashboard with entity and trend visualizations.

### health.monitor
**Purpose**: Centralized system health monitoring and service management for all core TrojanHorse components.
**Inputs**: Internal service statuses, file system checks, configuration.
**Outputs**: Consolidated logs, health metrics, alerts, service control.
**Technology**: Python subprocess management, logging.
**Failure Mode**: Attempts service restarts, sends notifications, logs critical errors.

**Key Features**:
- Manages `audio_capture`, `internal_api`, `hotkey_client` processes.
- Checks for recent audio/analysis file creation.
- Monitors disk space and analysis capabilities.
- Provides `start`, `stop`, `restart`, `status`, `check`, `monitor`, `optimize`, `analyze` CLI commands.

### ingest.notes
**Purpose**: Organize and clean user-authored notes
**Inputs**: Markdown files from Capacities or manual creation
**Outputs**: Cleaned, timestamped daily note files
**Technology**: Python markdown processing
**Failure Mode**: Preserve original files, log processing errors

**Key Features**:
- Multi-source note aggregation
- Timestamp normalization
- Content cleanup and formatting
- Duplicate detection and merging

### analyze.connect
**Purpose**: Link related content across time and context
**Inputs**: Transcripts and notes from same date
**Outputs**: Relationship maps and cross-references
**Technology**: Text similarity analysis, future vector embeddings
**Failure Mode**: Skip analysis, preserve source data

**Key Features**:
- Timestamp-based proximity matching
- Content similarity detection
- Cross-day relationship building
- Metadata enrichment

### process.llm
**Purpose**: AI-powered summarization and analysis
**Inputs**: Complete daily content folders
**Outputs**: Summaries, action items, tags, classifications
**Technology**: Ollama (local) + OpenRouter (cloud) hybrid
**Failure Mode**: Skip processing, log errors, preserve inputs

**Key Features**:
- Privacy-aware content filtering
- Local vs cloud processing decisions
- Incremental analysis updates
- Multiple output formats

### log.errors
**Purpose**: Centralized logging and system health monitoring
**Inputs**: Log streams from all modules
**Outputs**: Consolidated logs, health metrics, alerts
**Technology**: Python logging + SQLite for queries
**Failure Mode**: Basic file logging, reduced functionality

**Key Features**:
- Structured JSON logging
- Health metric collection
- Error aggregation and alerting
- Performance monitoring

## Data Flow Architecture

```
Audio Sources → capture.audio → Temp Storage → transcribe.whisper → Daily Folders (Transcripts)
                                                               ↓
                                                               analyze.router
                                                               ↓
                                                               analytics.engine → Database (Entities, Trends)
                                                               ↓
                                                               process.llm → Summaries & Analysis
                                                               ↓
Manual Notes → ingest.notes ───────────────────────────────────┤
                                                               ↓
                                                               search.engine → Indexed Storage (SQLite)
                                                               ↓
                                                               web.interface (UI) & internal.api (Hotkey Client)
```

## Storage Architecture

### Directory Structure
```
Meeting Notes/
├── YYYY-MM-DD/
│   ├── notes/
│   │   └── YYYY-MM-DD.md          # Consolidated daily notes
│   ├── transcribed_audio/
│   │   ├── audio_HHMMSS.txt       # Individual transcripts
│   │   └── metadata.json          # Audio session metadata
│   ├── files/
│   │   ├── screenshots/           # Associated images
│   │   ├── documents/             # PDFs, emails, etc.
│   │   └── links/                 # Saved web content
│   ├── analysis/
│   │   ├── summary.md             # Daily summary
│   │   ├── actions.json           # Extracted action items
│   │   └── tags.json              # Auto-generated tags
│   └── log.json                   # Daily activity log
```

### File Naming Conventions
- **Audio**: `audio_HHMMSS.{wav,txt}` (24-hour format)
- **Notes**: `YYYY-MM-DD.md` (ISO date format)
- **Logs**: `log.json` (structured JSON)
- **Analysis**: Descriptive names (`summary.md`, `actions.json`)

## Service Architecture

### macOS LaunchAgent Integration
`com.contextcapture.audio.plist` now primarily manages the `health_monitor.py` service, which in turn orchestrates all other core components (`audio_capture.py`, `internal_api.py`, `hotkey_client.py`).

```xml
com.contextcapture.audio.plist
├── Auto-start on user login
├── Crash recovery and restart (for health_monitor)
├── Background process management (for health_monitor)
├── Proper signal handling (for health_monitor)
└── Log file management (for health_monitor)
```

### Health Monitoring
- **Service Status**: Direct process monitoring of `audio_capture`, `internal_api`, `hotkey_client`.
- **File Activity**: Recent audio file creation verification.
- **Disk Space**: Storage availability checking.
- **Component Health**: Module-specific health checks.
- **Auto-Recovery**: Service restart on failure detection.
- **New Commands**: `start`, `stop`, `restart`, `optimize`, `analyze` for comprehensive system control.

## Security & Privacy Architecture

### Data Protection Layers
1. **Local Processing**: All transcription and analysis local by default
2. **Selective Cloud Use**: Only sanitized, non-sensitive data sent to APIs
3. **Automatic Cleanup**: Raw audio deleted after successful transcription
4. **Access Control**: File permissions restrict access to user only
5. **Optional Encryption**: Future support for encrypted storage

### Privacy Controls
- **Content Filtering**: Local LLM identifies sensitive information
- **API Sanitization**: Strip PII before cloud processing
- **Retention Policies**: Automatic cleanup of old data
- **Audit Logging**: Track all data access and processing

## Performance Considerations

### Resource Management
- **CPU**: Background priority for continuous processes
- **Memory**: Streaming processing to minimize RAM usage
- **Disk I/O**: Efficient file operations and cleanup
- **Network**: Minimal bandwidth usage, local-first approach

### Scalability Design
- **Chunked Processing**: 5-minute audio segments prevent memory issues
- **Incremental Analysis**: Process only new content each day
- **Database Indexing**: SQLite for fast search and retrieval
- **Async Operations**: Non-blocking transcription and analysis

## Integration Points

### External Tool Integration
- **Capacities**: Note import and export
- **Obsidian**: Markdown file compatibility
- **Notion**: API integration for summary export
- **Calendar Apps**: Meeting context integration
- **Email**: Automatic email content capture

### API Interfaces
- **REST API**: Web interface for system control (now includes analytics dashboard)
- **CLI Interface**: Command-line tools for automation (consolidated under `health_monitor.py`)
- **Python API**: Direct module integration
- **Internal API**: Lightweight local API for workflow integration (e.g., hotkey client)
- **Webhook Support**: External system notifications

## Monitoring & Observability

### Logging Strategy
- **Structured JSON**: Machine-readable log format
- **Multiple Levels**: Debug, Info, Warning, Error classifications
- **Component Isolation**: Separate log streams per module
- **Retention Policy**: Automatic log rotation and cleanup

### Metrics Collection
- **System Health**: CPU, memory, disk usage
- **Processing Stats**: Transcription success rates, processing times
- **User Activity**: Capture duration, content volume
- **Error Rates**: Failure frequencies by component

### Alerting System
- **macOS Notifications**: User-visible system alerts
- **Log-based Alerts**: Automated error detection
- **Health Check Failures**: Service restart notifications
- **Storage Warnings**: Disk space and retention alerts

## Future Architecture Evolution

### Phase 2: Enhanced Analysis (Completed)
- **Vector Embeddings**: Semantic content search
- **Graph Database**: Relationship mapping between content
- **Real-time Processing**: Live transcription and analysis
- **Multi-modal Input**: Video and image content analysis

### Phase 3: Collaborative Features (Future)
- **Shared Contexts**: Team workspace integration
- **Real-time Sync**: Multi-device content synchronization
- **Conflict Resolution**: Merge strategies for concurrent edits
- **Access Control**: User and role-based permissions

### Phase 4: Intelligence Layer (Future)
- **Predictive Analysis**: Proactive content suggestions
- **Automated Actions**: Smart response to content patterns
- **Learning System**: Adaptive behavior based on usage
- **Advanced RAG**: Sophisticated context retrieval and synthesis