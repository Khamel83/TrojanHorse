# TrojanHorse - Complete Machine Setup Guide

This guide will walk you through setting up TrojanHorse from scratch on a new macOS machine.

## 🎯 Overview

TrojanHorse is a complete audio capture, transcription, and analysis system that runs continuously in the background. This setup guide covers:

1. **System Prerequisites** - Required software and dependencies
2. **Audio Setup** - BlackHole for system audio capture + microphone configuration
3. **TrojanHorse Installation** - Core system setup and configuration
4. **AI/ML Setup** - Local and cloud analysis engines
5. **Search System** - Phase 3 search and web interface
6. **Service Configuration** - Running as a macOS service
7. **Verification & Testing** - Ensuring everything works correctly

## 📋 Prerequisites

### System Requirements
- **macOS 10.15+** (Catalina or later)
- **8GB+ RAM** (16GB recommended for ML models)
- **20GB+ free disk space**
- **Administrator privileges**
- **Active internet connection** (initial setup only)

### Required Software
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install core dependencies
brew install ffmpeg python3 git curl

# Install Python dependencies
pip3 install --user -r requirements.txt

# Download spaCy language model (required for Advanced Analytics)
python3 -m spacy download en_core_web_sm
```

## 🔊 Step 1: Audio System Setup

### Install BlackHole
BlackHole creates a virtual audio driver for capturing system audio:

1. **Download BlackHole**:
   ```bash
   # Option 1: Direct download
   open https://existential.audio/blackhole/
   # Download "BlackHole 2ch" installer
   
   # Option 2: Via Homebrew
   brew install --cask blackhole-2ch
   ```

2. **Install BlackHole**:
   - Run the downloaded installer
   - Follow the installation wizard
   - **Restart your Mac** after installation
   - Grant any security permissions if prompted

### Configure Audio Routing

3. **Open Audio MIDI Setup**:
   ```bash
   open "/Applications/Utilities/Audio MIDI Setup.app"
   ```

4. **Create Multi-Output Device**:
   - Click the "+" button → "Create Multi-Output Device"
   - Name it "TrojanHorse Output"
   - Check both:
     - ✅ **Built-in Output** (your speakers/headphones)
     - ✅ **BlackHole 2ch**
   - Set **Built-in Output** as Master Device
   - Close Audio MIDI Setup

5. **Set System Audio Output**:
   - Go to **System Preferences** → **Sound** → **Output**
   - Select **"TrojanHorse Output"**
   - Test that you can still hear system audio normally

### Verify Audio Setup
```bash
# List available audio devices
python3 -c "
import subprocess
result = subprocess.run(['ffmpeg', '-f', 'avfoundation', '-list_devices', 'true', '-i', ''], 
                       capture_output=True, text=True)
print('AUDIO DEVICES:')
print(result.stderr)
"
```

You should see both your microphone and BlackHole listed as input devices.

## 🚀 Step 2: TrojanHorse Installation

### Clone and Setup Repository
```bash
# Choose your preferred location
cd ~/Documents  # or wherever you want the project

# Clone the repository
git clone https://github.com/Khamel83/TrojanHorse.git
cd TrojanHorse

# Install Python dependencies
pip3 install --user -r requirements.txt
```

### Create Configuration
```bash
# Copy template configuration
cp config.template.json config.json

