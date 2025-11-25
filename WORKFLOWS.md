# TrojanHorse Workflows

This document describes the specific user workflows for using TrojanHorse with your daily productivity tools.

## Quick Reference

| Workflow | Command | Frequency | Location |
|----------|---------|-----------|----------|
| Start Workday | `th workday` | Daily, once | Mac mini |
| Process New Files | `th process` | On-demand or cron | Either device |
| Build Search Index | `th embed` | After processing | Either device |
| Query Notes | `th ask "question"` | As needed | Either device |

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

**Setup Drafts:**
1. Open Drafts → Settings → Sync
2. Set iCloud Drive location to your vault: `WorkVault/Inbox/`
3. Enable "Automatically create action" if needed

**Daily Capture Patterns:**
- Meeting notes: Start with "Meeting about X"
- Quick thoughts: Raw text, TrojanHorse categorizes
- Tasks: Start with "TODO:" or "ACTION:"
- Email dumps: Paste and add "Email from Y about Z"

### MacWhisper Pro Integration

**Setup MacWhisper:**
1. Open MacWhisper Pro
2. Go to Preferences → Export
3. Set export location: `WorkVault/TranscriptsRaw/`
4. Choose format: Plain text (.txt)

**Meeting Process:**
1. Start recording at meeting start
2. Stop recording at meeting end
3. Review and edit if needed
4. Export (auto-processes via TrojanHorse)

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
├── Inbox/                  # Drafts exports
├── TranscriptsRaw/         # MacWhisper exports
└── (other capture dirs)    # As configured in .env
```

### Output Structure
```
WorkVault/Processed/
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
- `Ctrl+C`: Stop th workday
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