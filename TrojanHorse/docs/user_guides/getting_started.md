# Getting Started with TrojanHorse

Welcome to TrojanHorse, your personal context capture system! This guide will help you get the system up and running quickly.

## What is TrojanHorse?

TrojanHorse is a local-first, privacy-focused audio capture and transcription system. It continuously records your microphone and system audio, transcribes everything locally, and provides AI-powered analysis with a searchable web interface. It's designed to help you capture and retrieve important conversations and information from your daily work.

## Quick Setup Checklist

Follow these steps to get TrojanHorse installed and running:

1.  **Install Prerequisites:** Ensure you have Homebrew, Python 3, Git, FFmpeg, and BlackHole installed. Refer to the [Detailed Setup Guide](docs/SETUP.md) for instructions.

2.  **Clone the Repository:**
    ```bash
    cd "/Users/$(whoami)/Documents"  # or your preferred location
    git clone https://github.com/Khamel83/TrojanHorse.git
    cd TrojanHorse
    ```

3.  **Install Python Dependencies & spaCy Model:**
    ```bash
    pip3 install -r requirements.txt
    python3 -m spacy download en_core_web_sm
    ```

4.  **Create and Configure `config.json`:**
    ```bash
    cp config.template.json config.json
    # Open config.json in a text editor and customize paths, API keys, etc.
    ```
    *Important: Update `storage.base_path` to a location where you want your transcripts stored.*

5.  **Install TrojanHorse Service:**
    ```bash
    python3 setup.py install
    ```

6.  **Grant macOS Permissions:**
    You will need to grant Microphone and Full Disk Access permissions to your Terminal application (and Python if prompted) in `System Settings > Privacy & Security > Privacy`.

7.  **Load and Start the Service:**
    ```bash
    cp com.contextcapture.audio.plist ~/Library/LaunchAgents/
    launchctl load ~/Library/LaunchAgents/com.contextcapture.audio.plist
    ```

## First Run & Verification

After installation, verify that TrojanHorse is running correctly:

1.  **Check System Status:**
    ```bash
    python3 src/health_monitor.py status
    ```
    You should see all services (`audio_capture`, `internal_api`, `hotkey_client`) listed as `running`.

2.  **Verify Audio Capture:**
    TrojanHorse continuously captures audio in the background. To confirm it's working, check for new audio files in your temporary storage directory (configured in `config.json`, default is `~/TrojanHorse/temp/`):
    ```bash
    ls -la ~/TrojanHorse/temp/
    ```
    You should see new `.wav` files appearing every few minutes.

3.  **Verify Transcription:**
    As audio files are captured, they are automatically transcribed. Check your main storage directory (configured in `config.json`, default is `~/Meeting Notes/`) for transcribed text files:
    ```bash
    ls -la "/Users/$(whoami)/Documents/Meeting Notes/$(date +%Y-%m-%d)/transcribed_audio/"
    ```
    You should see `.txt` files corresponding to your captured audio.

## Basic Usage

Once verified, TrojanHorse will continue to run in the background, capturing and processing your audio. You can access your data and insights through the web interface.

*   **Web Interface:** Open your browser and go to `http://127.0.0.1:5000` (or the port you configured in `config.json`). Here you can search your transcripts and view analytics.

*   **Hotkey Search:** Copy any text to your clipboard and press your configured hotkey (default: `Cmd+Shift+C`). A system notification will appear with relevant search results from your captured context.

For more detailed usage, refer to the [Daily Operation & Features Guide](docs/user_guides/daily_operation.md).
