# Daily Operation & Features of TrojanHorse

This guide will walk you through the day-to-day use of TrojanHorse and explain its powerful features for managing your captured context.

## Understanding Your Data

TrojanHorse organizes your captured audio and analysis into a clear, date-based folder structure. By default, this is located in `~/Meeting Notes/` (or the `base_path` you configured in `config.json`).

Each day will have its own folder (e.g., `YYYY-MM-DD/`) containing:

*   `transcribed_audio/`: Contains the raw `.txt` files of your transcribed audio chunks.
*   `analysis/`: Contains the `.analysis.md` files, which are markdown summaries and extracted insights from your transcripts.

## Using the Web Interface

The web interface is your primary tool for interacting with your captured context. Access it by opening your web browser and navigating to `http://127.0.0.1:5000` (or your configured `internal_api_port`).

### Search Your Transcripts

The main page provides a powerful search interface:

*   **Keyword Search:** Type in keywords to find exact matches in your transcripts.
*   **Semantic Search:** Enter concepts or questions, and TrojanHorse will find semantically similar content, even if the exact words aren't present.
*   **Hybrid Search:** (Default) Combines both keyword and semantic search for the most relevant results.

Results are displayed with snippets, timestamps, and links to the full transcript and its analysis.

### View Individual Transcripts

Click on any search result to view the full transcript and its associated AI analysis. The `.analysis.md` file provides a summary, action items, and other extracted information.

### Analytics Dashboard

Navigate to the `/dashboard` route (e.g., `http://127.0.0.1:5000/dashboard`) to access the Analytics Dashboard. This provides high-level insights across your captured data:

*   **Top Entities:** Bar charts showing the most frequently mentioned people, organizations, and locations over a selected period.
*   **Trending Entities:** A table highlighting entities whose mentions have significantly increased recently.

Use the date range selector to customize the period for analysis.

## Leveraging Workflow Integration (Hotkey Client)

The hotkey client allows you to quickly search your captured context from any application.

### Configuration

Your hotkey is configured in `config.json` under `workflow_integration.hotkey`. The default is `Cmd+Shift+C`.

### How to Use

1.  **Copy Text:** Select and copy any text to your system clipboard (e.g., a name, a project code, a question).
2.  **Press Hotkey:** Press your configured hotkey combination.
3.  **Get Notification:** A macOS system notification will appear with the top search result from your TrojanHorse knowledge base, including a snippet and timestamp.

This allows you to get instant context without interrupting your workflow.

## Basic Maintenance

TrojanHorse is designed to run in the background, but a few commands can help you manage it.

*   **Check System Status:**
    ```bash
    python3 src/health_monitor.py status
    ```
    This provides a quick overview of all running services and system health.

*   **Optimize Database:**
    Over time, the search database can become fragmented. Run this command periodically to optimize it:
    ```bash
    python3 src/health_monitor.py optimize
    ```

*   **Run Analytics Manually:**
    Advanced analytics (entity extraction, trend calculation) run automatically, but you can trigger a manual run:
    ```bash
    python3 src/health_monitor.py analyze
    ```

For more advanced troubleshooting and configuration, refer to the [Advanced Configuration & Customization Guide](docs/user_guides/advanced_config.md).