# Edit configuration (see below for details)
nano config.json  # or use your preferred editor
```

### Configuration Setup
Edit `config.json` with your specific settings:

```json
{
  "audio": {
    "chunk_duration": 300,
    "sample_rate": 44100,
    "quality": "medium",
    "format": "wav",
    "input_device": "BlackHole 2ch",
    "microphone_device": "Built-in Microphone"
  },
  "storage": {
    "temp_path": "~/TrojanHorse/temp",
    "base_path": "~/TrojanHorse/notes",
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

**Important**: Replace `YOUR_USERNAME` with your actual username, and update paths as needed. Ensure `openrouter_api_key` is set if you plan to use cloud analysis. The `privacy` and `workflow_integration` sections are new and provide enhanced control and functionality.

## 🧠 Step 3: AI/ML Setup

### Local AI with Ollama
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve &

# Install recommended model (this will take a few minutes)
ollama pull qwen2.5:7b

# Test local AI
ollama run qwen2.5:7b "Hello, can you analyze meeting transcripts?"
```

### Cloud AI Setup (Optional)
1. **Get OpenRouter API Key**:
   - Visit https://openrouter.ai/
   - Sign up for an account
   - Generate an API key
   - Add $5-10 credit for testing

2. **Update Configuration**:
   ```bash
   # Edit config.json and add your API key
   nano config.json
   # Update the "openrouter_api_key" field
   ```

### Install Transcription Engine

TrojanHorse supports multiple transcription engines. Choose one or more:

*   **Option 1: MacWhisper (Recommended for macOS)**
    *   Download from Mac App Store: [https://apps.apple.com/app/macwhisper/id1458140153](https://apps.apple.com/app/macwhisper/id1458140153)
    *   If you have `mas-cli` installed: `mas install 1458140153`

*   **Option 2: Faster-Whisper (Open Source Alternative)**
    *   Install via pip: `pip3 install --user faster-whisper`

*   **Option 3: OpenAI Whisper (CLI)**
    *   Install via pip: `pip3 install --user openai-whisper`

**Test Transcription:**
```bash
python3 src/transcribe.py
```
This command will process any pending audio files in your `temp` directory. Check the `Meeting Notes` folder for `.txt` files.

## 🔍 Step 4: Search System Setup

### Initialize Search Database
```bash
# Create search database and index existing transcripts
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db --verbose

# Generate semantic embeddings (this may take a few minutes)
python3 -c "
from src.semantic_search import SemanticSearch
s = SemanticSearch('trojan_search.db')
stats = s.batch_generate_embeddings()
print(f'Generated embeddings: {stats}')
s.close()
"
```

### Test Web Interface
```bash
# Start web interface
python3 src/web_interface.py --database trojan_search.db --port 5000 --verbose

# In another terminal, test the interface
curl "http://127.0.0.1:5000/api/stats"

# Open in browser
open "http://127.0.0.1:5000"
```

## 🔧 Step 5: Service Configuration

TrojanHorse now uses `health_monitor.py` to manage all its core services (audio capture, internal API, hotkey client).

### Install as macOS Service
```bash
# Install the system service (this sets up a launchd plist for health_monitor.py)
python3 src/setup.py install

# Verify installation
python3 src/health_monitor.py status
```

### Configure Auto-Start
```bash
# Enable the health_monitor service to start automatically on login
launchctl load ~/Library/LaunchAgents/com.contextcapture.audio.plist

# Verify service is running
python3 src/health_monitor.py status
```

### Set Up Health Monitoring
```bash
# Test health monitoring
python3 src/health_monitor.py check

# Start continuous monitoring loop (optional, runs in background)
python3 src/health_monitor.py monitor &

# Add aliases to your shell profile (.zshrc, .bash_profile) for convenience:
echo 'alias trojan-status="python3 ~/Documents/TrojanHorse/src/health_monitor.py status"' >> ~/.zshrc
echo 'alias trojan-start="python3 ~/Documents/TrojanHorse/src/health_monitor.py start"' >> ~/.zshrc
echo 'alias trojan-stop="python3 ~/Documents/TrojanHorse/src/health_monitor.py stop"' >> ~/.zshrc
echo 'alias trojan-restart="python3 ~/Documents/TrojanHorse/src/health_monitor.py restart"' >> ~/.zshrc
```

## ✅ Step 6: Verification & Testing

After completing the setup, verify that all components of TrojanHorse are functioning correctly.

### Overall System Status
```bash
python3 src/health_monitor.py status
```
This should show all services (audio_capture, internal_api, hotkey_client) as running.

### Audio Capture Test
```bash
# Audio capture runs continuously in the background once health_monitor is started.
# Check for recent audio files in your temp directory:
ls -la ~/TrojanHorse/temp/
```

### Transcription Test
```bash
# Transcription runs automatically on new audio files.
# Check for transcribed text files in your Meeting Notes folder:
ls -la "/Users/YOUR_USERNAME/Documents/Meeting Notes/$(date +%Y-%m-%d)/transcribed_audio/"
```

### Analysis Test
```bash
# Run a full analysis pass (entity extraction, trend calculation)
python3 src/health_monitor.py analyze

# Check for analysis files in your Meeting Notes folder:
ls -la "/Users/YOUR_USERNAME/Documents/Meeting Notes/$(date +%Y-%m-%d)/analysis/"
```

### Search System Test
```bash
# Start the web interface (if not already running via health_monitor)
python3 src/web_interface.py --database trojan_search.db --port 5000 --verbose

# Open in browser
open "http://127.0.0.1:5000"

# Test search functionality via API
curl -X POST -H "Content-Type: application/json" -d '{"query": "test", "type": "hybrid"}' http://127.0.0.1:5000/api/search

# Test analytics dashboard
open "http://127.0.0.1:5000/dashboard"
```

### Workflow Integration Test (Hotkey Client)
1.  Ensure `health_monitor.py` is running (e.g., `python3 src/health_monitor.py monitor &`).
2.  Copy some text to your clipboard (e.g., from a web page or document).
3.  Press the configured hotkey (default: `Cmd+Shift+C`).
4.  You should see a macOS notification with a search result snippet from your transcripts.

### End-to-End Test
```bash
# Complete system test (if test_reliability.py is updated for new services)
# python3 src/test_reliability.py --duration 60 --full-test
```

## 🎮 Step 7: Daily Usage

### Starting the System
To start all core TrojanHorse services (audio capture, internal API, hotkey client):
```bash
python3 src/health_monitor.py start
```

### Accessing Your Data
-   **Web Interface**: `http://127.0.0.1:5000` (or the port configured in `config.json`)
-   **Analytics Dashboard**: `http://127.0.0.1:5000/dashboard`
-   **Files**: `~/Documents/Meeting Notes/YYYY-MM-DD/` (or the `base_path` configured in `config.json`)
-   **Logs**: `~/Documents/TrojanHorse/logs/`

### Common Commands
```bash
# Check system status
python3 src/health_monitor.py status

# Stop all services
python3 src/health_monitor.py stop

# Restart all services
python3 src/health_monitor.py restart

# Run advanced analytics (entity extraction, trend calculation)
python3 src/health_monitor.py analyze

# Optimize the search database (runs VACUUM)
python3 src/health_monitor.py optimize

# Process pending transcriptions (if auto-processing is off or for manual re-runs)
python3 src/transcribe.py

# Reindex transcripts for search (if new transcripts are added manually)
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db

# Update semantic embeddings (if new models are used or for full re-embedding)
python3 -c "from src.semantic_search import SemanticSearch; s=SemanticSearch('trojan_search.db'); s.batch_generate_embeddings(force_regenerate=True); s.close()"
```

## 🔒 Privacy & Security Notes

- **All transcription happens locally** on your machine
- **Raw audio is automatically deleted** after transcription (configurable)
- **Cloud analysis is optional** and can be disabled
- **Search database is local** and never sent to external services
- **Web interface runs locally** and is not accessible from internet

## 🐛 Troubleshooting

### Service Issues
If services are not starting or are unhealthy, check the logs and use `health_monitor.py`:
```bash
# Check service logs
tail -f logs/health_monitor.log
tail -f logs/audio_capture.err
tail -f logs/audio_capture.out

# Check overall system health
python3 src/health_monitor.py status

# Restart all services
python3 src/health_monitor.py restart

# Reinstall service (if launchd plist is corrupted)
python3 src/setup.py uninstall
python3 src/setup.py install
```

### Audio Issues
```bash
# Check audio devices
python3 src/audio_capture.py --list-devices

# Test microphone
python3 -c "
import sounddevice as sd
import numpy as np
print('Testing microphone for 3 seconds...')
audio = sd.rec(int(3 * 44100), samplerate=44100, channels=1)
sd.wait()
print('Audio captured successfully' if audio.max() > 0.01 else 'No audio detected')
"

# Reset audio permissions
tccutil reset Microphone com.apple.Terminal
```

### Transcription Failures
```bash
# Check transcription logs
tail -f "/Users/YOUR_USERNAME/Documents/Meeting Notes/$(date +%Y-%m-%d)/transcription.log"

# Verify MacWhisper or faster-whisper installation
# Check available disk space
df -h
```

### Search & Web Interface Issues
```bash
# Rebuild search database (WARNING: This will delete existing search data)
rm trojan_search.db
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db

# Check web interface logs (run web interface with --verbose)
python3 src/web_interface.py --database trojan_search.db --port 5000 --verbose
```

### Performance Issues
```bash
# Check disk space
df -h

# Check memory usage
top -l 1 | grep -E "(PhysMem|Processes)"

# Monitor system resources
python3 src/health_monitor.py monitor

# Optimize database
python3 src/health_monitor.py optimize
```

## 📞 Support

If you encounter issues:

1. **Check logs** in `logs/` directory
2. **Run health check**: `python3 src/health_monitor.py check`
3. **Verify configuration**: Review `config.json` settings
4. **Test components individually** using the test commands above
5. **Check system permissions** for microphone and file access

---

This setup guide should get you up and running with a fully functional TrojanHorse system. The entire setup process typically takes 30-60 minutes depending on download speeds and hardware.