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

## 3. System Configuration

Now, configure the system for your specific environment.

1.  **Set Cloud API Key**
    For cloud-based analysis, you must set your OpenRouter API key as an environment variable. This is a secret and should not be saved in any project file.
    ```bash
    # Add this line to your shell profile (e.g., ~/.zshrc or ~/.bash_profile)
    # Then, restart your terminal or run `source ~/.zshrc`
    export OPENROUTER_API_KEY="your-key-here"
    ```

2.  **Review `config.json` (Optional)**
    The system is configured to work out-of-the-box, but you can review `config.json` to customize settings like the transcription model size or audio quality.

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

3.  **Update and Load the Service File**
    This is the most critical manual step. The `com.contextcapture.audio.plist` file tells macOS how to run the application. You **must** update it to point to the correct project location on your machine.

    -   **A. Edit the file**: Open `com.contextcapture.audio.plist` in a text editor.
    -   **B. Replace the paths**: Find the `ProgramArguments` and `WorkingDirectory` sections. Replace the placeholder paths with the **absolute path** to your `TrojanHorse` project folder.

        *Tip: You can get the absolute path by running `pwd` in your terminal from the project directory.*

        ```xml
        <!-- Example for a user named 'khamel83' -->
        <key>ProgramArguments</key>
        <array>
            <string>/usr/bin/python3</string>
            <string>/Users/khamel83/path/to/TrojanHorse/src/main.py</string>
        </array>
        <key>WorkingDirectory</key>
        <string>/Users/khamel83/path/to/TrojanHorse</string>
        ```

    -   **C. Load the service**: Once the paths are correct, run these commands in your terminal to copy the file and start the service:

        ```bash
        # Copy the file to the macOS LaunchAgents directory
        cp com.contextcapture.audio.plist ~/Library/LaunchAgents/

        # Load and start the service
        launchctl load ~/Library/LaunchAgents/com.contextcapture.audio.plist
        ```

## 5. Verification

After completing all the steps, verify that the system is running correctly.

```bash
python3 src/health_monitor.py status
```

If everything is set up correctly, you should see a status report indicating that the services are running and files are being processed. The service will now run automatically, even after you restart your computer.