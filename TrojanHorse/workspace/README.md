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

### Prerequisites
```bash
# Install dependencies
brew install ffmpeg
pip install faster-whisper  # optional, for local transcription

# Set up BlackHole for system audio capture
# Download from: https://existential.audio/blackhole/
```

### Installation
```bash
# Clone and setup
git clone https://github.com/Khamel83/TrojanHorse.git
cd TrojanHorse
python3 setup.py install
```

### Verify Installation
```bash
python3 health_monitor.py status
```

## 📂 Project Structure

```
TrojanHorse/
├── audio_capture.py          # Core audio recording engine
├── transcribe.py             # Multi-engine transcription with analysis integration
├── analyze_local.py          # Local Ollama-based analysis with PII detection
├── cloud_analyze.py          # OpenRouter cloud analysis integration
├── process_gemini.py         # Advanced Gemini analysis with cost tracking
├── health_monitor.py         # System monitoring & restart
├── setup.py                  # Installation & management
├── com.contextcapture.audio.plist  # macOS service config
├── config.json               # System configuration
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md       # Technical architecture
│   ├── SETUP.md             # Detailed setup guide
│   └── API.md               # Module interfaces
└── logs/                     # System logs
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
python3 setup.py install      # Install service
python3 setup.py uninstall    # Remove service  
python3 setup.py check        # Verify dependencies

# Health Monitoring
python3 health_monitor.py status    # System status
python3 health_monitor.py check     # Health verification
python3 health_monitor.py restart   # Restart services
python3 health_monitor.py monitor   # Continuous monitoring

# Audio & Transcription
python3 audio_capture.py --list-devices  # Show audio devices
python3 transcribe.py /path/to/audio.wav # Manual transcription
python3 transcribe.py                    # Process pending files
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

**MVP Complete (v0.1.0)**:
- ✅ Continuous audio capture
- ✅ Multi-engine transcription
- ✅ Health monitoring
- ✅ macOS service integration
- ✅ Daily folder organization

**Phase 2 (v0.2.0)** - Local-First Intelligence:
- ✅ **Local LLM Analysis**: Implemented (analyze_local.py with Ollama + qwen3:8b)
- ✅ **Cloud Intelligence**: Implemented (cloud_analyze.py + process_gemini.py)
- ✅ **Privacy Architecture**: Implemented (PII detection in analyze_local.py)
- ✅ **Cost Optimization**: Implemented (cost tracking in process_gemini.py)
- 🔄 **Architecture Unification**: Replace complex implementations with unified analysis_router.py

**Phase 3 (v0.3.0)** - Search & Memory:
- 🔄 **Search Engine**: SQLite + FTS5 for instant content retrieval
- 🔄 **Semantic Search**: Vector embeddings for concept-based queries
- 🔄 **Web Interface**: Flask-based search and browsing interface
- 🔄 **Batch Indexing**: Retroactive processing of existing transcripts

**Future (v1.0.0)**:
- 📋 **Workflow Integration**: Real-time context injection for work
- 📋 **Advanced Analytics**: Cross-day pattern recognition and insights
- 📋 **Multi-device Sync**: Mac Mini + Raspberry Pi distributed processing
- 📋 **API Ecosystem**: Integration with external tools and services

See [Development Roadmap](docs/ROADMAP.md) for detailed implementation plan.

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

## 📖 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Detailed Setup Guide](docs/SETUP.md)
- [API Reference](docs/API.md)
- [Development Roadmap](docs/ROADMAP.md)
- [Implementation Tasks](docs/TASKS.md)
- [Final Implementation Plan](docs/FINAL_PLAN.md)
- [Project History](CLAUDE.md)

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