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

## 6. Drafts Integration for Text Capture

TrojanHorse is designed to work with Drafts as the front door for all text on iPhone, iPad, Apple Watch, and macOS.

Think of it this way:

**Drafts is where you type.**
**TrojanHorse is where those thoughts go to live.**

### Why Drafts?

Drafts is the fastest way to capture text on Apple devices:
- New ideas from your head → Drafts quick capture
- Text from Mail/Slack/web → Drafts clipboard capture
- Voice dictation on phone/watch → Drafts

Drafts then exports those notes as plain text files into your vault's Inbox/ folder, where TrojanHorse picks them up, classifies them, summarizes them, and files them in Processed/.

**Important distinction:**
- Drafts syncs via its own iCloud database (which TrojanHorse can't see)
- TrojanHorse only sees regular files in your iCloud Drive vault

That's why we configure one simple "Export to Vault" action in Drafts.

### 1. Configure Drafts Shortcuts on macOS

On your Mac:
1. Open Drafts → Settings → Shortcuts
2. Set three global shortcuts:

**Main window shortcut**
- Example: `⌃⌥⌘1`
- Use this to bring the full Drafts app to the front

**Quick capture shortcut**
- Example: `⌃⌥Space`
- Use this to open a small "new draft" window from any app

**Capture clipboard shortcut**
- Example: `⌃⌥⌘V`
- Use this to create a new draft from whatever text is currently on your clipboard

**Recommended mental model:**
- "New thought in my head" → Quick capture shortcut
- "Text I just copied from somewhere" → Capture clipboard shortcut
- "I want to work in Drafts for a bit" → Main window shortcut

### 2. Create the "Export to TrojanHorse Inbox" Action

We need exactly one Drafts action that turns a draft into a plain text file inside your vault.

1. In Drafts, open the Actions pane
2. Create a new Action and name it: **Export to TrojanHorse Inbox**
3. Add a "File" step with these settings:

**Template / Content:**
```
[[draft]]
```
(or `[[body]]` if you prefer to skip title metadata)

**File Name (example):**
```
[[created|%Y-%m-%d-%H%M%S]]-[[title]].md
```

**Folder:** your TrojanHorse inbox, which should match:
```
WORKVAULT_ROOT/Inbox
```

For example:
```
/Users/omar/Library/Mobile Documents/com~apple~CloudDocs/WorkVault/Inbox
```

**File Type:** Text or Markdown
**Encoding:** UTF-8

4. Assign a keyboard shortcut to the action, e.g. `⌘S`
5. Add it to the action bar so it's easy to tap on iPhone/iPad

**From now on:** `⌘S` in Drafts means "send this to TrojanHorse."

You decide which drafts deserve to go into the vault by exporting them.

### 3. Daily Capture Flows (Mac)

**A. New idea from anywhere (Mac)**
1. Press your Quick capture shortcut (e.g. `⌃⌥Space`)
2. Type your idea or note
3. Press `⌘S` to run Export to TrojanHorse Inbox
4. Close the capture window (or just press Esc)

**Result:**
- Drafts saves a copy in its own database
- A .md file is created in WorkVault/Inbox/
- TrojanHorse (via `th workday` on the Mac mini) picks it up on the next run

**B. Email / Slack / web text → vault (Mac)**
1. Select the text in Mail/Slack/Browser
2. Press `⌘C` to copy
3. Press your Capture clipboard shortcut (e.g. `⌃⌥⌘V`)
   - Drafts creates a new draft containing the clipboard contents
4. Optionally add a one-line header for context, e.g.:
   ```
   Email from Alex about WARN reporting
   ```
5. Press `⌘S` to export

TrojanHorse will classify this as an email/slack-style note and file it under the appropriate work/personal/category path in Processed/.

**C. Longer notes in the main Drafts window (Mac)**
If you want to stay in Drafts and write something longer:
1. Press the Main window shortcut to bring Drafts forward
2. Create or edit a draft as usual
3. When you're done and want it in the knowledge base, press `⌘S`

You can continue editing in Drafts any time; the exported file in the vault is treated as the source for TrojanHorse. If you edit the exported file in Zed, TrojanHorse tracks it via its internal index.

### 4. Daily Capture Flows (iPhone / Apple Watch)

**On iPhone/iPad:**
- Open Drafts
- Dictate or type your note
- Tap the "Export to TrojanHorse Inbox" action in the action bar

**On Apple Watch:**
- Open Drafts on the Watch
- Dictate a note
- Let it sync to the phone
- On the phone or Mac, run Export to TrojanHorse Inbox on that draft when convenient

### 5. How TrojanHorse Uses Drafts Exports

Once a draft has been exported:
1. A .md or .txt file appears in `WORKVAULT_ROOT/Inbox/`
2. On the Mac mini, `th workday` or `th process` will:
   - Detect the new file
   - Classify it (work vs personal, category, project, tags)
   - Generate a summary and metadata
   - Move it into `WORKVAULT_ROOT/Processed/....`
   - Record it in the internal SQLite index and embeddings store
3. After `th embed`, you can query it with:
   ```bash
   th ask "What did we decide about the WARN project?"
   th ask "What tasks do I have from last week?"
   ```

Drafts' job ends the moment the file is written into Inbox/. Everything else is handled by TrojanHorse.

### 6. Why We Don't Read Directly from Drafts

By design, TrojanHorse does not talk to Drafts' internal database or APIs.

**TrojanHorse:**
- Simple, portable, filesystem-based
- Works with any text source that can write files (Drafts, MacWhisper, editors, scripts)

**Drafts:**
- Manages its own sync, versions, tags, etc. inside its app

This separation keeps TrojanHorse:
- Editor-agnostic (Drafts today, something else tomorrow)
- Platform-agnostic (any tool that can create .txt/.md in your vault works)
- Easier to maintain and reason about

The only contract between them is:

> **Drafts writes plain text files into WORKVAULT_ROOT/Inbox/.**
> **TrojanHorse processes anything it finds there.**