# TrojanHorse: Local Vault Processor + Q&A

A minimal, local-first system that watches folders, processes new text/markdown files, classifies them using LLMs, writes structured notes, and provides RAG-based Q&A.

## Overview

TrojanHorse turns raw notes into organized, searchable knowledge. It integrates with your existing capture tools (Drafts, MacWhisper, etc.) and provides:

- **Automatic processing** of new files in your vault
- **AI-powered classification** and summarization
- **Smart organization** into structured directory hierarchies
- **RAG-powered search** to query your notes with natural language
- **Cross-platform compatibility** (works on macOS, Linux, Windows)

## Quick Start

### 1. Installation

```bash
git clone https://github.com/Khamel83/TrojanHorse.git
cd TrojanHorse

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 2. Configuration

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Required: Root of your vault
WORKVAULT_ROOT=/Users/yourname/Library/Mobile Documents/com~apple~CloudDocs/WorkVault

# Optional: Where raw files are dropped (default: Inbox)
WORKVAULT_CAPTURE_DIRS=Inbox,TranscriptsRaw

# Optional: Where processed notes go (default: next to source files)
WORKVAULT_PROCESSED_ROOT=Processed

# Required: OpenRouter API key (for Gemini Flash 2.5 Lite)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Embedding configuration
EMBEDDING_PROVIDER=openai  # Options: openai, openrouter
EMBEDDING_API_KEY=your_openai_api_key_here
# Or use OpenRouter for embeddings:
# EMBEDDING_PROVIDER=openrouter
# OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
```

### 3. Verify Setup

Run the verification script to check everything is working:

```bash
./scripts/verify_setup.sh
```

### 4. Start Processing

**Option A: One-click workday starter**
```bash
./scripts/start_workday.sh  # Automated setup and start
```

**Option B: Manual setup**
```bash
th setup                    # Initialize directories
th process                  # Process new files once
th workday                  # Run continuous loop (5-min intervals)
```

**Option C: Automated processing**
```bash
# Use provided cron template
*/10 * * * * /path/to/TrojanHorse/scripts/cron_template.sh

# Or install macOS launchd service
cp scripts/com.khamel83.trojanhorse.plist ~/Library/LaunchAgents/
# Edit the file to update paths, then:
launchctl load ~/Library/LaunchAgents/com.khamel83.trojanhorse.plist
```

### 5. Build Search Index

```bash
th embed  # Build the RAG search index for semantic queries
```

### 6. Query Your Notes

```bash
th ask "What did we decide about the WARN project last week?"
th ask "Meeting notes about dashboard analytics"
th ask "What tasks do I have pending?"
```

## Daily Workflows

For detailed user workflows with Drafts, MacWhisper, Wispr Flow, and Zed, see [WORKFLOWS.md](WORKFLOWS.md).

### Quick Reference

| Task | Tool | Command | Result |
|------|------|---------|--------|
| Start day | Terminal | `./scripts/start_workday.sh` | Continuous processing |
| Meeting | MacWhisper | Export to TranscriptsRaw/ | Auto-processed meeting notes |
| Quick capture | Drafts + Wispr | Save to Inbox/ | Auto-categorized notes |
| Search | Terminal | `th ask "question"` | AI-powered answers from notes |

### Multi-Device Setup

**Mac Mini (24/7 Server):**
- Run `./scripts/start_workday.sh` and leave running
- Or use cron/launchd for automated processing
- Hosts the primary database and vault

**Work MacBook (Client):**
- Use `th process` for on-demand processing
- Query with `th ask` as needed
- Both devices share vault via iCloud Drive

## Directory Structure

TrojanHorse creates an organized vault structure:

```
WorkVault/
├── Inbox/                    # Raw files from Drafts, etc.
├── TranscriptsRaw/          # Raw transcripts from MacWhisper
├── Processed/               # Processed notes (if configured)
│   ├── work/
│   │   ├── meetings/
│   │   │   └── 2025/
│   │   ├── emails/
│   │   └── slack/
│   └── personal/
│       ├── ideas/
│       └── logs/
└── .trojanhorse/           # Internal state (SQLite DB, embeddings)
```

## Integration with Other Apps

### Capture Tools

- **Drafts**: Configure to export to your `Inbox` folder
- **MacWhisper Pro**: Set export location to `TranscriptsRaw`
- **Clipboard Manager**: Paste important text into Drafts
- **Wispr Flow**: Dictate into Drafts or any text editor

