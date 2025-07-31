# Detailed Setup Guide

This guide provides step-by-step instructions for setting up the TrojanHorse Context Capture System on macOS.

## Prerequisites

### System Requirements
- **macOS**: 10.14 (Mojave) or later
- **Python**: 3.7 or later (system Python is fine)
- **Disk Space**: At least 5GB free (more recommended for extended use)
- **Audio**: Microphone access permissions required

### Required Software

#### 1. Install Homebrew (if not already installed)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 2. Install FFmpeg
```bash
brew install ffmpeg
```

#### 3. Install BlackHole (Audio Routing)
1. Download from: https://existential.audio/blackhole/
2. Run the installer package
3. Restart your computer (required for audio driver installation)

#### 4. Install Python Dependencies
```bash
pip3 install -r requirements.txt
```

#### 5. Download spaCy Language Model
This is required for Advanced Analytics.
```bash
python3 -m spacy download en_core_web_sm
```

## Audio Setup

### BlackHole Configuration

BlackHole creates a virtual audio device that allows capture of system audio. You need to configure it properly:

#### 1. Create Multi-Output Device
1. Open **Audio MIDI Setup** (Applications > Utilities)
2. Click the **+** button and select "Create Multi-Output Device"
3. Name it "BlackHole + Speakers"
4. Check both your speakers/headphones AND BlackHole 2ch
5. Set your speakers as the "Master Device"
6. Set drift correction for BlackHole

#### 2. Set System Audio Output
1. Go to **System Preferences > Sound > Output**
2. Select "BlackHole + Speakers" as your output device
3. Test that you can still hear audio normally

#### 3. Configure Audio Input (for applications)
Applications that need to capture system audio should use "BlackHole 2ch" as input.

### Device Index Discovery

Find your audio device indices for configuration:

```bash
# Run this in your project directory
python3 audio_capture.py --list-devices
```

This will show output like:
```
[0] Built-in Microphone
[1] BlackHole 2ch
[2] AirPods Pro
```

Note the indices for your preferred microphone and BlackHole.

## Installation

### 1. Clone Repository
```bash
cd "/Users/$(whoami)/Documents"  # or your preferred location
git clone https://github.com/Khamel83/TrojanHorse.git
cd TrojanHorse
```

### 2. Install TrojanHorse Service
The `health_monitor.py` script now manages all core services (audio capture, internal API, hotkey client). This step sets up `health_monitor.py` as a `launchd` service.

```bash
python3 setup.py install
```

### 3. Configure Audio Devices and Other Settings

