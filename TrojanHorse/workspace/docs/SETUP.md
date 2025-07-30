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

### Optional Dependencies

#### MacWhisper Pro (Recommended)
1. Purchase and download from Mac App Store
2. Install the CLI component from the app's preferences
3. Verify installation: `macwhisper --version`

#### faster-whisper (Fallback Transcription)
```bash
pip3 install faster-whisper
```

#### System Whisper (Last Resort)
```bash
pip3 install openai-whisper
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

### 2. Run Setup Script
```bash
python3 setup.py install
```

The setup script will:
- Check for required dependencies
- Create necessary directory structure
- Generate default configuration
- Install and start the macOS service
- Set up logging directories

### 3. Configure Audio Devices

Edit `config.json` to match your audio setup:

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
  }
}
```

Update the `device_indices` based on your `--list-devices` output.

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
Service Status: ✓ running
Recent Audio Files: ✓ found_1_recent_files
Disk Space: ✓ disk_space_ok_45.2GB
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

## Configuration Options

### config.json Structure

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

### Service Won't Start

1. **Check dependencies**:
   ```bash
   python3 setup.py check
   ```

2. **Check service logs**:
   ```bash
   cat logs/audio_capture.err
   ```

3. **Manual service management**:
   ```bash
   # Unload service
   launchctl unload ~/Library/LaunchAgents/com.contextcapture.audio.plist
   
   # Reload service
   launchctl load ~/Library/LaunchAgents/com.contextcapture.audio.plist
   ```

### No Audio Being Captured

1. **Verify BlackHole setup**:
   - Check that "BlackHole + Speakers" is selected as system output
   - Test that you can hear audio normally
   - Verify BlackHole appears in audio device list

2. **Check device indices**:
   ```bash
   python3 audio_capture.py --list-devices
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
   python3 transcribe.py /path/to/test.wav
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