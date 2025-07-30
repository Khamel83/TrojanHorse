# CLAUDE.md - Project Development History

This file tracks the development history and AI assistance for the TrojanHorse Context Capture System.

## Project Overview

**Project Name**: TrojanHorse (Context Capture System)
**Started**: 2025-07-30
**AI Assistant**: Claude (Sonnet 4)
**Development Approach**: AgentOS methodology with modular, autonomous components

## Initial Vision & Requirements

### Core Problem
Lost context in remote work - conversations, meetings, and audio content that gets forgotten or becomes difficult to retrieve.

### Solution Architecture
Local-first audio capture and transcription system that:
- Continuously records mic + system audio
- Auto-transcribes using local AI models
- Organizes content into daily folder structures
- Provides foundation for AI-assisted analysis

### Key Design Principles
- **Local-first**: Privacy-respecting, minimal cloud dependencies
- **Modular**: Each component can fail gracefully and be rebuilt
- **Resilient**: Health monitoring and auto-restart capabilities
- **Human-readable**: Logs and outputs designed for observability
- **Long-term thinking**: Designed for slow, stable, persistent operation

## Development Sessions

### Session 1: 2025-07-30 - MVP Architecture & Implementation

**Context**: User presented comprehensive AgentOS-style specification for audio capture system.

**Analysis Completed**:
- ✅ Project naming concerns (noted security implications)
- ✅ Technical architecture review (modular design strengths)
- ✅ Privacy & security considerations
- ✅ Scalability & performance planning
- ✅ Tooling & dependency evaluation
- ✅ Implementation improvement recommendations

**Key Recommendations Made**:
- Encryption for sensitive data (later simplified to optional)
- Local vs API processing strategy (Ollama + OpenRouter hybrid)
- Configuration management structure
- SQLite indexing for future search capabilities
- Phased implementation approach

**MVP Components Built**:
1. **audio_capture.py** - Core FFmpeg-based continuous recording
   - 5-minute chunk capture
   - Mic + system audio mixing via BlackHole
   - Auto-move to daily folders
   - Graceful shutdown handling
   - Device detection and configuration

2. **transcribe.py** - Multi-engine transcription pipeline
   - MacWhisper Pro (primary)
   - faster-whisper (fallback)
   - System whisper (last resort)
   - Auto-delete raw audio after transcription
   - Post-processing and metadata addition

3. **health_monitor.py** - System monitoring and recovery
   - Service status checking
   - Recent file verification
   - Disk space monitoring
   - Auto-restart capabilities
   - macOS notification integration
   - Comprehensive status reporting

4. **setup.py** - Installation and management
   - Dependency checking
   - Folder structure creation
   - Service installation/uninstallation
   - Configuration generation

5. **com.contextcapture.audio.plist** - macOS LaunchAgent service
   - Auto-start on boot
   - Crash recovery
   - Background processing
   - Proper logging paths

**Configuration Strategy**:
- JSON-based configuration with sensible defaults
- Modular settings per component
- Easy customization for different use cases

**Documentation Created**:
- Comprehensive README with setup instructions
- Usage commands and troubleshooting
- Architecture overview and file structure

### Session 2: 2025-07-30 - Repository Setup & Documentation

**Context**: User requested GitHub repository setup with proper version control and documentation.

