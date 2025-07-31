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
    "input_device": "BlackHole 2ch",
    "microphone_device": "Built-in Microphone"
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
    "default_type": "local",
    "local_model": "qwen2.5:7b"
  },
  "search": {
    "database_path": "trojan_search.db",
    "enable_semantic": true,
    "web_interface_port": 5000
  }
}
```

**Important**: Replace `YOUR_USERNAME` with your actual username, and update paths as needed.

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
```bash
# Option 1: MacWhisper (recommended for Mac)
mas install 1458140153  # if you have mas-cli
# Or download from Mac App Store: https://apps.apple.com/app/macwhisper/id1458140153

# Option 2: Faster-Whisper (open source alternative)
pip3 install --user faster-whisper

# Test transcription
python3 src/transcribe.py --test
```

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

### Install as macOS Service
```bash
# Install the system service
python3 src/setup.py install

# Verify installation
python3 src/health_monitor.py status
```

### Configure Auto-Start
```bash
# Enable service to start automatically
launchctl load ~/Library/LaunchAgents/com.contextcapture.audio.plist

# Verify service is running
launchctl list | grep contextcapture
```

### Set Up Health Monitoring
```bash
# Test health monitoring
python3 src/health_monitor.py check

# Set up continuous monitoring (optional)
# Add to your shell profile (.zshrc, .bash_profile):
echo 'alias trojan-status="python3 ~/Documents/TrojanHorse/src/health_monitor.py status"' >> ~/.zshrc
echo 'alias trojan-restart="python3 ~/Documents/TrojanHorse/src/health_monitor.py restart"' >> ~/.zshrc
```

## ✅ Step 6: Verification & Testing

### Audio Capture Test
```bash
# Test audio capture for 30 seconds
python3 src/audio_capture.py --test --duration 30

# Check if audio file was created
ls -la temp/
```

### Transcription Test
```bash
# Test transcription on captured audio
python3 src/transcribe.py --test

# Check transcription output
ls -la "Meeting Notes/$(date +%Y-%m-%d)/transcribed_audio/"
```

### Analysis Test
```bash
# Test local analysis
python3 src/analyze_local.py --test

# Test cloud analysis (if configured)
python3 src/cloud_analyze.py --test
```

### Search System Test
```bash
# Test search functionality
python3 -c "
from src.search_engine import SearchEngine
search = SearchEngine('trojan_search.db')
results = search.search('test')
print(f'Found {len(results)} results')
search.close()
"
```

### End-to-End Test
```bash
# Complete system test
python3 src/test_reliability.py --duration 60 --full-test
```

## 🎮 Step 7: Daily Usage

### Starting the System
```bash
# Start all services
python3 src/health_monitor.py restart

# Start web interface (in separate terminal)
python3 src/web_interface.py --database trojan_search.db --port 5000
```

### Accessing Your Data
- **Web Interface**: http://127.0.0.1:5000
- **Files**: `~/Documents/Meeting Notes/YYYY-MM-DD/`
- **Logs**: `~/Documents/TrojanHorse/logs/`

### Common Commands
```bash
# Check system status
python3 src/health_monitor.py status

# Process pending transcriptions
python3 src/transcribe.py

# Reindex transcripts for search
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db

# Update embeddings
python3 -c "from src.semantic_search import SemanticSearch; s=SemanticSearch('trojan_search.db'); s.batch_generate_embeddings(force_regenerate=True); s.close()"
```

## 🔒 Privacy & Security Notes

- **All transcription happens locally** on your machine
- **Raw audio is automatically deleted** after transcription (configurable)
- **Cloud analysis is optional** and can be disabled
- **Search database is local** and never sent to external services
- **Web interface runs locally** and is not accessible from internet

## 🐛 Troubleshooting

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

### Service Issues
```bash
# Check service logs
tail -f logs/audio_capture.err
tail -f logs/audio_capture.out

# Restart services
python3 src/health_monitor.py restart

# Reinstall service
python3 src/setup.py uninstall
python3 src/setup.py install
```

### Search Issues
```bash
# Rebuild search database
rm trojan_search.db
python3 src/batch_indexer.py --base-path "Meeting Notes" --database trojan_search.db

# Check web interface logs
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