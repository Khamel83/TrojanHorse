# TrojanHorse Workflows

This document describes the specific user workflows for using TrojanHorse with your daily productivity tools.

## Quick Reference

| Workflow | Command | Frequency | Location |
|----------|---------|-----------|----------|
| Start Workday | `th workday` | Daily, once | Mac mini |
| Process New Files | `th process` | On-demand or cron | Either device |
| Build Search Index | `th embed` | After processing | Either device |
| Query Notes | `th ask "question"` | As needed | Either device |
| Start API Server | `th api` | Continuous for integration | Either device |
| Promote to Atlas | `th promote-to-atlas "ids"` | As needed | Either device |
| Synthesize Meetings | `th meeting-process` | After meetings | Work Mac |
| List Meetings | `th meetings` | As needed | Either device |

## Daily Workflows

### 1. Start of Workday (Mac Mini)

Open Terminal and run:
```bash
cd ~/TrojanHorse
source venv/bin/activate
th workday
```

This starts a continuous processing loop that:
- Checks capture directories every 5 minutes
- Processes new files automatically
- Logs progress to terminal

Leave this running all day in a terminal window or tmux session.

**Alternative: Automated via cron**
```bash
# Edit crontab
crontab -e

# Add this line for every 10 minutes
*/10 * * * * cd /path/to/TrojanHorse && source venv/bin/activate && th process >> ~/trojanhorse_cron.log 2>&1
```

### 2. During the Day (Both Devices)

#### Meeting Workflow (Work Mac)

1. **Start Recording**: Open MacWhisper Pro and begin recording
2. **Export Transcript**: After meeting, export to your vault's `TranscriptsRaw/` folder
3. **Processing**: TrojanHorse will automatically:
   - Classify as "meeting" and "work"
   - Extract key points and summary
   - Organize to `Processed/work/meetings/YYYY/`
4. **Access Later**: Find processed notes in Zed or query with `th ask`

#### Quick Capture Workflow (Any Device + Drafts)

