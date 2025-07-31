# Advanced Configuration & Customization of TrojanHorse

This guide provides detailed information for users who want to fine-tune their TrojanHorse setup, customize its behavior, and troubleshoot advanced issues.

## `config.json` Deep Dive

The `config.json` file is the central place for all TrojanHorse settings. It's located in the root of your TrojanHorse project directory. Below is a comprehensive breakdown of each section and its parameters.

```json
{
  "audio": {
    "chunk_duration": 300,        // Duration of each audio recording chunk in seconds (e.g., 300s = 5 minutes)
    "sample_rate": 44100,         // Audio sample rate (e.g., 44100 Hz for CD quality)
    "quality": "medium",          // Audio recording quality: "low", "medium", "high"
    "format": "wav",              // Output audio format (currently only WAV is fully supported)
    "device_indices": {
      "microphone": 0,            // The FFmpeg device index for your primary microphone
      "system_audio": 1           // The FFmpeg device index for BlackHole 2ch (for system audio capture)
    }
  },
  "transcription": {
    "engine": "macwhisper",       // Primary transcription engine: "macwhisper", "faster-whisper", or "system"
    "language": "auto",           // Language of the audio: ISO 639-1 code (e.g., "en", "es") or "auto" for auto-detection
    "model_size": "base"          // Size of the transcription model: "tiny", "base", "small", "medium", "large"
  },
  "storage": {
    "temp_path": "/path/to/temp", // Absolute path to a temporary directory for raw audio files before transcription
    "base_path": "/path/to/notes", // Absolute path to the base directory where daily organized notes and transcripts are stored
    "auto_delete_audio": true,    // If true, raw audio files are deleted after successful transcription
    "retention_days": 90          // Number of days to retain transcribed audio and analysis files before automatic cleanup
  },
  "monitoring": {
    "check_interval": 60,         // Frequency (in seconds) at which `health_monitor.py` performs health checks
    "max_restart_attempts": 3,    // Maximum number of times `health_monitor.py` will attempt to restart a failed service
    "restart_delay": 30,          // Delay (in seconds) between service restart attempts
    "health_check_window": 300    // Time window (in seconds) for checking recent activity (e.g., new audio files)
  },
  "analysis": {
    "default_mode": "local",      // Default analysis mode: "local", "cloud", "hybrid", or "prompt"
    "local_model": "qwen3:8b",    // Name of the local LLM model to use with Ollama (e.g., "qwen3:8b")
    "cloud_model": "google/gemini-2.0-flash-001", // Name of the cloud LLM model to use via OpenRouter (e.g., "google/gemini-2.0-flash-001")
    "cost_limit_daily": 0.20,     // Daily cost limit (in USD) for cloud analysis to prevent unexpected bills
    "enable_pii_detection": true, // Enable or disable Personally Identifiable Information (PII) detection
    "hybrid_threshold_words": 1000 // Word count threshold for "hybrid" analysis mode: transcripts longer than this use cloud analysis
  },
  "privacy": {
    "redaction_keywords": []      // A list of keywords (strings) to automatically replace with `[REDACTED]` in transcripts before analysis. Case-insensitive.
  },
  "workflow_integration": {
    "hotkey": "<cmd>+<shift>+c",  // System-wide hotkey combination for quick search (e.g., "<cmd>+<shift>+c", "<ctrl>+<alt>+s")
    "internal_api_port": 5001     // The local port on which the internal API server runs
  }
}
```

## Customizing Analysis Prompts

TrojanHorse uses external text files for the prompts sent to local and cloud LLMs. This allows you to easily customize the type of analysis performed without modifying the code.

*   **`prompts/local_analysis.txt`**: Used for local LLM analysis (e.g., Ollama).
*   **`prompts/gemini_analysis.txt`**: Used for cloud LLM analysis (e.g., Gemini Flash via OpenRouter).

To customize, simply open these `.txt` files in a text editor and modify the instructions. Ensure your prompts are clear and guide the LLM to produce the desired output (e.g., summaries, action items, sentiment analysis).

## Advanced Storage Management

Beyond the basic `temp_path` and `base_path` settings, consider these for long-term data management:

