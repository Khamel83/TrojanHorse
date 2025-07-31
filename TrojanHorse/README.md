# TrojanHorse - Context Capture System

> **Note**: Despite the name, this is a legitimate personal productivity tool for audio capture and transcription. The name reflects the system's ability to "infiltrate" your daily workflow and capture context seamlessly.

A local-first, privacy-focused audio capture and transcription system that continuously records, transcribes, and organizes work-related conversations and audio into a searchable knowledge base.

## 🎯 Purpose

This system solves the problem of lost context in remote work by:
- Continuously capturing audio from meetings, calls, and conversations
- Automatically transcribing everything using local AI models
- Organizing content into daily folders for easy retrieval
- Providing a foundation for AI-assisted analysis and search

## 🏗️ Architecture

Built following the **AgentOS** methodology with modular, autonomous components:

- **capture.audio** - Continuous FFmpeg-based recording
- **transcribe.whisper** - Multi-engine transcription pipeline
- **ingest.notes** - Note organization and cleanup
- **analyze.connect** - Content linking and relationship mapping
- **process.llm** - AI-powered summarization and analysis
- **log.errors** - Comprehensive monitoring and health checks

## 🚀 Quick Start

> **📖 For complete setup instructions, see [MACHINE_SETUP.md](MACHINE_SETUP.md)**

### Prerequisites
- **macOS 10.15+** with administrator privileges
- **8GB+ RAM** (16GB recommended)
- **20GB+ free disk space**

### Essential Dependencies
```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install core dependencies
brew install ffmpeg python3 git
brew install --cask blackhole-2ch

# Install Python dependencies
pip3 install --user -r requirements.txt
```

### Quick Installation
```bash
# Clone and setup
git clone https://github.com/Khamel83/TrojanHorse.git
cd TrojanHorse

# Install Python dependencies and spaCy model
pip3 install --user -r requirements.txt
python3 -m spacy download en_core_web_sm

# Copy template configuration and edit config.json with your settings
cp config.template.json config.json
# Edit config.json with your settings (e.g., paths, API keys, hotkey)

# Install system service (sets up health_monitor.py as a launchd service)
python3 src/setup.py install

# Load and start the health_monitor service
cp com.contextcapture.audio.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.contextcapture.audio.plist

# Initialize search database (only needed once, or after deleting trojan_search.db)
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db
```

### Verify Installation
```bash
# Check overall system status (should show all services running)
python3 src/health_monitor.py status

# Open web interface in browser
open "http://127.0.0.1:5000"

# Test hotkey client (copy text to clipboard, then press Cmd+Shift+C)
# You should see a macOS notification with a search result.
```

## 📂 Project Structure

```
TrojanHorse/
├── src/                           # Core source code
│   ├── audio_capture.py          # Core audio recording engine
│   ├── transcribe.py             # Multi-engine transcription 
│   ├── analysis_router.py        # Unified analysis interface
│   ├── analyze_local.py          # Local Ollama-based analysis
│   ├── cloud_analyze.py          # OpenRouter cloud analysis
│   ├── search_engine.py          # SQLite + FTS5 search engine
│   ├── semantic_search.py        # Vector embeddings + semantic search
│   ├── web_interface.py          # Flask web interface
│   ├── batch_indexer.py          # Retroactive transcript indexing
│   ├── health_monitor.py         # System monitoring & restart
│   ├── setup.py                  # Installation & management
│   ├── database_schema.sql       # Search database schema
│   ├── analytics_engine.py       # Advanced analytics engine
│   ├── internal_api.py           # Internal API server for workflow integration
│   └── hotkey_client.py          # Hotkey listener for workflow integration
├── templates/                     # Web interface templates
│   ├── base.html                 # Base template with Bootstrap
│   ├── index.html                # Main search interface
│   └── transcript.html           # Individual transcript view
├── static/                        # Web interface assets
│   ├── css/style.css             # Custom styles
│   └── js/app.js                 # JavaScript functionality
├── .agent-os/                     # Agent OS development framework
│   ├── product/                  # Product documentation
│   └── specs/                    # Feature specifications
├── docs/                          # Technical documentation
├── config.json                    # System configuration
├── requirements.txt               # Python dependencies
├── MACHINE_SETUP.md              # Complete setup guide
└── logs/                         # System logs
```

