# Complete Project Setup Guide

This document provides a complete, step-by-step guide for setting up the TrojanHorse system on a new machine. Follow these instructions in order to ensure a successful installation.

## 1. Prerequisites

Ensure these tools are installed on your system before you begin.

- **Homebrew**: The package manager for macOS. If you don't have it, install it from [https://brew.sh/](https://brew.sh/).
- **Python 3**: The programming language the project is written in. macOS usually comes with Python 3, but you can install a specific version with `brew install python`.
- **Git**: The version control system used to download the project.

## 2. Initial Project & Dependency Installation

This section covers getting the code and installing its core dependencies.

1.  **Clone the Repository**
    Open your terminal and run this command to download the project files:
    ```bash
    git clone https://github.com/Khamel83/TrojanHorse.git
    ```

2.  **Navigate to Project Directory**
    ```bash
    cd TrojanHorse
    ```

3.  **Install FFmpeg**
    This is a critical dependency for audio processing.
    ```bash
    brew install ffmpeg
    ```

4.  **Install Python Dependencies**
    This installs all the required Python libraries.
    ```bash
    pip install -r requirements.txt
    ```

5.  **Download spaCy Language Model**
    This is required for Advanced Analytics.
    ```bash
    python3 -m spacy download en_core_web_sm
    ```

## 3. System Configuration

Now, configure the system for your specific environment.

1.  **Create `config.json`**
    Copy the template configuration file:
    ```bash
    cp config.template.json config.json
    ```

2.  **Edit `config.json`**
    Open `config.json` in a text editor and customize settings like transcription model size, audio quality, storage paths, and API keys. Ensure you update the `openrouter_api_key` if you plan to use cloud analysis. The `privacy` and `workflow_integration` sections are new and provide enhanced control and functionality.

    *Important: Replace placeholder paths like `/Users/YOUR_USERNAME/Documents/Meeting Notes` with your actual paths.*

3.  **Set Cloud API Key (Optional)**
    For cloud-based analysis, you must set your OpenRouter API key. While it can be placed directly in `config.json`, for better security, you can set it as an environment variable. This is a secret and should not be saved in any project file if you choose this method.
    ```bash
    # Add this line to your shell profile (e.g., ~/.zshrc or ~/.bash_profile)
    # Then, restart your terminal or run `source ~/.zshrc`
    export OPENROUTER_API_KEY="your-key-here"
    ```

## 4. macOS Service Setup (for Automation)

These steps are required to run the system as an automated, always-on service.

1.  **Grant System Permissions**
    The application needs permission to access the microphone and file system.

    -   Open **System Settings** > **Privacy & Security**.
    -   **Microphone**: Find your terminal application (e.g., Terminal, iTerm) in the list and enable it.
    -   **Full Disk Access**: Find your terminal application and enable it. This is crucial for the app to read and write files reliably.

2.  **Install BlackHole (Optional)**
    To capture system audio (e.g., from video calls) in addition to your microphone, you must install the free BlackHole virtual audio driver.

    -   **Download from**: [https://existential.audio/blackhole/](https://existential.audio/blackhole/)

3.  **Install TrojanHorse Service**
    The `health_monitor.py` script now manages all core services (audio capture, internal API, hotkey client). This step sets up `health_monitor.py` as a `launchd` service.

    ```bash
    python3 src/setup.py install
    ```

4.  **Load and Start the Service**
    ```bash
    # Copy the plist file to the macOS LaunchAgents directory
    cp com.contextcapture.audio.plist ~/Library/LaunchAgents/

    # Load and start the service
    launchctl load ~/Library/LaunchAgents/com.contextcapture.audio.plist
    ```

## 5. Verification

After completing all the steps, verify that the system is running correctly.

```bash
python3 src/health_monitor.py status
```

If everything is set up correctly, you should see a status report indicating that all services (`audio_capture`, `internal_api`, `hotkey_client`) are running and files are being processed. The system will now run automatically, even after you restart your computer.