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

# Configure audio (see MACHINE_SETUP.md for detailed steps)
cp config.template.json config.json
# Edit config.json with your settings

# Install system service
python3 src/setup.py install

# Initialize search database
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db
```

### Verify Installation
```bash
# Check system status
python3 src/health_monitor.py status

# Start web interface
python3 src/web_interface.py --database trojan_search.db --port 5000

# Open in browser
open "http://127.0.0.1:5000"
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
│   └── database_schema.sql       # Search database schema
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

The system uses `config.json` for all settings:

```json
{
  "audio": {
    "chunk_duration": 300,
    "sample_rate": 44100,
    "quality": "medium"
  },
  "transcription": {
    "engine": "macwhisper",
    "language": "auto", 
    "model_size": "base"
  },
  "storage": {
    "auto_delete_audio": true,
    "base_path": "/path/to/Meeting Notes"
  },
  "cloud_analysis": {
    "openrouter_api_key": "YOUR_OPENROUTER_API_KEY_HERE",
    "model": "google/gemini-2.0-flash-001",
    "base_url": "https://openrouter.ai/api/v1"
  },
  "analysis": {
    "default_type": "prompt"
  }
}
```

## 🔧 Commands

```bash
# System Management
python3 src/setup.py install      # Install service
python3 src/setup.py uninstall    # Remove service  
python3 src/setup.py check        # Verify dependencies

# Health Monitoring
python3 src/health_monitor.py status    # System status
python3 src/health_monitor.py check     # Health verification
python3 src/health_monitor.py restart   # Restart services
python3 src/health_monitor.py monitor   # Continuous monitoring

# Audio & Transcription
python3 src/audio_capture.py --list-devices  # Show audio devices
python3 src/transcribe.py /path/to/audio.wav # Manual transcription
python3 src/transcribe.py                    # Process pending files

# Search & Analysis
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db  # Index transcripts
python3 src/web_interface.py --database trojan_search.db --port 5000  # Start web interface
python3 src/search_engine.py  # Test search functionality
python3 src/semantic_search.py  # Test semantic search

# Analysis
python3 src/analysis_router.py --file transcript.txt  # Analyze single file
python3 src/analyze_local.py --test   # Test local analysis
python3 src/cloud_analyze.py --test   # Test cloud analysis
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

**📋 Phase 4 Future (v1.0.0)** - Advanced Features:
- 📋 **Workflow Integration**: Real-time context injection for work
- 📋 **Advanced Analytics**: Cross-day pattern recognition and insights
- 📋 **Multi-device Sync**: Mac Mini + Raspberry Pi distributed processing
- 📋 **API Ecosystem**: Integration with external tools and services

**🎯 Current Status**: Production-ready system with complete audio capture, transcription, analysis, and search capabilities. Web interface available for browsing and searching all captured content.

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

This project uses **Agent OS** for structured AI-assisted development:

### Development Workflows
- **Product Planning**: Managed via `.agent-os/product/` documentation
- **Feature Development**: Specs created in `.agent-os/specs/YYYY-MM-DD-feature-name/`
- **Task Execution**: Guided by Agent OS task breakdown and execution workflows

### Available Commands
- `/plan-product` - Initialize or update product documentation
- `/create-spec` - Plan and specify new features
- `/execute-tasks` - Implement features following Agent OS workflows
- `/analyze-product` - Add Agent OS to existing codebases

### Current Status
- **Phase 1**: ✅ MVP Complete (audio capture + transcription)
- **Phase 2**: ✅ Mostly Complete (local + cloud AI analysis)
- **Phase 3**: 🎯 Current Target (search & memory system)
- **Phase 4**: 📋 Future (workflow integration + advanced analytics)

See `.agent-os/product/roadmap.md` for detailed development phases.

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