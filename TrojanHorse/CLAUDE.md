# TrojanHorse - Claude Handoff Documentation

## 🎯 Project Overview

**TrojanHorse** is a complete audio capture, transcription, and analysis system for macOS that runs continuously in the background. It captures system audio and microphone input, transcribes everything locally, and provides AI-powered analysis with a searchable web interface.

**Current Status**: Production-ready system with all Phase 1-3 features complete.

## 🏗️ System Architecture

### Core Components

1. **Audio Capture** (`src/audio_capture.py`)
   - Continuous FFmpeg-based recording
   - BlackHole integration for system audio
   - Microphone input capture
   - Automatic file rotation every 5 minutes

2. **Transcription Engine** (`src/transcribe.py`)
   - Multi-engine support (MacWhisper, faster-whisper)
   - Automatic processing of audio files
   - Integration with analysis pipeline

3. **Analysis System**
   - **Local Analysis** (`src/analyze_local.py`): Ollama + qwen2.5:7b
   - **Cloud Analysis** (`src/cloud_analyze.py`): OpenRouter + Gemini 2.0 Flash
   - **Unified Router** (`src/analysis_router.py`): Single interface for all analysis

4. **Search & Memory System**
   - **Search Engine** (`src/search_engine.py`): SQLite + FTS5 full-text search
   - **Semantic Search** (`src/semantic_search.py`): Vector embeddings with sentence-transformers
   - **Batch Indexer** (`src/batch_indexer.py`): Retroactive transcript processing
   - **Web Interface** (`src/web_interface.py`): Flask-based search and browsing

5. **Health Monitoring** (`src/health_monitor.py`)
   - Service status monitoring
   - Automatic restart capabilities
   - System health checks

### Data Flow

```
Audio Input → FFmpeg Capture → Transcription → Analysis → Search Indexing → Web Interface
     ↓              ↓              ↓            ↓            ↓               ↓
BlackHole/Mic → Raw Audio → Text Files → AI Analysis → Database → User Access
```

## 📁 File Organization

### Directory Structure
```
Meeting Notes/
├── YYYY-MM-DD/
│   ├── transcribed_audio/     # Transcription text files
│   ├── analysis/              # AI analysis results
│   ├── notes/                 # Manual notes
│   └── log.json              # Daily activity log
└── ...
```

### Database Schema
- **SQLite Database**: `trojan_search.db`
- **Tables**: transcripts, analysis, embeddings
- **Search**: FTS5 virtual tables for full-text search
- **Embeddings**: Vector storage for semantic search

## 🔧 Configuration

### Primary Config (`config.json`)
```json
{
  "audio": {
    "chunk_duration": 300,
    "sample_rate": 44100,
    "input_device": "BlackHole 2ch",
    "microphone_device": "Built-in Microphone"
  },
  "transcription": {
    "engine": "macwhisper",
    "language": "auto"
  },
  "storage": {
    "base_path": "/Users/USERNAME/Documents/Meeting Notes",
    "auto_delete_audio": true
  },
  "analysis": {
    "default_type": "local",
    "local_model": "qwen2.5:7b"
  },
  "cloud_analysis": {
    "openrouter_api_key": "YOUR_API_KEY",
    "model": "google/gemini-2.0-flash-001"
  }
}
```

### System Service
- **LaunchAgent**: `~/Library/LaunchAgents/com.contextcapture.audio.plist`
- **Auto-start**: Configured to start on login
- **Process Management**: Health monitoring with auto-restart

## 🚀 Operation Commands

### Daily Usage
```bash
# Check system status
python3 src/health_monitor.py status

# Start web interface
python3 src/web_interface.py --database trojan_search.db --port 5000

# Process pending transcriptions
python3 src/transcribe.py

# Index new transcripts for search
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db
```

### Maintenance
```bash
# Restart all services
python3 src/health_monitor.py restart

# Rebuild search database
rm trojan_search.db
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db

# Update semantic embeddings
python3 -c "from src.semantic_search import SemanticSearch; s=SemanticSearch('trojan_search.db'); s.batch_generate_embeddings(force_regenerate=True); s.close()"
```

## 🔍 Web Interface Features

### Search Capabilities
- **Hybrid Search**: Combines keyword matching + semantic understanding
- **Keyword Search**: Fast FTS5 full-text search
- **Semantic Search**: Vector similarity with sentence-transformers
- **Advanced Filters**: Date ranges, classification, result limits

### User Interface
- **Responsive Design**: Bootstrap 5 with mobile support
- **Real-time Search**: Debounced search as you type
- **Timeline Analysis**: Chart.js visualization of activity patterns
- **Export System**: JSON, CSV, Markdown formats
- **Individual Transcript View**: Detailed analysis display

### API Endpoints
- `POST /api/search`: Search transcripts
- `GET /api/stats`: Database statistics
- `GET /api/timeline`: Activity timeline data
- `POST /api/export`: Export search results
- `GET /transcript/<id>`: Individual transcript view

## 🧠 AI Integration