**Voice Notes (iPhone/Mac/Watch):**
1. Open Drafts
2. Use Wispr Flow keyboard or regular typing
3. Save (Drafts auto-exports to your vault's `Inbox/` folder)
4. TrojanHorse processes automatically

**Email/Slack Dumps:**
1. Copy relevant text from email or Slack
2. Paste into new Draft
3. Add context like "Email from boss about project X"
4. Save - TrojanHorse will classify appropriately

#### Task Capture (Any Device)

1. Capture todo items in Drafts
2. Start lines with "TODO:", "ACTION:", or "TASK:"
3. TrojanHorse will categorize as tasks
4. Find them later with `th ask "What tasks do I have?"`

### 3. End of Day

The `th workday` loop continues running. You can:
- Let it run overnight for automated processing
- Stop with Ctrl+C if you prefer manual control
- Check processing status with `th status`

## App-Specific Workflows

### Drafts Integration

TrojanHorse is designed to work with Drafts as the front door for all text on iPhone, iPad, Apple Watch, and macOS.

Think of it this way:
**Drafts is where you type.**
**TrojanHorse is where those thoughts go to live.**

**Setup Drafts:**
1. **Configure Global Shortcuts** (macOS):
   - Main window: `⌃⌥⌘1` (bring Drafts to front)
   - Quick capture: `⌃⌥Space` (new draft from anywhere)
   - Capture clipboard: `⌃⌥⌘V` (draft from clipboard)

2. **Create Export Action**:
   - Name: **Export to TrojanHorse Inbox**
   - Content: `[[draft]]` (or `[[body]]`)
   - File name: `[[created|%Y-%m-%d-%H%M%S]]-[[title]].md`
   - Folder: `WORKVAULT_ROOT/Inbox/`
   - Shortcut: `⌘S`

**Daily Capture Flows:**

**Mac - New Idea:**
1. Press `⌃⌥Space` (Quick capture)
2. Type your thought
3. Press `⌘S` (Export to TrojanHorse)
4. Press Esc (close window)

**Mac - Email/Slack/Web Text:**
1. Select text → Copy (`⌘C`)
2. Press `⌃⌥⌘V` (Capture clipboard)
3. Add context header if needed
4. Press `⌘S` (Export)

**iPhone/iPad/Watch:**
1. Open Drafts
2. Dictate or type your note
3. Tap "Export to TrojanHorse Inbox" action

**Daily Capture Patterns:**
- Meeting notes: Start with "Meeting about X"
- Quick thoughts: Raw text, TrojanHorse categorizes
- Tasks: Start with "TODO:" or "ACTION:"
- Email dumps: Paste and add "Email from Y about Z"

**How it works:**
- Drafts exports plain text files to `WORKVAULT_ROOT/Inbox/`
- TrojanHorse detects, classifies, and processes them automatically
- Notes move to `Processed/` with AI-generated summaries and metadata
- Searchable via `th ask` after `th embed`

### MacWhisper Pro Integration

**Initial Setup (One-Time):**

1. Open MacWhisper Pro → Settings (Cmd+,)
2. **Model Selection**: Choose `WhisperKit large-v3` (with green Speaker Recognition badge)
   - This enables automatic speaker diarization ("Speaker 1:", "Speaker 2:", etc.)
   - Alternative: `large-v3-turbo` for faster processing with minor accuracy loss
3. **Export Configuration**:
   - Default Export Location: `WorkVault/TranscriptsRaw/`
   - Export Format: **Markdown (.md)**
   - Include Timestamps: ON
   - Include Speaker Labels: ON
4. **Optional Watch Folder**:
   - Add a folder for auto-transcription of audio files
   - MacWhisper will process any audio dropped there

**Meeting Recording Process:**

1. **Start Recording**: Click Record (verify red indicator is active and timer moving)
2. **During Meeting**: Let it run (periodically check timer is counting)
3. **End Recording**: Stop and wait for transcription to complete
4. **Review Speakers**: Click speaker names in sidebar to rename them
   - Use number keys (1,2,3) to reassign segments
   - Right-click → "Merge Speaker To..." if wrongly split
5. **Export**: Auto-exports to `TranscriptsRaw/` (or manual Cmd+E)

### Meeting Synthesis Workflow (NEW)

TrojanHorse can synthesize your typed notes with meeting transcripts into structured summaries with action items, decisions, and follow-ups.

**Directory Setup:**
```
WorkVault/
├── HyprnoteExport/       # Hyprnote exports (notes + transcript)
├── TranscriptsRaw/       # MacWhisper backup transcripts
├── MeetingsSynthesized/  # Output: synthesized summaries
└── MeetingNotes/         # Your typed notes (if using Drafts)
```

**Option A: MacWhisper + Drafts (Simplest)**

During meeting:
1. Start MacWhisper Pro recording
2. Open Drafts (Ctrl+Opt+Space for quick capture)
3. Type key notes, decisions, action items
4. Use markers: `ACTION:`, `DECISION:`, `FOLLOWUP:`

After meeting:
1. Stop MacWhisper → exports to `TranscriptsRaw/`
2. Save Drafts note to `MeetingNotes/` or `Inbox/`
3. Run: `th meeting-process`

**Option B: Hyprnote (Granola-like)**

```bash
# Install Hyprnote (optional)
brew tap fastrepl/hyprnote && brew install hyprnote --cask
```

During meeting:
1. Open Hyprnote → New Meeting
2. VERIFY: Recording pulse indicator is active
3. Type notes while seeing recording status
4. (Optional) Start MacWhisper as backup

After meeting:
1. Click "End Meeting" in Hyprnote
2. Export to `WorkVault/HyprnoteExport/`
3. Stop MacWhisper backup
4. Run: `th meeting-process`

**Meeting Synthesis Commands:**

```bash
# Process all new meetings
th meeting-process

# Process specific file
th meeting-process /path/to/meeting.md

# Preview without processing
th meeting-process --dry-run

# Override template
th meeting-process --template committee

# List recent synthesized meetings
th meetings

# Limit results
th meetings --limit 5
```

**HR Meeting Templates:**

TrojanHorse auto-detects meeting type and applies appropriate template:

| Template | Detected When | Key Outputs |
|----------|---------------|-------------|
| `one_on_one` | 2 participants, "1:1", "check-in", career topics | Development notes, follow-ups |
| `committee` | 4+ participants, "committee", "policy", agenda | Decisions, deferred items, minutes |
| `vendor` | "vendor", "contract", "proposal", external names | Commitments, budget implications |
| `default` | No specific signals | Standard summary + action items |

**Template Override:**
```bash
# Force committee template for policy meeting
th meeting-process meeting.md --template committee
```

**Output Example:**
```markdown
# HR Policy Review Committee
**Date:** 2025-12-11 | **Duration:** 65 minutes
**Attendees:** Sarah (Chair), John, Maria, Omar, External: Lisa (Legal)

## Summary
Quarterly policy review covering updated benefits and remote work guidelines...

## Decisions Made
- Approved new PTO accrual rates effective Q1
- Deferred hybrid work policy to next meeting

## Action Items
| Item | Owner | Due |
|------|-------|-----|
| Draft benefits memo | Sarah | Dec 15 |
| Legal review of remote policy | Lisa | Dec 18 |

---
*Synthesized by TrojanHorse*
```

**Workflow Tip:** Run `th meeting-process` at end of workday to batch-process all meetings, then use `th ask "What action items do I have from today's meetings?"` to get a summary.

### Wispr Flow Integration

**Setup Wispr Flow:**
1. Install Wispr Flow keyboard
2. Use in any app (Drafts recommended)
3. Speak naturally, it converts to text
4. TrojanHorse processes the resulting text

### Zed Editor Integration

**Setup Zed:**
1. Open Zed
2. File → Open Folder → Select your `WorkVault/`
3. Create split view: `Cmd+\`
4. Left panel: File tree + notes
5. Right panel: Terminal (optional, for `th workday`)

**Daily Use:**
- Search with `Cmd+Shift+F`
- Navigate processed notes in `Processed/` folder
- Edit and refine as needed
- Changes to processed files don't trigger reprocessing

## File Organization

### Input Structure
```
WorkVault/
├── Inbox/                  # Drafts exports (quick captures)
├── TranscriptsRaw/         # MacWhisper transcript exports
├── MeetingNotes/           # Your typed meeting notes (if using Drafts)
├── HyprnoteExport/         # Hyprnote combined exports (notes + transcript)
└── (other capture dirs)    # As configured in .env
```

### Output Structure
```
WorkVault/
├── MeetingsSynthesized/    # Synthesized meeting summaries
│   ├── 2025-12-11_one_on_one_sarah_career.md
│   ├── 2025-12-11_committee_hr_policy_review.md
│   └── 2025-12-10_vendor_workday_demo.md
└── Processed/              # All other processed notes
    ├── work/
    │   ├── meetings/
    │   │   └── 2025/
    │   │       ├── 2025-01-15_project_sync.md
    │   │       └── 2025-01-16_client_call.md
    │   ├── emails/
    │   ├── slack/
    │   ├── ideas/
    │   └── tasks/
    └── personal/
        ├── ideas/
        ├── logs/
        └── tasks/
```

## Troubleshooting Workflows

### Files Not Processing

**Check:**
1. Is `th workday` running? (Mac mini)
2. Are files in correct capture directories?
3. Run `th status` to check system state
4. Check `~/trojanhorse_cron.log` if using cron

**Manual Process:**
```bash
th process  # Force immediate processing
```

### Classification Issues

**If notes misclassified:**
1. Edit the processed note YAML frontmatter
2. Change `category`, `project`, or `tags`
3. Rebuild search index: `th embed`

### Search Not Working

**If `th ask` returns poor results:**
```bash
th embed  # Rebuild search index
th status # Check indexed notes count
```

## Advanced Workflows

### Multi-Device Sync

**Both devices accessing same vault:**
1. Use iCloud Drive for vault location
2. Run `th workday` on Mac mini (primary)
3. Use `th process` on MacBook when needed
4. Both devices see same processed notes

### Batch Processing

**Process backlog of files:**
```bash
# Add all files to capture directories
# Then run
th process
th embed
```

### Custom Workflows

**Email automation:**
- Set up email rules to forward to Drafts
- TrojanHorse processes automatically

**Meeting automation:**
- Use MacWhisper's auto-transcribe
- Files process automatically every 5 minutes

## API Integration Workflows

### 1. Start API Server for Integration

```bash
# Start API server (default localhost:8765)
th api

# Custom configuration
th api --host 0.0.0.0 --port 9000

# Development with auto-reload
th api --reload
```

**Use Cases:**
- External applications need to query your notes
- Automated processing workflows
- Integration with Atlas or other services
- Web interfaces and dashboards

### 2. API-Based Processing

```bash
# Process files via API
curl -X POST http://localhost:8765/process

# Rebuild search index
curl -X POST http://localhost:8765/embed

# Check system health
curl http://localhost:8765/health
```

### 3. Search and Query via API

```bash
# List notes with filters
curl "http://localhost:8765/notes?category=meeting&limit=20"

# Get specific note
curl http://localhost:8765/notes/{note_id}

# Ask questions (RAG)
curl -X POST http://localhost:8765/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What decisions were made about the project?", "top_k": 5}'
```

### 4. Atlas Integration Workflow

```bash
# Set environment variables
export ATLAS_API_URL="http://localhost:8787"
export ATLAS_API_KEY="your-atlas-key"  # Optional

# Promote curated notes to Atlas
th promote-to-atlas "note1,note2,note3"

# Or use API directly
curl -X POST http://localhost:8765/promote \
  -H "Content-Type: application/json" \
  -d '{"note_ids": ["note1", "note2", "note3"]}'
```

**Atlas Integration Scenarios:**

**Archive Important Ideas:**
```bash
# Find high-value ideas
curl "http://localhost:8765/notes?category=idea&limit=10"

# Promote to Atlas
th promote-to-atlas "idea1,idea2,idea3"
```

**Weekly Knowledge Transfer:**
```bash
# Get this week's meeting notes
notes=$(curl -s "http://localhost:8765/notes?category=meeting&limit=50" | jq -r '.items[].id')

# Transfer to Atlas for long-term storage
th promote-to-atlas "$notes"
```

### 5. External Application Integration

**Python Example:**
```python
import requests

# Search for project-specific notes
response = requests.get(
    "http://localhost:8765/notes",
    params={"project": "warn_dashboard", "limit": 10}
)
notes = response.json()["items"]

# Ask about recent decisions
response = requests.post(
    "http://localhost:8765/ask",
    json={"question": "What decisions were made this week?"}
)
answer = response.json()["answer"]
```

**JavaScript Example:**
```javascript
// Fetch recent notes
const response = await fetch('http://localhost:8765/notes?limit=20');
const data = await response.json();

// Process or display notes
data.items.forEach(note => {
    console.log(`${note.title}: ${note.summary}`);
});
```

## Keyboard Shortcuts Reference

**Drafts:**
- `Cmd+N`: New draft
- `Cmd+S`: Save
- `Cmd+Shift+N`: Quick capture

**MacWhisper:**
- `Space`: Start/stop recording
- `Cmd+E`: Export

**Zed:**
- `Cmd+P`: Open file
- `Cmd+Shift+F`: Search in files
- `Cmd+\`: Split pane

**Terminal:**
- `Ctrl+C`: Stop th workday or API server
- `Cmd+T`: New tab
- `Cmd+W`: Close tab

## Performance Tips

1. **Keep capture directories clean** - move processed files manually if needed
2. **Run `th embed` periodically** - keeps search index fresh
3. **Monitor cron logs** - check for processing errors
4. **Use structured Drafts** - better classification results

## Getting Help

- Run `th --help` for command reference
- Run `th status` for system diagnostics
- Check `~/trojanhorse_cron.log` for cron issues
- Review processed files for classification quality