## 🎛️ Configuration

The system uses `config.json` for all settings. Below is an example of the structure, including newly added sections:

```json
{
  "audio": {
    "chunk_duration": 300,
    "sample_rate": 44100,
    "quality": "medium",
    "format": "wav"
  },
  "storage": {
    "temp_path": "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/MacProAudio",
    "base_path": "/Users/hr-svp-mac12/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes",
    "auto_delete_audio": true
  },
  "transcription": {
    "engine": "macwhisper",
    "language": "auto",
    "model_size": "base"
  },
  "cloud_analysis": {
    "openrouter_api_key": "YOUR_OPENROUTER_API_KEY_HERE",
    "model": "google/gemini-2.0-flash-001",
    "base_url": "https://openrouter.ai/api/v1"
  },
  "analysis": {
    "default_mode": "local",
    "local_model": "qwen3:8b",
    "cloud_model": "google/gemini-2.0-flash-001",
    "cost_limit_daily": 0.20,
    "enable_pii_detection": true,
    "hybrid_threshold_words": 1000
  },
  "privacy": {
    "redaction_keywords": []
  },
  "workflow_integration": {
    "hotkey": "<cmd>+<shift>+c",
    "internal_api_port": 5001
  }
}
```

## 🔧 Commands

All primary system management and monitoring commands are now consolidated under `health_monitor.py`.

```bash
# Start all core services (audio capture, internal API, hotkey client)
python3 src/health_monitor.py start

# Stop all core services
python3 src/health_monitor.py stop

# Restart all core services
python3 src/health_monitor.py restart

# Check overall system status
python3 src/health_monitor.py status

# Run a comprehensive health check and exit with status code
python3 src/health_monitor.py check

# Start continuous monitoring loop (restarts services if unhealthy)
python3 src/health_monitor.py monitor

# Optimize the search database (runs VACUUM)
python3 src/health_monitor.py optimize

# Run advanced analytics (entity extraction, trend calculation)
python3 src/health_monitor.py analyze
```

**Other Utility Commands:**

```bash
# Install/Uninstall system service (uses launchd)
python3 src/setup.py install
python3 src/setup.py uninstall

# Verify Python dependencies
python3 src/setup.py check

# List available audio devices
python3 src/audio_capture.py --list-devices

# Manually process pending audio files for transcription
python3 src/transcribe.py

# Manually index new transcripts for search
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db

# Start the web interface (for direct access, usually managed by health_monitor)
python3 src/web_interface.py --database trojan_search.db --port 5000
```

## 📊 Output Structure

Daily organized folders with automatic cleanup:

```
Meeting Notes/
├── 2025-07-30/
│   ├── notes/
│   │   └── 2025-07-30.md           # Manual/imported notes
│   ├── transcribed_audio/
│   │   ├── audio_140532.txt        # Transcribed content
│   │   └── audio_141032.txt
│   ├── files/
│   │   └── screenshots/            # Associated files
│   └── log.json                    # Daily activity log
└── 2025-07-31/
    └── ...
```

## 🔒 Privacy & Security

- **Local-first**: All transcription happens on your machine
- **No cloud dependencies**: Optional API usage only for advanced analysis
- **Automatic cleanup**: Raw audio deleted after transcription
- **Configurable retention**: Control data retention policies
- **Encrypted storage**: Optional encryption for sensitive content

## 🛠️ Development Status

**✅ Phase 1 Complete (v0.1.0)** - MVP:
- ✅ Continuous audio capture with FFmpeg
- ✅ Multi-engine transcription (MacWhisper, faster-whisper)
- ✅ Health monitoring and auto-restart
- ✅ macOS service integration with LaunchAgent
- ✅ Daily folder organization with automatic cleanup