### Local Analysis (Ollama)
- **Model**: qwen2.5:7b (7B parameter model)
- **Capabilities**: Summarization, action item extraction, PII detection
- **Privacy**: Completely local processing
- **Performance**: ~2-3 seconds per transcript

### Cloud Analysis (OpenRouter)
- **Model**: google/gemini-2.0-flash-001
- **Features**: Advanced analysis, sentiment, classification
- **Cost Tracking**: Usage monitoring with daily limits
- **Fallback**: Automatic fallback to local if API fails

### Semantic Search
- **Model**: all-MiniLM-L6-v2 (384-dimensional embeddings)
- **Storage**: SQLite with pickle serialization
- **Performance**: MPS acceleration on Apple Silicon
- **Chunking**: 500 character chunks with 50 character overlap

## 🔒 Privacy & Security

### Data Protection
- **Local-first**: All transcription happens on device
- **Optional Cloud**: Cloud analysis is opt-in only
- **Auto-cleanup**: Raw audio deleted after transcription
- **No External Storage**: Search database remains local

### Audio Handling
- **Temporary Storage**: Audio files in `temp/` directory
- **Automatic Deletion**: Raw audio removed after processing
- **Retention Control**: Configurable cleanup policies

## 🐛 Common Issues & Solutions

### Audio Setup Issues
```bash
# Check audio devices
python3 src/audio_capture.py --list-devices

# Reset audio permissions
tccutil reset Microphone com.apple.Terminal

# Verify BlackHole installation
ls /Library/Audio/Plug-Ins/HAL/BlackHole2ch.driver/
```

### Service Problems
```bash
# Check service status
launchctl list | grep contextcapture

# View service logs
tail -f logs/audio_capture.err
tail -f logs/audio_capture.out

# Reinstall service
python3 src/setup.py uninstall
python3 src/setup.py install
```

### Search Issues
```bash
# Test search functionality
python3 -c "from src.search_engine import SearchEngine; s=SearchEngine('trojan_search.db'); print(s.get_stats()); s.close()"

# Rebuild search index
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db --verbose
```

### Performance Issues
```bash
# Monitor system resources
python3 src/health_monitor.py monitor

# Check disk space
df -h

# Review configuration
cat config.json
```

## 🔄 Development Workflow (Agent OS)

### Current Agent OS Integration
- **Product Documentation**: `.agent-os/product/` (mission, roadmap, tech stack)
- **Feature Specs**: `.agent-os/specs/YYYY-MM-DD-feature-name/`
- **Global Standards**: `~/.agent-os/standards/` (code style, best practices)
- **Instructions**: `~/.agent-os/instructions/` (workflows for planning and execution)

### Available Agent OS Commands
- `/plan-product`: Initialize or update product documentation
- `/create-spec`: Plan and specify new features
- `/execute-tasks`: Implement features following Agent OS workflows
- `/analyze-product`: Add Agent OS to existing codebases

### Development Phases Completed
- **✅ Phase 1**: MVP audio capture and transcription
- **✅ Phase 2**: Local and cloud AI analysis
- **✅ Phase 3**: Search engine and web interface
- **📋 Phase 4**: Future workflow integration and advanced analytics

## 📊 System Metrics

### Performance Benchmarks
- **Audio Capture**: Continuous with 5-minute chunks
- **Transcription**: ~1-2 minutes per 5-minute audio file
- **Local Analysis**: ~2-3 seconds per transcript
- **Search Performance**: <100ms for most queries
- **Web Interface**: Real-time response for search and navigation

### Resource Usage
- **CPU**: Low background usage, spikes during transcription
- **Memory**: ~200-500MB depending on loaded models
- **Disk**: ~50-100MB per day of transcripts (after audio cleanup)
- **Network**: Only for optional cloud analysis

## 🎯 Future Development Priorities

### Phase 4 Candidates
1. **Workflow Integration**: Real-time context injection
2. **Advanced Analytics**: Pattern recognition across days
3. **Multi-device Sync**: Distributed processing architecture
4. **API Ecosystem**: Integration with external tools
5. **Mobile Access**: iOS companion app for remote access

### Technical Debt
1. **Configuration Management**: More robust config validation
2. **Error Handling**: Enhanced error recovery and reporting
3. **Performance Optimization**: Database query optimization
4. **Security Hardening**: Enhanced privacy controls
5. **Documentation**: User guides and video tutorials

## 📞 Handoff Notes

### System Status
- **Production Ready**: All core functionality working
- **Stable**: No known critical bugs
- **Well Documented**: Comprehensive setup and usage guides
- **Maintainable**: Clean modular architecture with Agent OS structure

### Key Files to Monitor
- `config.json`: Primary configuration
- `logs/audio_capture.err`: Service error logs
- `logs/health_monitor.log`: System health logs
- `trojan_search.db`: Search database (backup regularly)

### Maintenance Schedule
- **Daily**: Check `python3 src/health_monitor.py status`
- **Weekly**: Review logs and disk usage
- **Monthly**: Update semantic embeddings if needed
- **As Needed**: Rebuild search index for performance

This system is ready for production use and provides a complete solution for continuous audio capture, transcription, analysis, and search. The modular architecture makes it easy to extend and maintain.