*   **`auto_delete_audio`**: Set to `false` if you wish to retain the original `.wav` audio files after transcription. Be mindful of disk space.
*   **`retention_days`**: Adjust this value to control how long transcribed text and analysis files are kept before `health_monitor.py` automatically cleans them up. Set to `0` to disable automatic cleanup.

## Comprehensive Troubleshooting

This section expands on common issues and provides detailed steps for diagnosis and resolution.

### Service Won't Start or is Unhealthy

1.  **Check dependencies**:
    Ensure all system and Python dependencies are correctly installed. Run `python3 setup.py check`.

2.  **Check service logs**:
    The `health_monitor.py` logs its activity, including service start/stop attempts and errors. Check these logs for clues:
    ```bash
    cat logs/health_monitor.log
    cat logs/audio_capture.err  # For audio capture specific errors
    ```

3.  **Manual service management**:
    You can manually control the services to diagnose issues:
    ```bash
    # Stop all services
    python3 src/health_monitor.py stop
    
    # Start all services
    python3 src/health_monitor.py start
    
    # Restart all services
    python3 src/health_monitor.py restart
    ```

### No Audio Being Captured

1.  **Verify BlackHole setup**:
    -   Ensure "BlackHole + Speakers" (or your custom multi-output device) is selected as your system audio output in `System Settings > Sound > Output`.
    -   Test that you can hear audio normally when this device is selected.
    -   Verify BlackHole appears in your audio device list: `python3 src/audio_capture.py --list-devices`.

2.  **Check device indices**:
    The `audio.device_indices` in `config.json` must match the output from `python3 src/audio_capture.py --list-devices`. Update `config.json` with the correct indices for your microphone and BlackHole.

3.  **Test manual capture**:
    You can test FFmpeg directly to isolate issues:
    ```bash
    # Replace :1 with your BlackHole device index if different
    ffmpeg -f avfoundation -i ":1" -t 30 test_capture.wav
    ```
    If this command fails, your FFmpeg or BlackHole setup might be incorrect.

### Transcription Not Working

1.  **Check transcription engine**:
    Verify your chosen transcription engine is correctly installed and accessible:
    ```bash
    # Test MacWhisper (if installed)
    macwhisper --version
    
    # Test faster-whisper (if installed)
    python3 -c "import faster_whisper; print('OK')"
    
    # Test system whisper (if installed)
    whisper --help
    ```

2.  **Manual transcription test**:
    Try transcribing a known good audio file manually:
    ```bash
    python3 src/transcribe.py /path/to/your/audio.wav
    ```

3.  **Check transcription logs**:
    Transcription logs are stored daily alongside your transcripts. Check for errors:
    ```bash
    cat "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes/$(date +%Y-%m-%d)/transcription.log"
    ```

### Permission Issues

macOS requires explicit permissions for microphone and file system access.

1.  **Reset permissions**:
    If you suspect permission issues, you can reset them and re-trigger the system prompts:
    -   Go to `System Settings > Privacy & Security > Privacy`.
    -   For **Microphone** and **Full Disk Access**, find and remove entries for `Terminal` and `Python`.
    -   Re-run any TrojanHorse script (e.g., `python3 src/health_monitor.py status`) to trigger the permission requests again. Grant them when prompted.

2.  **Check file permissions**:
    Ensure the directories TrojanHorse uses have proper read/write permissions:
    ```bash
    ls -la "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/"
    ```

### Storage Issues

1.  **Check disk space**:
    ```bash
    df -h "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/"
    ```

2.  **Clean up old files**:
    You can manually remove files older than a certain number of days:
    ```bash
    # Example: Remove files older than 30 days in your base_path
    find "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes" -type f -mtime +30 -delete
    ```

3.  **Adjust retention policy**:
    Modify `config.json` to change how long files are kept automatically:
    ```json
    {
      "storage": {
        "auto_delete_audio": true,
        "retention_days": 30 // Change this value
      }
    }
    ```

### Search & Web Interface Issues

1.  **Check web interface logs**:
    Run the web interface with verbose logging to see detailed errors:
    ```bash
    python3 src/web_interface.py --database trojan_search.db --port 5000 --verbose
    ```

2.  **Rebuild search database**:
    If your search results are incorrect or missing, you can rebuild the entire search database. **WARNING: This will delete all existing search data and analysis, and re-index everything from your raw transcripts.**
    ```bash
    rm trojan_search.db
    python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db
    ```

