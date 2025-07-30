# API Reference

This document provides detailed API documentation for all TrojanHorse modules and their interfaces.

## Module Interfaces

### audio_capture.py

#### AudioCapture Class

**Purpose**: Continuous audio recording with FFmpeg backend

```python
class AudioCapture:
    def __init__(self, config_path="config.json")
    def start_capture(self) -> None
    def stop_capture(self) -> None  
    def capture_chunk(self) -> None
    def get_audio_devices(self) -> str
    def move_to_daily_folder(self, temp_file: Path) -> None
    def trigger_transcription(self, audio_file: Path) -> None
```

**Configuration Schema**:
```json
{
  "audio": {
    "chunk_duration": 300,
    "sample_rate": 44100,
    "quality": "medium",
    "format": "wav"
  },
  "storage": {
    "temp_path": "/path/to/temp",
    "base_path": "/path/to/meeting/notes"
  }
}
```

**File Outputs**:
- WAV files: `audio_YYYYMMDD_HHMMSS.wav`
- Logs: `capture.log` in daily folder
- Status: Process exit codes (0=success, 1=error)

### transcribe.py

#### AudioTranscriber Class

**Purpose**: Multi-engine audio transcription pipeline

```python
class AudioTranscriber:
    def __init__(self, config_path="config.json")
    def transcribe_file(self, audio_file: str) -> Optional[Path]
    def transcribe_with_macwhisper(self, audio_file: Path) -> Optional[Path]
    def transcribe_with_faster_whisper(self, audio_file: Path) -> Optional[Path]
    def transcribe_with_system_whisper(self, audio_file: Path) -> Optional[Path]
    def post_process_transcript(self, transcript_file: Path) -> None
    def process_pending_files(self) -> None
```

**Engine Priority**: MacWhisper → faster-whisper → system whisper

**Configuration Schema**:
```json
{
  "transcription": {
    "engine": "macwhisper",
    "language": "auto",
    "model_size": "base"
  },
  "storage": {
    "auto_delete_audio": true
  }
}
```

**File Outputs**:
- Text files: `audio_YYYYMMDD_HHMMSS.txt`
- Format: Timestamped transcripts with metadata headers
- Logs: `transcription.log` in daily folder

### health_monitor.py

#### HealthMonitor Class

**Purpose**: System health monitoring and service management

```python
class HealthMonitor:
    def __init__(self, config_path="config.json")
    def check_service_status(self) -> Tuple[bool, str]
    def check_audio_files_recent(self) -> Tuple[bool, str]  
    def check_disk_space(self) -> Tuple[bool, str]
    def restart_service(self) -> bool
    def run_health_check(self) -> Tuple[bool, List[str]]
    def monitor_loop(self) -> None
    def status_report(self) -> None
    def send_notification(self, title: str, message: str) -> None
```

**Health Check Returns**:
```python
# Tuple format: (success: bool, status_message: str)
# Examples:
(True, "running")
(False, "not_loaded")
(True, "found_3_recent_files")
(False, "low_disk_space_0.8GB")
```

**Configuration Schema**:
```json
{
  "monitoring": {
    "check_interval": 60,
    "max_restart_attempts": 3,
    "restart_delay": 30,
    "health_check_window": 300
  }
}
```

### setup.py

#### Setup Functions

**Purpose**: System installation and management

```python
def create_folder_structure() -> bool
def install_service() -> bool
def uninstall_service() -> bool
def check_dependencies() -> bool
def create_default_config() -> bool
```

**Command Line Interface**:
```bash
python3 setup.py install    # Full system installation
python3 setup.py uninstall  # Remove service and config
python3 setup.py check      # Verify dependencies and status
```

**Directory Structure Created**:
```
Meeting Notes/
├── YYYY-MM-DD/
│   ├── notes/
│   ├── transcribed_audio/
│   ├── files/
│   └── log.json
MacProAudio/                # Temporary storage
logs/                       # System logs
```

## Configuration Management

### Configuration File (config.json)

**Full Schema**:
```json
{
  "audio": {
    "chunk_duration": 300,
    "sample_rate": 44100,
    "quality": "medium",
    "format": "wav",
    "device_indices": {
      "microphone": 0,
      "system_audio": 1
    }
  },
  "transcription": {
    "engine": "macwhisper",
    "language": "auto",
    "model_size": "base",
    "fallback_engines": ["faster-whisper", "system"]
  },
  "storage": {
    "temp_path": "/path/to/temp/audio",
    "base_path": "/path/to/meeting/notes",
    "auto_delete_audio": true,
    "retention_days": 90
  },
  "monitoring": {
    "check_interval": 60,
    "max_restart_attempts": 3,
    "restart_delay": 30,
    "health_check_window": 300,
    "notification_enabled": true
  },
  "logging": {
    "level": "INFO",
    "max_file_size": "10MB",
    "backup_count": 5,
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  }
}
```

### Configuration Validation

```python
def validate_config(config: dict) -> Tuple[bool, List[str]]:
    """
    Validates configuration file structure and values
    
    Returns:
        Tuple[bool, List[str]]: (is_valid, error_messages)
    """
```

## File Formats

### Daily Log Format (log.json)

