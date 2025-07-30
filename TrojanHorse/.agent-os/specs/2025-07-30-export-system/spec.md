# Spec Requirements Document

> Spec: Export System
> Created: 2025-07-30
> Status: Planning

## Overview

Implement an export system to allow users to integrate their transcribed conversations and analysis results with other productivity tools.

## User Stories

### Export to Markdown

As a user, I want to export my transcribed conversations and summaries to Markdown files, so that I can easily import them into my note-taking application.

### Export to JSON

As a user, I want to export my transcribed conversations and analysis results to JSON files, so that I can use them in other applications or for further analysis.

## Spec Scope

1. **Markdown Export:** Implement functionality to export selected transcriptions and their associated summaries/action items to Markdown format.
2. **JSON Export:** Implement functionality to export selected transcriptions and their associated analysis results to JSON format.
3. **User Selection:** Allow users to select which conversations or date ranges to export.

## Out of Scope

- Direct integration with specific third-party applications.
- Exporting audio files.

## Expected Deliverable

1. A new `export.py` module that contains the export logic.
2. The ability to export data to Markdown and JSON formats from the command line.