### Editing and Viewing

- **Zed**: Open your vault as a folder for seamless editing
- **VS Code**: Also works great with the built-in markdown support
- **Any Markdown Editor**: All notes are standard markdown with YAML frontmatter

## Note Format

Processed notes include rich metadata:

```markdown
---
id: "2025-11-25T14:30:00Z_a1b2c3d4"
source: "macwhisper"
raw_type: "meeting_transcript"
class_type: "work"
category: "meeting"
project: "warn_dashboard"
created_at: "2025-11-25T14:25:00Z"
processed_at: "2025-11-25T14:30:05Z"
summary: "Discussed Q4 analytics requirements and dashboard design changes."
tags:
  - work
  - warn
  - meeting
  - analytics
original_path: "/Users/.../TranscriptsRaw/team_sync_2025-11-25.txt"
---

# Analytics Dashboard Sync

Meeting notes about the Q4 analytics requirements...

[Full transcript content]
```

## CLI Commands

### Core Commands

- `th setup` - Initialize directories and test connections
- `th process` - Process new files once (cron-friendly)
- `th workday` - Run continuous processing loop
- `th embed` - Rebuild the search index
- `th ask "question"` - Query your notes
- `th status` - Show system status and statistics

### Options

```bash
th workday --interval 180  # Check every 3 minutes instead of 5
th ask "question" --top-k 5  # Use more context for answers
```

## Architecture

### Components

1. **Config Layer** - Environment-based configuration
2. **LLM Client** - OpenRouter integration for Gemini Flash 2.5 Lite
3. **Classifier** - AI-powered categorization and summarization
4. **Router** - Smart file organization logic
5. **Index DB** - SQLite tracking of processed files
6. **RAG Layer** - Vector search and question answering
7. **Processor** - Batch processing pipeline

### Data Flow

```
Raw Files → Classifier → Router → Processed Notes
                              ↓
                         RAG Index ← Query → Answer
```

## Multi-Device Setup

TrojanHorse is designed to work across multiple devices:

### Mac Mini (Server/24/7)
- Runs continuous processing with `th workday`
- Hosts the vault (ideally on iCloud Drive)
- Can run via cron for fully automated processing

### Work MacBook (Client)
- Create and edit notes during work
- Manual processing with `th process` as needed
- Query and search with `th ask`

### Shared Vault
- Store vault on iCloud Drive or similar
- Both devices access the same files
- Conflict resolution via file modification times

## Development

### Environment Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Code formatting
black trojanhorse/
ruff check trojanhorse/
ruff format trojanhorse/

# Type checking
mypy trojanhorse/
```

### Project Structure

```
trojanhorse/
├── trojanhorse/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── models.py          # Data models and YAML helpers
│   ├── llm_client.py      # OpenRouter API client
│   ├── classifier.py      # AI classification logic
│   ├── router.py          # File organization
│   ├── index_db.py        # Processed file tracking
│   ├── rag.py            # Search and Q&A
│   ├── processor.py      # Main processing pipeline
│   └── cli.py            # Command-line interface
├── tests/                # Test suite
├── .env.example          # Configuration template
├── requirements.txt      # Dependencies
├── pyproject.toml       # Project configuration
└── README.md            # This file
```

## Troubleshooting

### Common Issues

**"Configuration error: WORKVAULT_ROOT environment variable is required"**
- Create `.env` file from `.env.example`
- Set `WORKVAULT_ROOT` to your vault's absolute path

**"No new files to process"**
- Check that files are in your capture directories
- Ensure files have `.txt`, `.md`, or `.rtf` extensions
- Try `th status` to see what directories are being watched

**"OpenRouter connection failed"**
- Verify your `OPENROUTER_API_KEY` is correct
- Check internet connection
- API key may have expired or hit rate limits

**"RAG index empty"**
- Run `th embed` to build the search index
- Ensure you have processed notes first (`th process`)

### Debugging

Enable debug logging:

```bash
RUST_LOG=debug th process
```

Check status and statistics:

```bash
th status
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

- **Issues**: [GitHub Issues](https://github.com/Khamel83/TrojanHorse/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Khamel83/TrojanHorse/discussions)

---

**TrojanHorse** - Turn your notes into knowledge. 🐴