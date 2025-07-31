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

**Purpose**: Centralized system health monitoring and service management for all core TrojanHorse components.

```python
class HealthMonitor:
    def __init__(self, config_path="config.json")
    def start_all_services(self) -> None
    def stop_all_services(self) -> None
    def restart_all_services(self) -> None
    def run_health_check(self) -> Tuple[bool, List[str]]
    def monitor_loop(self) -> None
    def status_report(self) -> None
    def send_notification(self, title: str, message: str) -> None
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

### analytics_engine.py

#### AnalyticsEngine Class

**Purpose**: Performs cross-transcript analysis, entity extraction, and trend calculation.

```python
class AnalyticsEngine:
    def __init__(self, db_path="trojan_search.db")
    def run_full_analysis(self) -> None
    def calculate_trends(self) -> None
```

### internal_api.py

#### FastAPI Application

**Purpose**: Provides a lightweight, local API for quick search access.

```python
# Runs on http://127.0.0.1:5001 by default
@app.get("/search")
def search(query: str) -> Dict
```

### hotkey_client.py

#### HotkeyClient Class

**Purpose**: Listens for a system-wide hotkey to trigger searches via the internal API and display notifications.

```python
class HotkeyClient:
    def __init__(self, config_path="config.json")
    def start_listening(self) -> None
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
python3 health_monitor.py start     # Start all core services
python3 health_monitor.py stop      # Stop all core services
python3 health_monitor.py restart   # Restart all core services
python3 health_monitor.py monitor   # Continuous monitoring
python3 health_monitor.py optimize  # Optimize search database
python3 health_monitor.py analyze   # Run advanced analytics
```

#### audio_capture.py CLI
```bash
python3 audio_capture.py --list-devices     # Show audio devices
```

#### transcribe.py CLI
```bash
python3 transcribe.py                       # Process pending files
python3 transcribe.py /path/to/audio.wav    # Transcribe specific file
```

### Web Interface API Endpoints

#### Search API (`/api/search`)
- **Method**: `POST`
- **Description**: Performs keyword, semantic, or hybrid search on transcripts.
- **Request Body (JSON)**:
  ```json
  {
    "query": "your search query",
    "type": "hybrid", // "keyword", "semantic", or "hybrid"
    "limit": 20,
    "date_from": "YYYY-MM-DD",
    "date_to": "YYYY-MM-DD",
    "classification": "meeting"
  }
  ```
- **Response Body (JSON)**:
  ```json
  {
    "query": "your search query",
    "type": "hybrid",
    "count": 5,
    "results": [
      // Array of search result objects
    ]
  }
  ```

#### Analytics API (`/api/analytics/top_entities`)
- **Method**: `GET`
- **Description**: Retrieves top entities (PERSON, ORG, GPE) from analyzed transcripts.
- **Query Parameters**:
  - `start_date`: (Optional) Start date for analysis (YYYY-MM-DD)
  - `end_date`: (Optional) End date for analysis (YYYY-MM-DD)
- **Response Body (JSON)**:
  ```json
  [
    {
      "entity_text": "John Doe",
      "entity_type": "PERSON",
      "count": 15
    }
  ]
  ```

#### Analytics API (`/api/analytics/trends`)
- **Method**: `GET`
- **Description**: Retrieves trending entities based on recent activity.
- **Response Body (JSON)**:
  ```json
  [
    {
      "entity_text": "Project X",
      "trend_score": 0.75
    }
  ]
  ```

#### Internal Search API (`/search` - used by hotkey client)
- **Method**: `GET`
- **Description**: Lightweight search endpoint for internal use (e.g., by hotkey client).
- **Query Parameters**:
  - `query`: The search query string.
- **Response Body (JSON)**:
  ```json
  {
    "results": [
      // Array of simplified search result objects (snippet, timestamp)
    ]
  }
  ```