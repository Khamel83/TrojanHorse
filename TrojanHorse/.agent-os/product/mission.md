# Product Mission

## Pitch

TrojanHorse is a local-first, privacy-focused audio capture and transcription system that helps professionals in remote work environments solve the problem of lost context by continuously capturing, transcribing, and organizing work-related conversations and audio into a searchable knowledge base.

## Users

### Primary Customers

- **Remote Workers:** Professionals who spend a significant amount of time in virtual meetings and calls.
- **Knowledge Workers:** Individuals who rely on capturing and recalling information from conversations to perform their jobs effectively.

### User Personas

**Software Developer** (25-45 years old)
- **Role:** Senior Software Engineer
- **Context:** Works on a distributed team, attends multiple daily stand-ups, design sessions, and pair programming calls.
- **Pain Points:** Forgetting key decisions made in meetings, difficulty recalling technical details from discussions.
- **Goals:** Have a searchable record of all work-related conversations, easily find and review past technical discussions.

## The Problem

### Lost Context in Remote Work

In a remote work environment, a significant amount of context is shared through audio and video calls. This information is often ephemeral and easily lost, leading to misunderstandings, repeated conversations, and a general loss of productivity.

**Our Solution:** TrojanHorse provides a seamless way to capture and organize this context, creating a persistent and searchable knowledge base of all work-related conversations.

## Differentiators

### Local-First and Privacy-Focused

Unlike cloud-based transcription services, TrojanHorse processes all data locally, ensuring that sensitive conversations remain private and secure.

### Continuous and Seamless Capture

The system runs in the background, continuously capturing audio without requiring any user interaction, ensuring that no context is missed.

## Key Features

### Core Features

- **Continuous Audio Capture:** FFmpeg-based recording engine for continuous, reliable audio capture.
- **Multi-Engine Transcription:** Supports multiple transcription engines for flexibility and accuracy.
- **Daily Folder Organization:** Organizes transcriptions into daily folders for easy retrieval.
- **Health Monitoring:** System monitoring and automatic restart capabilities.
- **macOS Service Integration:** Runs as a background service on macOS.

### Collaboration Features

- **Search and Memory:** SQLite + FTS5 for instant content retrieval.
- **Semantic Search:** Vector embeddings for concept-based queries.
- **Export System:** Integration with productivity tools.