**Repository Initialization**:
- ✅ Git repository initialized
- ✅ Remote origin added (https://github.com/Khamel83/TrojanHorse.git)
- ✅ Comprehensive .gitignore created
- ✅ Enhanced README.md with full project documentation

**Documentation Structure**:
1. **README.md** - Main project documentation
   - Purpose and architecture overview
   - Quick start guide
   - Configuration options
   - Command reference
   - Troubleshooting guide
   - Development roadmap

2. **CLAUDE.md** - This development history file
   - Project tracking and decision rationale
   - AI assistance documentation
   - Development session logs

3. **.gitignore** - Comprehensive exclusions
   - Python artifacts
   - Audio files (too large)
   - Personal data directories
   - Configuration with sensitive data
   - Platform-specific files

**Planned Documentation** (to be created):
- `docs/ARCHITECTURE.md` - Technical deep dive
- `docs/SETUP.md` - Detailed installation guide
- `docs/API.md` - Module interface documentation

## Technical Decisions & Rationale

### Audio Capture Strategy
**Decision**: FFmpeg with BlackHole for system audio
**Rationale**: 
- Cross-platform compatibility
- Professional-grade audio handling
- Flexible device configuration
- No proprietary dependencies

### Transcription Pipeline
**Decision**: Multi-engine fallback approach
**Rationale**:
- Reliability through redundancy
- Flexibility for different environments
- Local-first with cloud backup options
- Cost optimization (local when possible)

### Service Architecture
**Decision**: macOS LaunchAgent for always-on operation
**Rationale**:
- Native system integration
- Auto-start and crash recovery
- Proper background operation
- System-level service management

### Storage Strategy
**Decision**: Daily folder structure with auto-cleanup
**Rationale**:
- Human-readable organization
- Easy manual browsing
- Reduced storage requirements
- Clear retention policies

### Health Monitoring
**Decision**: Comprehensive monitoring with auto-restart
**Rationale**:
- Reliability for critical capture phase
- Proactive issue detection
- Minimal manual intervention required
- Clear status visibility

## Future Development Phases

### Phase 2: Local LLM Integration
- Ollama integration for privacy-sensitive processing
- Content classification and filtering
- Basic summarization and tagging
- PII detection and sanitization

### Phase 3: Search & Indexing
- SQLite database for full-text search
- Cross-day content linking
- Tag-based organization
- Timeline view and navigation

### Phase 4: Advanced Analysis
- RAG implementation for context queries
- Project-based content tracking
- Meeting summaries and action items
- Integration with external tools

## Known Issues & Technical Debt

### Current Limitations
1. **BlackHole dependency**: Requires manual setup
2. **Device-specific configuration**: FFmpeg device indices may need adjustment
3. **Single-platform**: Currently macOS-only
4. **Limited error recovery**: Some failure modes require manual intervention

### Planned Improvements
1. **Enhanced audio device detection**: Auto-configure device indices
2. **Cross-platform support**: Linux and Windows compatibility
3. **Web interface**: Status dashboard and configuration UI
4. **Database migration**: Move from file-based to SQLite storage

## Development Environment

**Platform**: macOS (Darwin 24.5.0)
**Python**: 3.x (system Python)
**Key Dependencies**:
- FFmpeg (via Homebrew)
- BlackHole (audio routing)
- MacWhisper Pro (optional)
- faster-whisper (optional)

**IDE/Tools**:
- Claude Code for development
- Git for version control
- GitHub for repository hosting

## AI Assistance Notes

### Claude's Contributions
1. **Architecture Review**: Comprehensive analysis of initial specification
2. **Code Generation**: Complete MVP implementation in single session
3. **Best Practices**: Security, privacy, and reliability recommendations
4. **Documentation**: Professional-grade README and setup guides
5. **Repository Setup**: Proper version control initialization

### Human-AI Collaboration Patterns
- **Specification-driven development**: User provided clear AgentOS spec
- **Iterative refinement**: Real-time feedback and adjustments
- **Comprehensive implementation**: Full working system in single session
- **Documentation focus**: Emphasis on maintainability and future development

### Development Methodology
- **AgentOS principles**: Modular, autonomous components
- **Local-first approach**: Privacy and control prioritized
- **MVP methodology**: Core functionality first, extensibility planned
- **Production ready**: Proper error handling, logging, and monitoring

## Project Status

**Current Version**: v0.1.0 (MVP Complete)
**Next Milestone**: Repository commit and initial testing
**Long-term Goal**: Full context capture and AI-assisted analysis system

**Ready for**:
- ✅ Initial deployment and testing
- ✅ BlackHole setup and configuration
- ✅ Audio capture validation
- ✅ Transcription pipeline testing

**Future Work**:
- 🔄 Local LLM integration
- 🔄 Search and indexing
- 🔄 Note integration pipeline
- 🔄 Advanced analysis features

---

*This file serves as both project memory and development guide for future AI assistance sessions.*