### Performance Issues

1.  **Check disk space**:
    Low disk space can severely impact performance.
    ```bash
    df -h
    ```

2.  **Check memory usage**:
    Large language models can consume significant RAM.
    ```bash
    top -l 1 | grep -E "(PhysMem|Processes)"
    ```

3.  **Monitor system resources**:
    Use the built-in monitor to track resource usage over time:
    ```bash
    python3 src/health_monitor.py monitor
    ```

4.  **Optimize database**:
    Regularly optimize the SQLite database to improve search performance:
    ```bash
    python3 src/health_monitor.py optimize
    ```

## Advanced Configuration

### Custom Storage Locations

You can change the default paths for temporary audio and final notes in `config.json`:

```json
{
  "storage": {
    "temp_path": "/tmp/trojan_audio",
    "base_path": "/Users/username/Documents/Context"
  }
}
```

### Multiple Audio Sources (Advanced)

For capturing from multiple microphones or specific audio devices, you can configure `audio.device_indices` with more detail. Refer to FFmpeg documentation for advanced device mapping.

```json
{
  "audio": {
    "device_indices": {
      "microphone_1": 0,
      "microphone_2": 2,
      "system_audio": 1
    }
  }
}
```

### Performance Tuning (Advanced)

While TrojanHorse is optimized for low resource usage, you can experiment with these settings in `config.json`:

```json
{
  "audio": {
    "quality": "low",            // Lower quality reduces file size and processing load
    "sample_rate": 16000          // Lower sample rate reduces file size
  },
  "transcription": {
    "model_size": "tiny"          // Smaller models transcribe faster but with less accuracy
  },
  "analysis": {
    "default_mode": "local"       // Prioritize local analysis to avoid cloud costs and network latency
  }
}
```

## Maintenance

### Regular Tasks

1.  **Check system health** (weekly):
    ```bash
    python3 src/health_monitor.py status
    ```

2.  **Review logs** (monthly):
    ```bash
    ls -la logs/
    # Clean up old logs
    find logs/ -name "*.log" -mtime +30 -delete
    ```

3.  **Update transcription models** (as needed):
    If you use `faster-whisper`, you might need to update its models periodically:
    ```bash
    python3 -c "from faster_whisper import WhisperModel; WhisperModel('base')"
    ```

### Backup Strategy

Regularly back up your `base_path` directory (e.g., `~/Meeting Notes/`) and `trojan_search.db`.

1.  **Configuration backup**:
    ```bash
    cp config.json config.json.backup
    ```

2.  **Automated backup script example**:
    ```bash
    #!/bin/bash
    DATE=$(date +%Y%m%d)
    tar -czf "context_backup_$DATE.tar.gz" \
      "/Users/$(whoami)/Library/Mobile Documents/com~apple~CloudDocs/Work Automation/Meeting Notes" \
      "/path/to/trojan_search.db"
    ```

### Updates and Upgrades

To update TrojanHorse to the latest version:

1.  **Pull from repository**:
    ```bash
    git pull origin main
    ```

2.  **Reinstall dependencies and service**:
    ```bash
    pip3 install -r requirements.txt
    python3 -m spacy download en_core_web_sm
    python3 setup.py install
    ```

## Security & Privacy Considerations

### Data Protection
-   Audio files are automatically deleted after transcription (configurable).
-   Transcripts contain only text, no audio data.
-   All processing happens locally by default.
-   Optional encryption for sensitive content (future consideration).

### Access Control
-   Service runs with user privileges only.
-   File permissions restrict access to user account.
-   The internal API (`internal_api.py`) runs locally and is not exposed to the internet by default.
-   Logs are sanitized to remove sensitive information (via `privacy.redaction_keywords`).

### Privacy Best Practices
-   **Review transcripts** before any cloud processing if `privacy.redaction_keywords` is not comprehensive enough.
-   **Use local transcription engines** when possible to keep all data on your device.
-   **Implement data retention policies** appropriate for your needs via `storage.retention_days`.
-   Consider **encrypting your storage volume** for highly sensitive environments.
-   Regularly **review your `privacy.redaction_keywords`** list to ensure it covers all sensitive terms.
