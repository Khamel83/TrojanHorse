# macOS Deployment Guide - The Bridge

> Deployment guide for macOS work machines with strict IT policies.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Your MacBook (work)                                          │
│                                                               │
│  Hyprnote ── creates .md files ──> ~/Documents/Hyprnote/    │
│                                                               │
│  The Bridge ── watches folders ──> HTTP POST ──>            │
│    (LaunchAgent)                        │                   │
│                                          │                   │
└──────────────────────────────────────────┼───────────────────┘
                                           │
                                           │ Internet
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────┐
│ oci-dev (Oracle Cloud)                                      │
│                                                               │
│  Atlas API ── http://141.148.146.79:7444/api/notes/        │
│  └── Receives, stores, indexes notes                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Pre-Flight Checklist

### Security Considerations (IT-friendly)

| Concern | Solution |
|---------|----------|
| **Outbound connections** | Only one: HTTP to `141.148.146.79:7444` |
| **Inbound connections** | None (no open ports on Mac) |
| **Data sent** | Markdown files (your notes) - plain text, no encryption in transit |
| **Data received** | None (one-way sync only) |
| **Persistence** | Uses built-in macOS LaunchAgent (standard mechanism) |
| **Privileges** | Runs as your user, no sudo required |
| **Dependencies** | Python packages from PyPI (standard) |

### IT Approval Talking Points

- "It's a file sync utility that backs up my notes to my personal server"
- "Uses macOS built-in job scheduler (LaunchAgent) - no custom kernel stuff"
- "Only makes outbound HTTP requests - no open ports, no incoming connections"
- "Runs under my user account only - no admin privileges"
- "Can be disabled instantly by running: `launchctl unload ~/Library/LaunchAgents/com.bridge.service.plist`"

---

## Installation Steps

### 1. Prerequisites Check

```bash
# Verify Python 3.10+ installed
python3 --version

# Verify git installed
git --version

# Where should project live?
mkdir -p ~/github
cd ~/github
```

### 2. Clone and Setup

```bash
# Clone repository (or copy files if no git access)
cd ~/github
git clone https://github.com/Khamel83/trojanhorse.git
cd trojanhorse

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy template
cp .env.template .env

# Edit with your values
nano .env  # or use VS Code, etc.
```

**Minimal `.env` for Mac:**
```bash
# Atlas Configuration
ATLAS_API_URL="http://141.148.146.79:7444"
ATLAS_API_KEY=""

# Watcher Configuration
WATCH_PATHS="/Users/khamel/Documents/Hyprnote|tags:work,meeting"
DEBOUNCE_SECONDS=30
PROCESSED_SUBDIR="processed"
MOVE_AFTER_SYNC=true

# Logging
LOG_LEVEL="INFO"
LOG_FILE="/Users/khamel/Library/Logs/com.bridge.service/bridge.log"
```

### 4. Create Log Directory

```bash
mkdir -p ~/Library/Logs/com.bridge.service
```

### 5. Test Before Installing

```bash
# Activate venv
source ~/github/trojanhorse/.venv/bin/activate

# Test with a dummy file
echo "# Test Note" > /tmp/test_bridge.md

# Test sync
python bridge/bridge_service.py test \
  --atlas-url http://141.148.146.79:7444 \
  --test-file /tmp/test_bridge.md

# Should see: "Test successful!"
```

### 6. Install LaunchAgent

```bash
# Copy plist to LaunchAgents directory
cp systemd/com.bridge.service.plist ~/Library/LaunchAgents/

# Update paths in plist (if your username/paths differ)
# Edit the plist file to match your actual paths

# Load the service
launchctl load ~/Library/LaunchAgents/com.bridge.service.plist

# Verify it's running
launchctl list | grep com.bridge.service
```

### 7. Verify Everything Works

```bash
# Check logs
tail -f ~/Library/Logs/com.bridge.service/output.log
tail -f ~/Library/Logs/com.bridge.service/error.log

# Create a test file in watched folder
echo "# Hello from Mac" > ~/Documents/Hyprnote/test.md

# Wait 30s (debounce), then check logs for sync
```

---

## Operations

### Check Status

