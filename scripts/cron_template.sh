#!/usr/bin/env bash
# TrojanHorse cron job template
# Place this in your crontab with: crontab -e
#
# Example crontab entry (every 10 minutes):
# */10 * * * * /path/to/TrojanHorse/scripts/cron_template.sh

# Path to TrojanHorse directory
TROJANHORSE_DIR="${TROJANHORSE_DIR:-$HOME/TrojanHorse}"

# Log file location
LOG_FILE="${LOG_FILE:-$HOME/trojanhorse_cron.log}"

# Change to TrojanHorse directory
cd "$TROJANHORSE_DIR" || exit 1

# Activate virtual environment
if [[ -d "venv" ]]; then
    source venv/bin/activate
else
    echo "[$(date)] ERROR: Virtual environment not found" >> "$LOG_FILE"
    exit 1
fi

# Run TrojanHorse process
echo "[$(date)] Starting TrojanHorse process..." >> "$LOG_FILE"
if th process >> "$LOG_FILE" 2>&1; then
    echo "[$(date)] TrojanHorse process completed successfully" >> "$LOG_FILE"
else
    echo "[$(date)] ERROR: TrojanHorse process failed with exit code $?" >> "$LOG_FILE"
fi