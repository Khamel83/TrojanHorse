# Spec Requirements Document

> Spec: Local LLM Analysis
> Created: 2025-07-30
> Status: Planning

## Overview

Implement local Large Language Model (LLM) analysis capabilities to provide privacy-first insights and summarization of transcribed audio content.

## User Stories

### Automated Summarization

As a user, I want to have my transcribed conversations automatically summarized, so that I can quickly review the key points of a meeting.

### Action Item Extraction

As a user, I want to have action items automatically extracted from my transcribed conversations, so that I can easily track my to-dos.

## Spec Scope

1. **Ollama Integration:** Integrate with the Ollama framework for running local LLMs.
2. **Model Selection:** Allow users to select from a list of supported local LLMs.
3. **Summarization Service:** Create a service that takes transcribed text and generates a summary.
4. **Action Item Service:** Create a service that takes transcribed text and extracts action items.

## Out of Scope

- Real-time analysis during transcription.
- Training or fine-tuning local LLMs.

## Expected Deliverable

1. A new `analyze.py` module that contains the local LLM analysis logic.
2. The ability to run the analysis service from the command line.
3. The output of the analysis (summaries and action items) will be saved to the daily notes file.
