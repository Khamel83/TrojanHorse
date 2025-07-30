# Spec Requirements Document

> Spec: TrojanHorse System Completion (Phases 2-3)
> Created: 2025-07-30
> Status: Planning

## Overview

Complete the TrojanHorse Context Capture System through Phase 3 by fixing recording reliability, unifying the analysis architecture, and implementing search & memory capabilities. Priority #1: Audio recording must ALWAYS work when supposed to record.

## User Stories

### Remote Worker (Primary User)

As a remote worker, I want TrojanHorse to reliably capture all my audio conversations and provide searchable analysis, so that I never lose important context and can quickly retrieve past discussions.

The system must start recording on boot, survive crashes, and provide simple local/cloud analysis choices. I should be able to search all my conversations by keyword or concept without any technical complexity.

### System Reliability User  

As someone who depends on context capture, I want the audio recording to work 100% of the time it's supposed to work, so that I never lose conversations due to technical failures.

If recording fails, I want immediate notification and automatic recovery. Everything else can be re-run later, but lost audio is lost forever.

### Long-term Knowledge Worker

As a knowledge worker building context over months, I want to search through all my transcribed conversations semantically and by timeline, so that I can find relevant discussions across weeks or months.

## Spec Scope

1. **Recording Reliability Foundation** - Fix service paths, consolidate configurations, implement bulletproof audio capture
2. **Analysis Architecture Unification** - Replace complex implementations with simple, unified analysis router  
3. **Search & Memory System** - Implement SQLite + FTS5 for keyword search and vector embeddings for semantic search
4. **Web Interface** - Simple browser-based search and retrieval interface
5. **Batch Processing System** - Retroactively index existing transcripts and analysis results
6. **Testing & Validation** - Comprehensive testing focused on recording reliability scenarios

## Out of Scope

- Multi-device synchronization (Phase 4)
- Advanced analytics dashboard (Phase 4)  
- Workflow integration APIs (Phase 4)
- Real-time collaboration features
- External tool integrations beyond basic search

## Expected Deliverable

1. 100% reliable audio recording system that survives restarts, crashes, and permission issues
2. Unified analysis system with simple local/cloud choice that works with existing transcripts
3. Fast keyword search through all transcripts using SQLite FTS5
4. Semantic search capability using vector embeddings for conceptual queries
5. Clean web interface for searching and browsing conversation history
6. Batch indexing system that can process all existing transcripts retroactively

## Spec Documentation

- Tasks: @.agent-os/specs/2025-07-30-system-completion/tasks.md
- Technical Specification: @.agent-os/specs/2025-07-30-system-completion/sub-specs/technical-spec.md