**✅ Phase 2 Complete (v0.2.0)** - Local-First Intelligence:
- ✅ **Local LLM Analysis**: Ollama integration with qwen2.5:7b model
- ✅ **Cloud Intelligence**: OpenRouter API with Gemini 2.0 Flash
- ✅ **Privacy Architecture**: PII detection and local-first processing
- ✅ **Cost Optimization**: Usage tracking and daily limits
- ✅ **Architecture Unification**: Unified analysis_router.py interface

**✅ Phase 3 Complete (v0.3.0)** - Search & Memory:
- ✅ **Search Engine**: SQLite + FTS5 full-text search with ranking
- ✅ **Semantic Search**: sentence-transformers with vector embeddings
- ✅ **Hybrid Search**: Combined keyword + semantic search with scoring
- ✅ **Web Interface**: Flask + Bootstrap responsive interface
- ✅ **Timeline Analysis**: Interactive Chart.js visualization
- ✅ **Export System**: JSON, CSV, and Markdown export formats
- ✅ **Batch Indexing**: Retroactive processing of existing transcripts

**✅ Phase 4 Complete (v1.0.0)** - Advanced Features:
- ✅ **Workflow Integration**: Real-time context injection (Internal API + Hotkey Client)
- ✅ **Advanced Analytics**: Cross-day pattern recognition and insights (Analytics Engine + Dashboard)
- 📋 **Multi-device Sync**: Mac Mini + Raspberry Pi distributed processing (Future)
- 📋 **API Ecosystem**: Integration with external tools (Future)

**🎯 Current Status**: Production-ready system with complete audio capture, transcription, analysis, search, advanced analytics, and workflow integration capabilities. Web interface available for browsing and searching all captured content.

See [Development Roadmap](.agent-os/product/roadmap.md) for detailed implementation phases.

## 🐛 Troubleshooting

**Service Issues**:
- Check `logs/audio_capture.err` for FFmpeg errors
- Verify microphone permissions in System Preferences
- Ensure BlackHole is properly configured

**Audio Problems**:
- Run `python3 audio_capture.py --list-devices`
- Check device indices in audio_capture.py
- Test BlackHole system audio routing

**Transcription Failures**:
- Verify MacWhisper or faster-whisper installation
- Check available disk space
- Review transcription.log for errors

## 🚀 Agent OS Integration

This project is managed using **Agent OS**, a structured AI-assisted development methodology. For detailed instructions, see the [Agent OS Integration Guide](.agent-os/README.md).

### How to Use Agent OS

**For AI Agents/LLMs:**

When working on this project, please adhere to the Agent OS workflows:

-   **Product Planning:** When asked to plan or initialize the product, use the instructions at `@.agent-os/instructions/plan-product.md`.
-   **Feature Specification:** For new features, use `@.agent-os/instructions/create-spec.md`.
-   **Task Execution:** When implementing tasks, follow the breakdown in the relevant spec file.
-   **Project Analysis:** To analyze the existing codebase, use `@.agent-os/instructions/analyze-product.md`.

Always check for and load context from `mission-lite.md` and `spec-lite.md` files when available.

**For Humans:**

Use the following commands to interact with Agent OS:

-   `/plan-product`: Initialize or update product documentation.
-   `/create-spec`: Plan and specify a new feature.
-   `/execute-tasks`: Implement tasks from a specification.
-   `/analyze-product`: Add or update the Agent OS structure for the project.

For the current development status, please see the "Development Status" section of this README and the [Development Roadmap](.agent-os/product/roadmap.md).

## 📖 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Detailed Setup Guide](docs/SETUP.md)
- [API Reference](docs/API.md)
- [Agent OS Integration](.agent-os/README.md)
- [Product Roadmap](.agent-os/product/roadmap.md)
- [Project History](docs/HISTORY.md)

## 🤝 Contributing

This is a personal project, but the modular architecture makes it easy to:
- Add new transcription engines
- Implement different storage backends
- Extend analysis capabilities
- Integrate with other tools

## 📄 License

Private project - not for public distribution.

---

*Built with Claude Code for continuous context capture and knowledge management.*