Edit `config.json` to match your audio setup and other preferences. This file now includes sections for `privacy` and `workflow_integration`.

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
    "model_size": "base"
  },
  "storage": {
    "auto_delete_audio": true,
    "base_path": "/Users/YOUR_USERNAME/Documents/Meeting Notes"
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

Update the `device_indices` based on your `--list-devices` output. Replace `YOUR_USERNAME` with your actual username, and update paths as needed. Ensure `openrouter_api_key` is set if you plan to use cloud analysis.

### 4. Grant Permissions

#### Microphone Access
1. Go to **System Preferences > Security & Privacy > Privacy**
2. Click on **Microphone**
3. Add and enable **Terminal** and **Python** if prompted
4. You may need to run the application once to trigger the permission request

#### File System Access
The system needs access to your cloud documents folder:
1. Go to **System Preferences > Security & Privacy > Privacy**
2. Click on **Full Disk Access**
3. Add **Terminal** and **Python** if the system requests it

## Verification

### 1. Check System Status
```bash
python3 health_monitor.py status
```

Expected output:
```
Context Capture System Status Report
====================================
Service 'audio_capture': ✓ running
Service 'internal_api': ✓ running
Service 'hotkey_client': ✓ running
Recent Audio Files: ✓ found_1_recent_files
Disk Space: ✓ disk_space_ok_45.2GB
Analysis Capabilities: ✓ both_local_and_cloud_available
Analysis Activity: ✓ found_1_recent_analyses
Overall Health: ✓ Healthy
```

### 2. Test Audio Capture
```bash
# Monitor logs in real-time
tail -f logs/audio_capture.out

# In another terminal, check for new files
ls -la "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/MacProAudio"
```

You should see new WAV files appearing every 5 minutes when audio is being captured.

### 3. Test Transcription
```bash
# Wait for an audio file to be created, then check transcription
ls -la "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes/$(date +%Y-%m-%d)/transcribed_audio/"
```

You should see corresponding `.txt` files with transcribed content.

### 4. Test Web Interface
```bash
# Open in browser
open "http://127.0.0.1:5000"

# Test search functionality via API
curl -X POST -H "Content-Type: application/json" -d '{"query": "test", "type": "hybrid"}' http://127.0.0.1:5000/api/search

# Test analytics dashboard
open "http://127.0.0.1:5000/dashboard"
```

### 5. Test Workflow Integration (Hotkey Client)
1.  Ensure `health_monitor.py` is running (e.g., `python3 src/health_monitor.py monitor &`).
2.  Copy some text to your clipboard (e.g., from a web page or document).
3.  Press the configured hotkey (default: `Cmd+Shift+C`).
4.  You should see a macOS notification with a search result snippet from your transcripts.

## Configuration Options

### `config.json` Structure

```json
{
  "audio": {
    "chunk_duration": 300,        // 5 minutes in seconds
    "sample_rate": 44100,         // CD quality
    "quality": "medium",          // low, medium, high
    "format": "wav",              // Output format
    "device_indices": {
      "microphone": 0,            // Your mic device index
      "system_audio": 1           // BlackHole device index
    }
  },
  "transcription": {
    "engine": "macwhisper",       // macwhisper, faster-whisper, system
    "language": "auto",           // ISO language code or "auto"
    "model_size": "base"          // tiny, base, small, medium, large
  },
  "storage": {
    "temp_path": "/path/to/temp", // Temporary audio storage
    "base_path": "/path/to/notes", // Daily organized storage
    "auto_delete_audio": true,    // Delete WAV after transcription
    "retention_days": 90          // Keep data for 90 days
  },
  "monitoring": {
    "check_interval": 60,         // Health check frequency (seconds)
    "max_restart_attempts": 3,    // Service restart attempts
    "restart_delay": 30,          // Delay between restart attempts
    "health_check_window": 300    // Recent activity window (seconds)
  },
  "analysis": {
    "default_mode": "local",      // local, cloud, hybrid, prompt
    "local_model": "qwen3:8b",    // Ollama model name
    "cloud_model": "google/gemini-2.0-flash-001", // OpenRouter model name
    "cost_limit_daily": 0.20,     // Daily cost limit for cloud analysis
    "enable_pii_detection": true, // Enable PII detection
    "hybrid_threshold_words": 1000 // Word count threshold for hybrid mode
  },
  "privacy": {
    "redaction_keywords": []      // List of keywords to redact from analysis
  },
  "workflow_integration": {
    "hotkey": "<cmd>+<shift>+c",  // System-wide hotkey for quick search
    "internal_api_port": 5001     // Port for the internal API server
  }
}
```

### Common Configuration Changes

#### Change Audio Quality
```json
{
  "audio": {
    "quality": "high",            // Better quality, larger files
    "sample_rate": 48000          // Higher sample rate
  }
}
```

#### Adjust Chunk Duration
```json
{
  "audio": {
    "chunk_duration": 600         // 10-minute chunks instead of 5
  }
}
```

#### Configure Transcription Engine
```json
{
  "transcription": {
    "engine": "faster-whisper",   // Use local transcription
    "model_size": "medium",       // Better accuracy
    "language": "en"              // Force English
  }
}
```

## Troubleshooting

### Service Won't Start or is Unhealthy

1. **Check dependencies**:
   ```bash
   python3 setup.py check
   ```

2. **Check service logs**:
   ```bash
   cat logs/health_monitor.log
   cat logs/audio_capture.err
   ```

3. **Manual service management**:
   ```bash
   # Stop all services
   python3 src/health_monitor.py stop
   
   # Start all services
   python3 src/health_monitor.py start
   
   # Restart all services
   python3 src/health_monitor.py restart
   ```

### No Audio Being Captured

1. **Verify BlackHole setup**:
   - Check that "BlackHole + Speakers" is selected as system output
   - Test that you can hear audio normally
   - Verify BlackHole appears in audio device list

2. **Check device indices**:
   ```bash
   python3 src/audio_capture.py --list-devices
   ```
   Update `config.json` with correct indices.

3. **Test manual capture**:
   ```bash
   # Test 30-second capture
   ffmpeg -f avfoundation -i ":1" -t 30 test_capture.wav
   ```

### Transcription Not Working

1. **Check transcription engine**:
   ```bash
   # Test MacWhisper
   macwhisper --version
   
   # Test faster-whisper
   python3 -c "import faster_whisper; print('OK')"
   
   # Test system whisper
   whisper --help
   ```

2. **Manual transcription test**:
   ```bash
   python3 src/transcribe.py /path/to/test.wav
   ```

3. **Check transcription logs**:
   ```bash
   cat "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes/$(date +%Y-%m-%d)/transcription.log"
   ```

### Permission Issues

1. **Reset permissions**:
   - Go to System Preferences > Security & Privacy > Privacy
   - Remove Python/Terminal from Microphone and Full Disk Access
   - Re-run the application to trigger permission requests

2. **Check file permissions**:
   ```bash
   ls -la "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/"
   ```

### Storage Issues

1. **Check disk space**:
   ```bash
   df -h "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/"
   ```

2. **Clean up old files**:
   ```bash
   # Remove files older than 30 days
   find "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes" -type f -mtime +30 -delete
   ```

3. **Adjust retention policy**:
   ```json
   {
     "storage": {
       "auto_delete_audio": true,
       "retention_days": 30
     }
   }
   ```

### Search & Web Interface Issues

1. **Check web interface logs**:
   ```bash
   python3 src/web_interface.py --database trojan_search.db --port 5000 --verbose
   ```

2. **Rebuild search database** (WARNING: This will delete existing search data):
   ```bash
   rm trojan_search.db
   python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db
   ```

### Performance Issues

1. **Check disk space**:
   ```bash
   df -h
   ```

2. **Check memory usage**:
   ```bash
   top -l 1 | grep -E "(PhysMem|Processes)"
   ```

3. **Monitor system resources**:
   ```bash
   python3 src/health_monitor.py monitor
   ```

4. **Optimize database**:
   ```bash
   python3 src/health_monitor.py optimize
   ```

## Advanced Configuration

### Custom Storage Locations

```json
{
  "storage": {
    "temp_path": "/tmp/trojan_audio",
    "base_path": "/Users/username/Documents/Context",
    "backup_path": "/Volumes/External/ContextBackup"
  }
}
```

### Multiple Audio Sources

For capturing from multiple microphones:

```json
{
  "audio": {
    "devices": [
      {"type": "microphone", "index": 0, "weight": 1.0},
      {"type": "microphone", "index": 2, "weight": 0.5},
      {"type": "system", "index": 1, "weight": 1.0}
    ]
  }
}
```

### Performance Tuning

```json
{
  "performance": {
    "process_priority": "low",
    "io_priority": "low",
    "max_concurrent_transcriptions": 2,
    "chunk_buffer_size": 3
  }
}
```

## Maintenance

### Regular Tasks

1. **Check system health** (weekly):
   ```bash
   python3 health_monitor.py status
   ```

2. **Review logs** (monthly):
   ```bash
   ls -la logs/
   # Clean up old logs
   find logs/ -name "*.log" -mtime +30 -delete
   ```

3. **Update transcription models** (as needed):
   ```bash
   # Update faster-whisper models
   python3 -c "from faster_whisper import WhisperModel; WhisperModel('base')"
   ```

### Backup Strategy

1. **Configuration backup**:
   ```bash
   cp config.json config.json.backup
   ```

2. **Automated backup script**:
   ```bash
   #!/bin/bash
   DATE=$(date +%Y%m%d)
   tar -czf "context_backup_$DATE.tar.gz" \
     "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes"
   ```

### Updates and Upgrades

1. **Update from repository**:
   ```bash
   git pull origin main
   python3 setup.py install  # Reinstall with updates
   ```

2. **Update dependencies**:
   ```bash
   brew upgrade ffmpeg
   pip3 install --upgrade faster-whisper
   ```

## Security Considerations

### Data Protection
- Audio files are automatically deleted after transcription
- Transcripts contain only text, no audio data
- All processing happens locally by default
- Optional encryption for sensitive content

### Access Control
- Service runs with user privileges only
- File permissions restrict access to user account
- No network services exposed by default
- Logs sanitized to remove sensitive information

### Privacy Best Practices
- Review transcripts before any cloud processing
- Use local transcription engines when possible
- Implement data retention policies appropriate for your needs
- Consider encrypting storage for highly sensitive environments