```bash
# Is service running?
launchctl list | grep com.bridge.service

# Recent logs
tail -20 ~/Library/Logs/com.bridge.service/output.log
tail -20 ~/Library/Logs/com.bridge.service/error.log
```

### Restart Service

```bash
launchctl unload ~/Library/LaunchAgents/com.bridge.service.plist
launchctl load ~/Library/LaunchAgents/com.bridge.service.plist
```

### Stop Service

```bash
launchctl unload ~/Library/LaunchAgents/com.bridge.service.plist
# To prevent restart, don't load again
```

### Update Code

```bash
cd ~/github/trojanhorse
git pull
source .venv/bin/activate
pip install -r requirements.txt
launchctl unload ~/Library/LaunchAgents/com.bridge.service.plist
launchctl load ~/Library/LaunchAgents/com.bridge.service.plist
```

---

## Troubleshooting

### Service Not Starting

```bash
# Check plist syntax
plutil -lint ~/Library/LaunchAgents/com.bridge.service.plist

# Check for Python path issues
which python3
# Update plist if paths don't match

# Check permissions
ls -la ~/Library/LaunchAgents/com.bridge.service.plist
```

### Files Not Syncing

```bash
# 1. Verify paths in .env
cat ~/github/trojanhorse/.env | grep WATCH_PATHS

# 2. Check if folder exists
ls -la ~/Documents/Hyprnote/

# 3. Check network connectivity
curl http://141.148.146.79:7444/health

# 4. Run manually to see errors
cd ~/github/trojanhorse
source .venv/bin/activate
python bridge/bridge_service.py run
```

### Atlas Unreachable

```bash
# Test connectivity
curl -v http://141.148.146.79:7444/health

# Check if oci-dev is running
# (You'll need to SSH to oci-dev or check your cloud console)

# Check firewall/security software
# Corporate firewalls may block outbound HTTP to non-standard ports
```

### High Memory/CPU Usage

```bash
# Monitor resource usage
top -pid $(pgrep -f bridge_service.py)

# Should use minimal CPU (idle) and <100MB RAM
# If higher, may need to investigate
```

---

## Uninstall

```bash
# Stop and unload service
launchctl unload ~/Library/LaunchAgents/com.bridge.service.plist

# Remove files
rm ~/Library/LaunchAgents/com.bridge.service.plist
rm -rf ~/github/trojanhorse
rm -rf ~/Library/Logs/com.bridge.service

# Optionally remove processed files from your notes
find ~/Documents/Hyprnote -type d -name "processed" -exec rm -rf {} +
```

---

## Network Diagram for IT

```
Work MacBook
    |
    | HTTP POST (port 7444)
    |
    v
[Corporate Firewall] ──> [Corporate Proxy] ──> [Internet]
                                                    |
                                                    v
                                              oci-dev Oracle Cloud
                                              141.148.146.79:7444
```

**Firewall Rules Required:**
- Outbound TCP to 141.148.146.79 port 7444
- No inbound rules needed

---

## File Locations After Installation

```
~/github/trojanhorse/          # Code and virtual env
├── .venv/                     # Python environment
├── .env                       # Configuration (contains API URL)
├── bridge/                    # Bridge service code
└── systemd/                   # LaunchAgent plist

~/Library/LaunchAgents/
└── com.bridge.service.plist   # Auto-start configuration

~/Library/Logs/com.bridge.service/
├── output.log                 # Standard output
└── error.log                  # Standard error

~/Documents/Hyprnote/          # Your watched folder
├── processed/                 # Successfully synced files
└── [your notes].md            # Active notes
```

---

## Security & Privacy Notes

1. **No sensitive data in .env**: Only URL, no passwords (unless using API key)
2. **Logs may contain note titles**: Consider log rotation if sensitive
3. **HTTPS option**: If Atlas supports SSL, change URL to `https://`
4. **VPN requirement**: If oci-dev is behind VPN, add to .env:
   ```bash
   # Note: Bridge won't work when VPN is disconnected
   ```

---

## Next Steps

1. **Test on personal Mac first** (if you have one)
2. **Document exact paths** for your work machine
3. **Prepare IT justification** using talking points above
4. **Schedule install** when you have time to troubleshoot
5. **Keep uninstall instructions handy**

---

**Last Updated:** 2026-02-02
