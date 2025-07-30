# Spec Requirements Document

> Spec: Content Classification
> Created: 2025-07-30
> Status: Planning

## Overview

Implement automated content classification to categorize transcribed conversations and extract action items.

## User Stories

### Automated Categorization

As a user, I want my transcribed conversations to be automatically categorized, so that I can easily find all conversations related to a specific topic.

### Action Item Extraction

As a user, I want to have action items automatically extracted from my transcribed conversations, so that I can easily track my to-dos.

## Spec Scope

1. **Categorization Service:** Create a service that takes transcribed text and assigns it to one or more predefined categories.
2. **Action Item Extraction Service:** Create a service that takes transcribed text and extracts action items.
3. **User Configuration:** Allow users to define their own categories.

## Out of Scope

- Real-time classification during transcription.
- Classifying non-text content.

## Expected Deliverable

1. A new `classify.py` module that contains the content classification logic.
2. The ability to run the classification service from the command line.
3. The classification results (categories and action items) will be saved to the daily notes file.