```json
{
  "date": "2025-07-30",
  "events": [
    {
      "timestamp": "2025-07-30T14:05:32Z",
      "type": "audio_capture_started",
      "module": "capture.audio",
      "details": {
        "chunk_duration": 300,
        "output_file": "audio_20250730_140532.wav"
      }
    },
    {
      "timestamp": "2025-07-30T14:10:32Z", 
      "type": "transcription_completed",
      "module": "transcribe.whisper",
      "details": {
        "input_file": "audio_20250730_140532.wav",
        "output_file": "audio_20250730_140532.txt",
        "engine": "macwhisper",
        "duration": 300.5,
        "success": true
      }
    }
  ],
  "summary": {
    "audio_chunks_captured": 12,
    "transcriptions_completed": 11,
    "transcription_success_rate": 0.91,
    "total_audio_duration": 3605.2,
    "storage_used_mb": 145.3
  }
}
```

### Transcript Format

```
Transcription of audio_20250730_140532
Generated: 2025-07-30 14:12:45
Engine: macwhisper
Language: en (confidence: 0.95)
Duration: 300.50s
--------------------------------------------------

[0.00s -> 15.32s] Good morning everyone, let's start with the project update from last week.

[15.32s -> 28.91s] The audio capture system is working well, we've processed about 12 hours of content so far.

[28.91s -> 45.67s] I think we should focus on the transcription accuracy next, maybe try the medium model instead of base.
```

## Error Handling

### Standard Error Codes

```python
class TrojanHorseError(Exception):
    """Base exception for TrojanHorse system"""
    pass

class AudioCaptureError(TrojanHorseError):
    """Audio capture related errors"""
    pass

class TranscriptionError(TrojanHorseError):
    """Transcription processing errors"""
    pass

class ConfigurationError(TrojanHorseError):
    """Configuration validation errors"""
    pass

class ServiceError(TrojanHorseError):
    """System service management errors"""
    pass
```

### Error Response Format

```json
{
  "error": {
    "type": "TranscriptionError",
    "message": "All transcription engines failed",
    "details": {
      "file": "audio_20250730_140532.wav",
      "engines_tried": ["macwhisper", "faster-whisper", "system"],
      "last_error": "faster-whisper not available"
    },
    "timestamp": "2025-07-30T14:15:32Z"
  }
}
```

## Integration APIs

### Command Line Interface

#### health_monitor.py CLI
```bash
python3 health_monitor.py status    # System status report
python3 health_monitor.py check     # Boolean health check
python3 health_monitor.py restart   # Restart services
python3 health_monitor.py monitor   # Continuous monitoring
```

#### audio_capture.py CLI
```bash
python3 audio_capture.py                    # Start capture
python3 audio_capture.py --list-devices     # Show audio devices
```

#### transcribe.py CLI
```bash
python3 transcribe.py                       # Process pending files
python3 transcribe.py /path/to/audio.wav    # Transcribe specific file
```

### macOS LaunchAgent Integration

**Service Management**:
```bash
# Load service
launchctl load ~/Library/LaunchAgents/com.contextcapture.audio.plist

# Unload service  
launchctl unload ~/Library/LaunchAgents/com.contextcapture.audio.plist

# Check service status
launchctl list com.contextcapture.audio

# View service logs
tail -f ~/Library/Logs/com.contextcapture.audio.out
```

**Service Configuration Properties**:
- **Label**: `com.contextcapture.audio`
- **Auto-start**: `RunAtLoad = true`
- **Keep alive**: Restart on crashes
- **Process type**: Background
- **I/O priority**: Low (system-friendly)

## Future API Extensions

### Planned v0.2.0 APIs

#### Local LLM Integration
```python
class LLMProcessor:
    def __init__(self, ollama_endpoint="http://localhost:11434")
    def classify_content(self, transcript: str) -> dict
    def extract_tasks(self, transcript: str) -> List[str]
    def sanitize_for_api(self, transcript: str) -> str
    def generate_summary(self, transcripts: List[str]) -> str
```

#### Search and Indexing
```python
class ContentIndex:
    def __init__(self, db_path="context.db")
    def index_transcript(self, transcript_file: Path) -> None
    def search_content(self, query: str) -> List[dict]
    def get_related_content(self, date: str) -> List[dict]
    def export_timerange(self, start: str, end: str) -> dict
```

#### Note Integration
```python
class NoteProcessor:
    def __init__(self, capacities_path: str)
    def import_capacities_notes(self, date: str) -> None
    def merge_audio_notes(self, date: str) -> None
    def export_daily_summary(self, date: str) -> str
    def create_obsidian_links(self, transcript: str) -> str
```

### Webhook Support (Planned)

```python
# POST /api/v1/webhook/transcription_complete
{
  "event": "transcription_complete",
  "data": {
    "file": "audio_20250730_140532.txt",
    "duration": 300.5,
    "word_count": 1247,
    "confidence": 0.91
  },
  "timestamp": "2025-07-30T14:12:45Z"
}
```

## Development APIs

### Module Testing

```python
# Test audio capture
from audio_capture import AudioCapture
capture = AudioCapture()
devices = capture.get_audio_devices()

# Test transcription
from transcribe import AudioTranscriber
transcriber = AudioTranscriber()
result = transcriber.transcribe_file("test.wav")

# Test health monitoring
from health_monitor import HealthMonitor
monitor = HealthMonitor()
status, issues = monitor.run_health_check()
```

### Custom Module Development

```python
class CustomModule:
    """Template for extending TrojanHorse functionality"""
    
    def __init__(self, config_path="config.json"):
        self.config = self.load_config(config_path)
        self.setup_logging()
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration with defaults"""
        pass
    
    def setup_logging(self) -> None:
        """Configure logging to daily folder"""
        pass
    
    def process(self, input_data: Any) -> Any:
        """Main processing function"""
        pass
```

This API reference provides the complete interface specification for the current MVP and planned future extensions.