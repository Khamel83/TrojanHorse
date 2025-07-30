# Spec Requirements Document

> Spec: Cloud Intelligence
> Created: 2025-07-30
> Status: Planning

## Overview

Integrate with a cloud-based AI service (Gemini Flash 2.0 via OpenRouter) to provide advanced insights and analysis of transcribed audio content.

## User Stories

### Advanced Summarization

As a user, I want to have the option to use a more powerful cloud-based AI to generate higher-quality summaries of my transcribed conversations.

### Deeper Analysis

As a user, I want to be able to ask questions about my transcribed conversations and get answers from a powerful cloud-based AI.

## Spec Scope

1. **OpenRouter Integration:** Integrate with the OpenRouter API to access the Gemini Flash 2.0 model.
2. **API Key Management:** Securely store and manage the OpenRouter API key.
3. **Cloud Analysis Service:** Create a service that sends transcribed text to the OpenRouter API and returns the results.
4. **User Choice:** Allow users to choose between local and cloud-based analysis on a case-by-case basis.

## Out of Scope

- Real-time analysis during transcription.
- Fine-tuning cloud-based models.

## Expected Deliverable

1. A new `cloud_analyze.py` module that contains the cloud-based analysis logic.
2. The ability to run the cloud analysis service from the command line.
3. The output of the analysis will be saved to the daily notes file.
